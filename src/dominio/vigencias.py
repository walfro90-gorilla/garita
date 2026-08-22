"""Estado de vigencia: regla determinista, sin LLM."""

from datetime import date, timedelta

from dominio.enums import EstadoVigencia

VENTANA_POR_VENCER = timedelta(days=30)


def estado_vigencia(fecha_vencimiento: date | None, hoy: date, *, localizado: bool = True) -> EstadoVigencia:
    """None + localizado ⇒ ilegible (el documento existe pero la fecha no se lee).
    None + no localizado ⇒ no_localizado. Nunca se inventa una fecha."""
    if fecha_vencimiento is None:
        return EstadoVigencia.ilegible if localizado else EstadoVigencia.no_localizado
    if fecha_vencimiento < hoy:
        return EstadoVigencia.vencido
    if fecha_vencimiento - hoy <= VENTANA_POR_VENCER:
        return EstadoVigencia.por_vencer
    return EstadoVigencia.vigente
