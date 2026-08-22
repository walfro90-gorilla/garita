"""Tool `vigencias_query`: estado rodante de vigencias por activo y operador. Scope: cumplimiento.

Determinista. Lee el expediente (Activo, Operador) del repositorio y convierte
cada DocumentoVigencia en un Bloqueo: vencido / no localizado / ilegible =
duro; por vencer o con revisión humana pendiente = blando. Ids deterministas.
"""

from datetime import date, datetime, time, timezone

from dominio.enums import EstadoVigencia, MotivoBloqueo
from dominio.modelos import Activo, Bloqueo, DocumentoVigencia, Operador
from dominio.vigencias import estado_vigencia

AGENTE = "cumplimiento"

DUROS = {
    EstadoVigencia.vencido: MotivoBloqueo.documento_vencido,
    EstadoVigencia.no_localizado: MotivoBloqueo.documento_no_localizado,
    EstadoVigencia.ilegible: MotivoBloqueo.documento_ilegible,
}


def _bloqueos_de(doc: DocumentoVigencia, dueño: str, viaje_id: str, hoy: date) -> list[Bloqueo]:
    estado = estado_vigencia(doc.fecha_vencimiento, hoy, localizado=doc.estado != EstadoVigencia.no_localizado)
    cuando = datetime.combine(hoy, time.min, tzinfo=timezone.utc)
    out: list[Bloqueo] = []

    def b(motivo: MotivoBloqueo, severidad: str, explicacion: str) -> Bloqueo:
        return Bloqueo(bloqueo_id=f"blq-{viaje_id}-{motivo}-{doc.documento_id}", motivo=motivo, severidad=severidad,
                       explicacion=explicacion, documento_id=doc.documento_id, evidencia_uri=doc.fuente_uri,
                       accion_propuesta_id=None, detectado_por=AGENTE, detectado_en=cuando)

    if estado in DUROS:
        detalle = f"venció el {doc.fecha_vencimiento}" if estado == EstadoVigencia.vencido else estado.replace("_", " ")
        out.append(b(DUROS[estado], "duro", f"{doc.tipo.replace('_', ' ')} de {dueño}: {detalle}."))
    elif estado == EstadoVigencia.por_vencer:
        out.append(b(MotivoBloqueo.documento_vencido, "blando",
                     f"{doc.tipo.replace('_', ' ')} de {dueño} vence el {doc.fecha_vencimiento} ({(doc.fecha_vencimiento - hoy).days} días)."))
    if doc.requiere_revision_humana and estado not in DUROS:
        out.append(b(MotivoBloqueo.revision_humana_pendiente, "blando",
                     f"{doc.tipo.replace('_', ' ')} de {dueño}: extracción con confianza {doc.confianza_extraccion:.2f}; revisar a mano."))
    return out


def vigencias_query(repo, *, tenant_id: str, viaje_id: str, activo_ids: list[str], operador_id: str, hoy: date) -> list[Bloqueo]:
    out: list[Bloqueo] = []
    for activo_id in activo_ids:
        activo = repo.obtener("activos", activo_id, Activo)
        if activo is None:
            continue  # la existencia la verifica cross_check
        for doc in (activo.tarjeta_circulacion, activo.verificacion_fisico_mecanica, activo.poliza_responsabilidad_civil):
            out.extend(_bloqueos_de(doc, f"{activo.tipo} {activo.placa}", viaje_id, hoy))
    operador = repo.obtener("operadores", operador_id, Operador)
    if operador is not None:
        docs = [operador.licencia_federal] + ([operador.visa_fast] if operador.visa_fast else [])
        for doc in docs:
            out.extend(_bloqueos_de(doc, f"operador {operador.operador_id}", viaje_id, hoy))
    return out
