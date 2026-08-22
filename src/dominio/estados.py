"""Máquina de estados del viaje (CLAUDE.md <state_machine>).

    borrador → validando → bloqueado ⇄ validando → listo → en_ruta → cerrado
                                                     ↓
                                               cancelado (desde cualquier estado)

Toda transición se escribe al ledger ANTES de persistirse.
"""

from typing import Any

from dominio.enums import EstadoAccion, EstadoViaje
from dominio.modelos import AccionPropuesta, Viaje

E = EstadoViaje

TRANSICIONES: dict[EstadoViaje, frozenset[EstadoViaje]] = {
    E.borrador: frozenset({E.validando, E.cancelado}),
    E.validando: frozenset({E.bloqueado, E.listo, E.cancelado}),
    E.bloqueado: frozenset({E.validando, E.cancelado}),
    E.listo: frozenset({E.en_ruta, E.cancelado}),
    E.en_ruta: frozenset({E.cerrado, E.cancelado}),
    E.cerrado: frozenset(),
    E.cancelado: frozenset(),
}


class TransicionInvalida(Exception):
    pass


def transitar(
    viaje: Viaje,
    destino: EstadoViaje,
    *,
    ledger: Any,
    repo: Any,
    actor: str,
    accion: AccionPropuesta | None = None,
    carta_porte_xml: bytes | None = None,
) -> Viaje:
    """Devuelve el viaje en su nuevo estado. No muta el recibido."""
    origen = viaje.estado
    if destino not in TRANSICIONES[origen]:
        raise TransicionInvalida(f"{origen} → {destino} no está permitida")

    nuevo = viaje.model_copy(deep=True)

    if origen == E.validando and destino == E.listo and nuevo.bloqueos_duros_abiertos():
        ids = [b.bloqueo_id for b in nuevo.bloqueos_duros_abiertos()]
        raise TransicionInvalida(f"validando → listo exige cero bloqueos duros; abiertos: {ids}")

    if origen == E.validando and destino == E.bloqueado and not nuevo.bloqueos_duros_abiertos():
        raise TransicionInvalida("validando → bloqueado exige al menos un bloqueo duro")

    if origen == E.bloqueado and destino == E.validando:
        if accion is None or accion.viaje_id != nuevo.viaje_id:
            raise TransicionInvalida("bloqueado → validando exige una AccionPropuesta de este viaje")
        if accion.estado != EstadoAccion.aprobada:
            raise TransicionInvalida(f"la acción {accion.accion_id} no está aprobada por un humano")
        bloqueo = next((b for b in nuevo.bloqueos if b.bloqueo_id == accion.bloqueo_id and b.abierto), None)
        if bloqueo is None:
            raise TransicionInvalida(f"la acción {accion.accion_id} no resuelve ningún bloqueo abierto")
        bloqueo.resuelto_por_accion_id = accion.accion_id

    if origen == E.listo and destino == E.en_ruta:
        from tools.xsd_validate import xsd_validate  # import tardío: el esquema pesa

        if carta_porte_xml is None:
            raise TransicionInvalida("listo → en_ruta exige el payload de Carta Porte")
        errores = xsd_validate(carta_porte_xml)
        if errores:
            raise TransicionInvalida(f"Carta Porte inválida contra XSD: {errores[:3]}")

    nuevo.estado = destino
    ledger.append(
        tenant_id=nuevo.tenant_id,
        viaje_id=nuevo.viaje_id,
        tipo_evento="transicion_viaje",
        actor=actor,
        payload={"de": origen, "a": destino, "accion_id": accion.accion_id if accion else None},
    )
    repo.guardar("viajes", nuevo.viaje_id, nuevo)
    return nuevo
