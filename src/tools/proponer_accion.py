"""Tool `proponer_accion`: Bloqueo → AccionPropuesta en pending_approval. Scope: seguimiento.

Idempotente: el id de la acción deriva del bloqueo; si ya existe pendiente o
aprobada, se devuelve sin tocarla. Si el humano la RECHAZÓ, se propone una nueva
(sufijo -2, -3…): rechazar no deja al viaje sin salida. El agente nunca ejecuta
el efecto; solo lo deja en la cola de aprobación.
"""

from datetime import date, datetime, time, timezone

from dominio.enums import EstadoAccion, MotivoBloqueo, TipoAccion
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
    base_id = f"acc-{bloqueo.bloqueo_id}"
    accion_id, n = base_id, 1
    while (existente := repo.obtener("acciones", accion_id, AccionPropuesta)) is not None:
        if existente.estado != EstadoAccion.rechazada:
            return existente
        n += 1
        accion_id = f"{base_id}-{n}"
    tipo = TIPO_POR_MOTIVO[bloqueo.motivo]
    accion = AccionPropuesta(
        accion_id=accion_id, tenant_id=tenant_id, viaje_id=viaje_id, bloqueo_id=bloqueo.bloqueo_id, tipo=tipo,
        descripcion=f"{tipo.replace('_', ' ').capitalize()}: {bloqueo.explicacion} Evidencia: {bloqueo.evidencia_uri}",
        propuesta_por=AGENTE, propuesta_en=datetime.combine(hoy, time.min, tzinfo=timezone.utc),
    )
    repo.guardar("acciones", accion_id, accion)
    return accion
