"""Enumeraciones del dominio. Valores en snake_case; se persisten como texto."""

from enum import StrEnum


class TipoDocumento(StrEnum):
    licencia_federal = "licencia_federal"
    visa_fast = "visa_fast"
    tarjeta_circulacion = "tarjeta_circulacion"
    verificacion_fisico_mecanica = "verificacion_fisico_mecanica"
    poliza_responsabilidad_civil = "poliza_responsabilidad_civil"
    permiso_sict = "permiso_sict"
    inspeccion_17_puntos = "inspeccion_17_puntos"


class EstadoVigencia(StrEnum):
    vigente = "vigente"
    por_vencer = "por_vencer"
    vencido = "vencido"
    no_localizado = "no_localizado"
    ilegible = "ilegible"


class EstadoViaje(StrEnum):
    borrador = "borrador"
    validando = "validando"
    bloqueado = "bloqueado"
    listo = "listo"
    en_ruta = "en_ruta"
    cerrado = "cerrado"
    cancelado = "cancelado"


class MotivoBloqueo(StrEnum):
    documento_vencido = "documento_vencido"
    documento_no_localizado = "documento_no_localizado"
    documento_ilegible = "documento_ilegible"
    xsd_invalido = "xsd_invalido"
    catalogo_invalido = "catalogo_invalido"
    dato_inconsistente = "dato_inconsistente"
    revision_humana_pendiente = "revision_humana_pendiente"


class TipoAccion(StrEnum):
    renovar_documento = "renovar_documento"
    solicitar_documento = "solicitar_documento"
    corregir_dato = "corregir_dato"
    notificar = "notificar"
    agendar = "agendar"


class EstadoAccion(StrEnum):
    pendiente_aprobacion = "pendiente_aprobacion"
    aprobada = "aprobada"
    rechazada = "rechazada"
    ejecutada = "ejecutada"


class EstadoHandoff(StrEnum):
    ok = "ok"
    reintento = "reintento"
    dead_letter = "dead_letter"
    failed_budget_exceeded = "failed_budget_exceeded"


class EstadoHallazgo(StrEnum):
    cumple = "cumple"
    parcial = "parcial"
    no_cumple = "no_cumple"
