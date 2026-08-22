"""Compuerta humana (ADR-005). Un agente propone; solo aquí un humano aprueba o rechaza."""

from datetime import datetime, timezone

from dominio.enums import EstadoAccion
from dominio.modelos import AccionPropuesta


class AccionNoPendiente(Exception):
    pass


def _resolver(accion: AccionPropuesta, destino: EstadoAccion, humano: str, *, ledger, repo) -> AccionPropuesta:
    if accion.estado != EstadoAccion.pendiente_aprobacion:
        raise AccionNoPendiente(f"{accion.accion_id} está en {accion.estado}")
    nueva = accion.model_copy(update={"estado": destino, "aprobada_por": humano, "aprobada_en": datetime.now(timezone.utc)})
    ledger.append(tenant_id=nueva.tenant_id, viaje_id=nueva.viaje_id, tipo_evento=f"accion_{destino}", actor=humano,
                  payload={"accion_id": nueva.accion_id, "bloqueo_id": nueva.bloqueo_id, "tipo": nueva.tipo})
    repo.guardar("acciones", nueva.accion_id, nueva)
    return nueva


def aprobar(accion: AccionPropuesta, humano: str, *, ledger, repo) -> AccionPropuesta:
    return _resolver(accion, EstadoAccion.aprobada, humano, ledger=ledger, repo=repo)


def rechazar(accion: AccionPropuesta, humano: str, *, ledger, repo) -> AccionPropuesta:
    return _resolver(accion, EstadoAccion.rechazada, humano, ledger=ledger, repo=repo)


def cola_de_aprobacion(repo, tenant_id: str) -> list[AccionPropuesta]:
    return repo.listar("acciones", AccionPropuesta, tenant_id=tenant_id, estado=EstadoAccion.pendiente_aprobacion)
