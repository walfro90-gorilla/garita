"""API de GARITA para Cloud Run. Dos vistas del frontend: cola de aprobación y expediente.

Monta el servidor de ADK (agentes en src/agentes) y encima las rutas del negocio.
Sin autenticación propia: el servicio se protege con IAM de Cloud Run (F5).
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from google.adk.cli.fast_api import get_fast_api_app
from pydantic import BaseModel

from agentes.coordinador import flujo
from agentes.flota import procesar_viaje_adk
from api.deps import construir_servicios
from dominio.acciones import AccionNoPendiente, aprobar, cola_de_aprobacion, rechazar
from dominio.enums import EstadoAccion, EstadoViaje
from dominio.estados import TransicionInvalida
from dominio.modelos import AccionPropuesta, Activo, DocumentoVigencia, EntradaLedger, Operador, Viaje
from infra.ledger import LedgerAlterado
from infra.pac_mock import TimbradoRechazado
from tools.carta_porte import CartaPorteIncompleta

AGENTES_DIR = str(Path(__file__).resolve().parents[1] / "agentes")

app = get_fast_api_app(agents_dir=AGENTES_DIR, web=False)
app.state.servicios = construir_servicios()
api = APIRouter(prefix="/api")


def _s() -> flujo.Servicios:
    return app.state.servicios


class Humano(BaseModel):
    humano: str


class Expediente(BaseModel):
    viaje: Viaje
    tractor: Activo | None
    cajas: list[Activo]
    operador: Operador | None
    acciones: list[AccionPropuesta]
    ledger: list[EntradaLedger]


@api.get("/salud")
def salud() -> dict:
    return {"ok": True, "region_pii": "northamerica-south1", "gemini": "global", "pac": "mock"}


@api.get("/viajes/{viaje_id}", response_model=Expediente)
def expediente(viaje_id: str) -> Expediente:
    s = _s()
    viaje = s.repo.obtener("viajes", viaje_id, Viaje)
    if viaje is None:
        raise HTTPException(404, f"viaje {viaje_id} no existe")
    tractor, cajas, operador = flujo._expediente(viaje, s)
    return Expediente(
        viaje=viaje, tractor=tractor, cajas=cajas, operador=operador,
        acciones=s.repo.listar("acciones", AccionPropuesta, viaje_id=viaje_id),
        ledger=[e for e in s.ledger.entradas if e.viaje_id == viaje_id],
    )


@api.post("/viajes/{viaje_id}/procesar", response_model=Viaje)
def procesar(viaje_id: str) -> Viaje:
    """borrador/validando → corre la flota. bloqueado → solo si un humano ya aprobó una acción
    de un bloqueo abierto: se reanuda y se revalida con la evidencia actual."""
    s = _s()
    viaje = s.repo.obtener("viajes", viaje_id, Viaje)
    if viaje is None:
        raise HTTPException(404, f"viaje {viaje_id} no existe")
    if viaje.estado == EstadoViaje.bloqueado:
        aprobadas = [a for a in s.repo.listar("acciones", AccionPropuesta, viaje_id=viaje_id, estado=EstadoAccion.aprobada)
                     if any(b.abierto and b.accion_propuesta_id == a.accion_id for b in viaje.bloqueos)]
        if not aprobadas:
            raise HTTPException(409, "viaje bloqueado: esperando aprobación humana de la acción propuesta")
        return flujo.reanudar_tras_aprobacion(viaje_id, aprobadas[0].accion_id, s)
    if viaje.estado not in (EstadoViaje.borrador, EstadoViaje.validando):
        raise HTTPException(409, f"viaje en {viaje.estado}; no se procesa")
    viaje, _eventos = procesar_viaje_adk(viaje_id, s)
    return viaje


@api.post("/viajes/{viaje_id}/despachar")
def despachar(viaje_id: str) -> dict:
    try:
        viaje, timbre = flujo.despachar(viaje_id, _s())
    except (ValueError, TransicionInvalida) as e:
        raise HTTPException(409, str(e))
    except (CartaPorteIncompleta, TimbradoRechazado) as e:
        raise HTTPException(422, str(e))
    return {"viaje": viaje, "timbre": timbre}


@api.get("/acciones", response_model=list[AccionPropuesta])
def acciones(estado: EstadoAccion = EstadoAccion.pendiente_aprobacion, tenant_id: str | None = None) -> list[AccionPropuesta]:
    s = _s()
    filtro = {"estado": estado} | ({"tenant_id": tenant_id} if tenant_id else {})
    return s.repo.listar("acciones", AccionPropuesta, **filtro)


def _resolver_accion(accion_id: str, humano: str, fn) -> dict:
    s = _s()
    accion = s.repo.obtener("acciones", accion_id, AccionPropuesta)
    if accion is None:
        raise HTTPException(404, f"acción {accion_id} no existe")
    try:
        accion = fn(accion, humano, ledger=s.ledger, repo=s.repo)
    except AccionNoPendiente as e:
        raise HTTPException(409, str(e))
    viaje = s.repo.obtener("viajes", accion.viaje_id, Viaje)
    if accion.estado == EstadoAccion.aprobada and viaje is not None and viaje.estado == EstadoViaje.bloqueado:
        viaje = flujo.reanudar_tras_aprobacion(accion.viaje_id, accion.accion_id, s)  # se revalida con la evidencia actual
    return {"accion": accion, "viaje": viaje}


@api.post("/acciones/{accion_id}/aprobar")
def aprobar_accion(accion_id: str, cuerpo: Humano) -> dict:
    return _resolver_accion(accion_id, cuerpo.humano, aprobar)


@api.post("/acciones/{accion_id}/rechazar")
def rechazar_accion(accion_id: str, cuerpo: Humano) -> dict:
    return _resolver_accion(accion_id, cuerpo.humano, rechazar)


@api.put("/documentos/{documento_id}", response_model=DocumentoVigencia)
def registrar_documento(documento_id: str, documento: DocumentoVigencia) -> DocumentoVigencia:
    """Alta manual de un documento ya extraído (la ingesta con Gemma/Gemini lo hará sola).
    Actualiza el activo u operador que lo referencia por documento_id."""
    s = _s()
    if documento.documento_id != documento_id:
        raise HTTPException(422, "documento_id del cuerpo no coincide con la ruta")
    actualizado = False
    for coleccion, tipo in (("activos", Activo), ("operadores", Operador)):
        for obj in s.repo.listar(coleccion, tipo, tenant_id=documento.tenant_id):
            for campo, valor in obj.model_dump().items():
                if isinstance(valor, dict) and valor.get("documento_id") == documento_id:
                    s.repo.guardar(coleccion, getattr(obj, f"{coleccion[:-1] if coleccion != 'activos' else 'activo'}_id"),
                                   obj.model_copy(update={campo: documento}))
                    actualizado = True
    if not actualizado:
        raise HTTPException(404, f"ningún activo u operador referencia {documento_id}")
    s.repo.guardar("documentos", documento_id, documento)
    s.ledger.append(tenant_id=documento.tenant_id, viaje_id="", tipo_evento="documento_registrado", actor="humano",
                    payload={"documento_id": documento_id, "estado": documento.estado, "hash_documento": documento.hash_documento})
    return documento


@api.get("/ledger/verify")
def verificar_ledger() -> dict:
    s = _s()
    try:
        s.ledger.verify()
    except LedgerAlterado as e:
        return {"integro": False, "entrada": e.secuencia, "motivo": str(e), "entradas": len(s.ledger.entradas)}
    return {"integro": True, "entradas": len(s.ledger.entradas)}


app.include_router(api)
