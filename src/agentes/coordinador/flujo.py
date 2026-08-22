"""Flujo del coordinador (F3), sin LLM: planea, delega, decide si el viaje sale.

    validando ─┬─ validador   (cross_check)      ─┐
               └─ cumplimiento (vigencias_query) ─┴─► fusión ─► ¿bloqueos duros?
                                                        sí → seguimiento (proponer_accion) → bloqueado
                                                        no → listo

Cada paso pasa por `ejecutar_handoff` (validación Pydantic, reintento, dead-letter).
El coordinador solo lee el expediente y delega (CLAUDE.md <agent_contracts>).
Las funciones de paso son puras respecto a ADK: `flota.py` las envuelve en agentes.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, TypeAdapter

from dominio.enums import EstadoAccion, EstadoViaje, MotivoBloqueo
from dominio.estados import transitar
from dominio.modelos import AccionPropuesta, Activo, Bloqueo, HandoffResult, Operador, Transportista, Viaje
from infra.handoff import ejecutar_handoff
from infra.idempotencia import clave_idempotencia
from tools.registry import ToolRegistry

AGENTE = "coordinador"
LISTA_BLOQUEOS = TypeAdapter(list[Bloqueo])


@dataclass
class Servicios:
    repo: Any
    ledger: Any
    registro: ToolRegistry
    hoy: date
    publisher: Any = None
    pac: Any = None  # infra.pac_mock.PacMock en todos los entornos del hackathon


class CartaPorteTimbrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    viaje_id: str
    tenant_id: str
    id_ccp: str
    uuid: str
    hash_xml: str
    xml: str


def _expediente(viaje: Viaje, s: Servicios) -> tuple[Activo | None, list[Activo], Operador | None]:
    tractor = s.repo.obtener("activos", viaje.tractor_id, Activo)
    cajas = [c for c in (s.repo.obtener("activos", i, Activo) for i in viaje.caja_ids) if c is not None]
    operador = s.repo.obtener("operadores", viaje.operador_id, Operador)
    return tractor, cajas, operador


def paso_validador(viaje: Viaje, s: Servicios) -> tuple[list[Bloqueo], HandoffResult]:
    cross_check = s.registro.resolver("validador", "cross_check")
    tractor, cajas, operador = _expediente(viaje, s)
    bloqueos, resultado = ejecutar_handoff(
        agente="validador", paso_id=f"validador:{viaje.viaje_id}",
        llamar=lambda _err: cross_check(viaje, tractor, cajas, operador, s.hoy),
        validar=LISTA_BLOQUEOS.validate_python, ledger=s.ledger, tenant_id=viaje.tenant_id,
        viaje_id=viaje.viaje_id, publisher=s.publisher,
    )
    return _o_fallo(bloqueos, resultado, viaje, s, "validador"), resultado


def paso_cumplimiento(viaje: Viaje, s: Servicios) -> tuple[list[Bloqueo], HandoffResult]:
    vigencias_query = s.registro.resolver("cumplimiento", "vigencias_query")
    bloqueos, resultado = ejecutar_handoff(
        agente="cumplimiento", paso_id=f"cumplimiento:{viaje.viaje_id}",
        llamar=lambda _err: vigencias_query(tenant_id=viaje.tenant_id, viaje_id=viaje.viaje_id,
                                            activo_ids=[viaje.tractor_id, *viaje.caja_ids],
                                            operador_id=viaje.operador_id, hoy=s.hoy),
        validar=LISTA_BLOQUEOS.validate_python, ledger=s.ledger, tenant_id=viaje.tenant_id,
        viaje_id=viaje.viaje_id, publisher=s.publisher,
    )
    return _o_fallo(bloqueos, resultado, viaje, s, "cumplimiento"), resultado


def _o_fallo(bloqueos: list[Bloqueo] | None, r: HandoffResult, viaje: Viaje, s: Servicios, agente: str) -> list[Bloqueo]:
    """Si el sub-agente fue a dead-letter, el viaje no sale: bloqueo duro `verificacion_fallida`."""
    if bloqueos is not None:
        return bloqueos
    return [Bloqueo(
        bloqueo_id=f"blq-{viaje.viaje_id}-{MotivoBloqueo.verificacion_fallida}-{agente}",
        motivo=MotivoBloqueo.verificacion_fallida, severidad="duro",
        explicacion=f"{agente} no pudo verificar el viaje tras {r.intentos} intentos ({r.estado}); revisar dead-letter.",
        documento_id=None, evidencia_uri=f"expediente://dead_letters/dl-{r.paso_id}", accion_propuesta_id=None,
        detectado_por=AGENTE, detectado_en=datetime.combine(s.hoy, time.min, tzinfo=timezone.utc),
    )]


def fusionar(viaje: Viaje, detectados: list[Bloqueo]) -> list[Bloqueo]:
    """La detección nueva manda: lo que ya no se detecta desaparece; lo re-detectado se
    reabre aunque un humano hubiera aprobado una acción (aprobar no hace legal al camión;
    la evidencia sí). Se conserva la acción ya propuesta para no duplicarla."""
    previos = {b.bloqueo_id: b for b in viaje.bloqueos}
    out: list[Bloqueo] = []
    for b in detectados:
        prev = previos.get(b.bloqueo_id)
        out.append(b.model_copy(update={"accion_propuesta_id": prev.accion_propuesta_id}) if prev else b)
    return out


def paso_seguimiento(viaje: Viaje, bloqueos: list[Bloqueo], s: Servicios) -> list[Bloqueo]:
    proponer_accion = s.registro.resolver("seguimiento", "proponer_accion")
    out: list[Bloqueo] = []
    for b in bloqueos:
        if b.severidad == "duro" and b.abierto:
            accion = proponer_accion(bloqueo=b, tenant_id=viaje.tenant_id, viaje_id=viaje.viaje_id, hoy=s.hoy)
            b = b.model_copy(update={"accion_propuesta_id": accion.accion_id})
        out.append(b)
    return out


def decidir(viaje: Viaje, bloqueos: list[Bloqueo], s: Servicios) -> Viaje:
    """La decisión del coordinador: bloqueado o listo. Siempre queda en el ledger."""
    viaje = viaje.model_copy(update={"bloqueos": bloqueos})
    duros = viaje.bloqueos_duros_abiertos()
    decision = EstadoViaje.bloqueado if duros else EstadoViaje.listo
    s.ledger.append(
        tenant_id=viaje.tenant_id, viaje_id=viaje.viaje_id, tipo_evento="decision_coordinador", actor=AGENTE,
        payload={"decision": decision, "bloqueos_duros": [b.bloqueo_id for b in duros],
                 "bloqueos_blandos": [b.bloqueo_id for b in viaje.bloqueos if b.severidad == "blando"],
                 "acciones_propuestas": [b.accion_propuesta_id for b in duros if b.accion_propuesta_id]},
        idempotency_key=clave_idempotencia(viaje.viaje_id, "decision", [b.model_dump(mode="json") for b in viaje.bloqueos]),
    )
    return transitar(viaje, decision, ledger=s.ledger, repo=s.repo, actor=AGENTE)


def procesar_viaje(viaje_id: str, s: Servicios) -> Viaje:
    """Versión síncrona sin ADK (tests y API). `flota.py` hace lo mismo con agentes ADK."""
    viaje = s.repo.obtener("viajes", viaje_id, Viaje)
    if viaje is None:
        raise KeyError(viaje_id)
    if viaje.estado == EstadoViaje.borrador:
        viaje = transitar(viaje, EstadoViaje.validando, ledger=s.ledger, repo=s.repo, actor=AGENTE)
    if viaje.estado != EstadoViaje.validando:
        raise ValueError(f"{viaje_id} está en {viaje.estado}; solo se procesa en validando")
    b_val, _ = paso_validador(viaje, s)
    b_cum, _ = paso_cumplimiento(viaje, s)
    bloqueos = paso_seguimiento(viaje, fusionar(viaje, b_val + b_cum), s)
    return decidir(viaje, bloqueos, s)


def reanudar_tras_aprobacion(viaje_id: str, accion_id: str, s: Servicios) -> Viaje:
    """Un humano aprobó la acción: bloqueado → validando y se vuelve a procesar."""
    viaje = s.repo.obtener("viajes", viaje_id, Viaje)
    accion = s.repo.obtener("acciones", accion_id, AccionPropuesta)
    if viaje is None or accion is None or accion.estado != EstadoAccion.aprobada:
        raise ValueError("se requiere un viaje bloqueado y una acción aprobada")
    transitar(viaje, EstadoViaje.validando, ledger=s.ledger, repo=s.repo, actor=AGENTE, accion=accion)
    return procesar_viaje(viaje_id, s)


def despachar(viaje_id: str, s: Servicios) -> tuple[Viaje, Any]:
    """listo → en_ruta: construye la Carta Porte, la pasa por el PAC (mock) y sale.
    El XML y el timbre quedan en el expediente; el hash del XML, en el ledger."""
    from infra.pac_mock import PacMock
    from tools.carta_porte import id_ccp

    construir_carta_porte = s.registro.resolver("validador", "construir_carta_porte")

    viaje = s.repo.obtener("viajes", viaje_id, Viaje)
    if viaje is None or viaje.estado != EstadoViaje.listo:
        raise ValueError(f"{viaje_id} no está en listo")
    tractor, cajas, operador = _expediente(viaje, s)
    transportista = s.repo.obtener("transportistas", viaje.tenant_id, Transportista)
    if transportista is None:
        raise ValueError(f"no hay transportista para {viaje.tenant_id}")
    xml = construir_carta_porte(viaje, tractor, cajas, operador, transportista)
    timbre = (s.pac or PacMock()).timbrar(xml)
    s.ledger.append(
        tenant_id=viaje.tenant_id, viaje_id=viaje_id, tipo_evento="carta_porte_timbrada_mock", actor=AGENTE,
        payload={"id_ccp": id_ccp(viaje_id), "uuid": timbre.uuid, "hash_xml": timbre.hash_xml, "pac": timbre.pac},
        idempotency_key=clave_idempotencia(viaje_id, "timbrado", timbre.hash_xml),
    )
    s.repo.guardar("cartas_porte", viaje_id, CartaPorteTimbrada(
        viaje_id=viaje_id, tenant_id=viaje.tenant_id, id_ccp=id_ccp(viaje_id), uuid=timbre.uuid,
        hash_xml=timbre.hash_xml, xml=xml.decode("utf-8")))
    return transitar(viaje, EstadoViaje.en_ruta, ledger=s.ledger, repo=s.repo, actor=AGENTE, carta_porte_xml=xml), timbre
