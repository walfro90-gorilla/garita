"""Tool `proponer_accion`: Bloqueo → AccionPropuesta en pending_approval. Scope: seguimiento.

Idempotente: el id de la acción deriva del bloqueo; si ya existe, se devuelve la
existente sin tocarla (aunque un humano ya la haya aprobado). El agente nunca
ejecuta el efecto; solo lo deja en la cola de aprobación.
"""

from datetime import date, datetime, time, timezone

from dominio.enums import MotivoBloqueo, TipoAccion
from dominio.modelos import AccionPropuesta, Bloqueo

AGENTE = "seguimiento"

TIPO_POR_MOTIVO = {
    MotivoBloqueo.documento_vencido: TipoAccion.renovar_documento,
    MotivoBloqueo.documento_no_localizado: TipoAccion.solicitar_documento,
    MotivoBloqueo.documento_ilegible: TipoAccion.solicitar_documento,
    MotivoBloqueo.revision_humana_pendiente: TipoAccion.corregir_dato,
    MotivoBloqueo.xsd_invalido: TipoAccion.corregir_dato,
    MotivoBloqueo.catalogo_invalido: TipoAccion.corregir_dato,
    MotivoBloqueo.dato_inconsistente: TipoAccion.corregir_dato,
    MotivoBloqueo.verificacion_fallida: TipoAccion.notificar,
}


def proponer_accion(repo, *, bloqueo: Bloqueo, tenant_id: str, viaje_id: str, hoy: date) -> AccionPropuesta:
    accion_id = f"acc-{bloqueo.bloqueo_id}"
    existente = repo.obtener("acciones", accion_id, AccionPropuesta)
    if existente is not None:
        return existente
    tipo = TIPO_POR_MOTIVO[bloqueo.motivo]
    accion = AccionPropuesta(
        accion_id=accion_id, tenant_id=tenant_id, viaje_id=viaje_id, bloqueo_id=bloqueo.bloqueo_id, tipo=tipo,
        descripcion=f"{tipo.replace('_', ' ').capitalize()}: {bloqueo.explicacion} Evidencia: {bloqueo.evidencia_uri}",
        propuesta_por=AGENTE, propuesta_en=datetime.combine(hoy, time.min, tzinfo=timezone.utc),
    )
    repo.guardar("acciones", accion_id, accion)
    return accion
