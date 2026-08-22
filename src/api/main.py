"""API de GARITA para Cloud Run. Dos vistas del frontend: cola de aprobación y expediente.

Los agentes corren con el Runner de ADK dentro de `procesar`; el servidor de
desarrollo de ADK (/run, /run_sse, sesiones) NO se monta aquí: expondría el
agente `hello` y endpoints de pruebas. Sin autenticación propia: el servicio se
protege con IAM de Cloud Run (F5).
"""

import os

from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel

from agentes.coordinador import flujo
from agentes.flota import procesar_viaje_adk, procesar_viaje_adk_simple
from api.deps import construir_servicios
from dominio.acciones import AccionNoPendiente, aprobar, cola_de_aprobacion, rechazar
from dominio.enums import EstadoAccion, EstadoViaje
from dominio.estados import TransicionInvalida
from dominio.modelos import AccionPropuesta, Activo, DocumentoVigencia, EntradaLedger, Operador, Viaje
from infra.ledger import LedgerAlterado
from infra.pac_mock import TimbradoRechazado
from tools.carta_porte import CartaPorteIncompleta

app = FastAPI(title="GARITA", version="0.3")
app.state.servicios = construir_servicios()
api = APIRouter(prefix="/api")
TENANT = os.environ.get("GARITA_TENANT", "tenant-cafe57-sintetico")


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
        try:
            return flujo.reanudar_tras_aprobacion(viaje_id, aprobadas[0].accion_id, s, procesar=procesar_viaje_adk_simple)
        except (ValueError, TransicionInvalida) as e:
            raise HTTPException(409, str(e))
    if viaje.estado not in (EstadoViaje.borrador, EstadoViaje.validando):
        raise HTTPException(409, f"viaje en {viaje.estado}; no se procesa")
    viaje, _eventos = procesar_viaje_adk(viaje_id, s)
    return viaje


@api.post("/viajes/{viaje_id}/despachar")
def despachar(viaje_id: str, cuerpo: Humano) -> dict:
    """Efecto externo (timbrado): lo autoriza un humano con nombre; queda en el ledger."""
    try:
        viaje, timbre = flujo.despachar(viaje_id, _s(), humano=cuerpo.humano)
    except (CartaPorteIncompleta, TimbradoRechazado) as e:  # subclases de ValueError: van antes
        raise HTTPException(422, str(e))
    except (ValueError, TransicionInvalida) as e:
        raise HTTPException(409, str(e))
    return {"viaje": viaje, "timbre": timbre}


@api.get("/acciones", response_model=list[AccionPropuesta])
def acciones(estado: EstadoAccion = EstadoAccion.pendiente_aprobacion, tenant_id: str = TENANT) -> list[AccionPropuesta]:
    """La cola de aprobación. Siempre por tenant (se transporta, no se aísla: CLAUDE.md)."""
    if estado == EstadoAccion.pendiente_aprobacion:
        return cola_de_aprobacion(_s().repo, tenant_id)
    return _s().repo.listar("acciones", AccionPropuesta, tenant_id=tenant_id, estado=estado)


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
    if viaje is not None and viaje.estado == EstadoViaje.bloqueado:
        if accion.estado == EstadoAccion.aprobada:
            try:  # se revalida con la evidencia actual; si el bloqueo ya no está abierto, la aprobación queda y el viaje no cambia
                viaje = flujo.reanudar_tras_aprobacion(accion.viaje_id, accion.accion_id, s, procesar=procesar_viaje_adk_simple)
            except (ValueError, TransicionInvalida):
                pass
        elif accion.estado == EstadoAccion.rechazada:
            viaje = flujo.reproponer_tras_rechazo(accion.viaje_id, s)  # el viaje no se queda sin salida
    return {"accion": accion, "viaje": viaje}


@api.post("/acciones/{accion_id}/aprobar")
def aprobar_accion(accion_id: str, cuerpo: Humano) -> dict:
    return _resolver_accion(accion_id, cuerpo.humano, aprobar)


@api.post("/acciones/{accion_id}/rechazar")
def rechazar_accion(accion_id: str, cuerpo: Humano) -> dict:
    return _resolver_accion(accion_id, cuerpo.humano, rechazar)


ID_POR_COLECCION = {"activos": ("activo_id", Activo), "operadores": ("operador_id", Operador)}


@api.put("/documentos/{documento_id}", response_model=DocumentoVigencia)
def registrar_documento(documento_id: str, documento: DocumentoVigencia) -> DocumentoVigencia:
    """Alta manual de un documento ya extraído (la ingesta con Gemma/Gemini lo hará sola).
    Sustituye el documento en el activo u operador que lo referencia; el campo debe
    corresponder al tipo del documento y el objeto se revalida completo."""
    s = _s()
    if documento.documento_id != documento_id:
        raise HTTPException(422, "documento_id del cuerpo no coincide con la ruta")
    actualizado = False
    for coleccion, (campo_id, tipo) in ID_POR_COLECCION.items():
        for obj in s.repo.listar(coleccion, tipo, tenant_id=documento.tenant_id):
            datos = obj.model_dump(mode="json")
            for campo, valor in datos.items():
                if isinstance(valor, dict) and valor.get("documento_id") == documento_id:
                    if campo != documento.tipo:
                        raise HTTPException(422, f"{documento_id} es {campo} en {coleccion}/{datos[campo_id]}; el cuerpo dice {documento.tipo}")
                    s.repo.guardar(coleccion, datos[campo_id], tipo.model_validate(datos | {campo: documento.model_dump(mode="json")}))
                    actualizado = True
    if not actualizado:
        raise HTTPException(404, f"ningún activo u operador referencia {documento_id}")
    s.repo.guardar("documentos", documento_id, documento)
    s.ledger.append(tenant_id=documento.tenant_id, viaje_id="", tipo_evento="documento_registrado", actor="humano",
                    payload={"documento_id": documento_id, "estado": documento.estado, "hash_documento": documento.hash_documento},
                    idempotency_key=f"doc:{documento_id}:{documento.hash_documento}")
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
