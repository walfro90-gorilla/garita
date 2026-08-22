"""Modelos Pydantic del dominio. Formas obligatorias en CLAUDE.md <data_models>.

Todo modelo persistido lleva `tenant_id`. Se transporta; no se aplica aislamiento.
Los campos que mapean 1:1 al XSD del SAT conservan el nombre del SAT.
"""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from dominio.enums import (
    EstadoAccion,
    EstadoHallazgo,
    EstadoHandoff,
    EstadoViaje,
    EstadoVigencia,
    MotivoBloqueo,
    TipoAccion,
    TipoDocumento,
)

UMBRAL_CONFIANZA = 0.85


class _Modelo(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DocumentoVigencia(_Modelo):
    documento_id: str
    tenant_id: str
    tipo: TipoDocumento
    folio: str | None
    fecha_emision: date | None
    fecha_vencimiento: date | None
    estado: EstadoVigencia
    fuente_uri: str
    confianza_extraccion: float = Field(ge=0.0, le=1.0)
    requiere_revision_humana: bool
    hash_documento: str

    @model_validator(mode="after")
    def _sabe_lo_que_no_sabe(self) -> "DocumentoVigencia":
        """Nunca se inventa una fecha. Si falta un campo crítico o la confianza es
        baja, la revisión humana es obligatoria aunque el extractor diga lo contrario."""
        con_fecha = (EstadoVigencia.vigente, EstadoVigencia.por_vencer, EstadoVigencia.vencido)
        if self.estado in con_fecha and self.fecha_vencimiento is None:
            raise ValueError(f"estado={self.estado} exige fecha_vencimiento")
        critico_ausente = self.fecha_vencimiento is None
        if self.confianza_extraccion < UMBRAL_CONFIANZA or critico_ausente:
            self.requiere_revision_humana = True
        return self


class Operador(_Modelo):
    operador_id: str
    tenant_id: str
    nombre: str  # PII
    curp: str | None  # PII
    licencia_federal: DocumentoVigencia  # tipo E
    visa_fast: DocumentoVigencia | None


class Activo(_Modelo):
    activo_id: str
    tenant_id: str
    tipo: Literal["tractor", "caja", "dolly"]
    placa: str
    numero_economico: str
    config_autotransporte: str | None  # c_ConfigAutotransporte, solo tractor
    tarjeta_circulacion: DocumentoVigencia
    verificacion_fisico_mecanica: DocumentoVigencia
    poliza_responsabilidad_civil: DocumentoVigencia

    @model_validator(mode="after")
    def _config_solo_tractor(self) -> "Activo":
        if self.tipo != "tractor" and self.config_autotransporte is not None:
            raise ValueError("config_autotransporte solo aplica a tractor")
        return self


class Mercancia(_Modelo):
    clave_prod_serv_cp: str  # c_ClaveProdServCP
    descripcion: str
    cantidad: float = Field(gt=0)
    clave_unidad: str  # c_ClaveUnidad
    peso_en_kg: float = Field(gt=0)
    fraccion_arancelaria: str | None  # c_FraccionArancelaria, obligatoria si transp_internac
    valor_mercancia: float | None = None
    moneda: str | None = None


class Bloqueo(_Modelo):
    bloqueo_id: str
    motivo: MotivoBloqueo
    severidad: Literal["duro", "blando"]
    explicacion: str  # legible por el coordinador de tráfico
    documento_id: str | None
    evidencia_uri: str
    accion_propuesta_id: str | None
    detectado_por: str  # nombre del agente
    detectado_en: datetime
    resuelto_por_accion_id: str | None = None

    @property
    def abierto(self) -> bool:
        return self.resuelto_por_accion_id is None


class AccionPropuesta(_Modelo):
    """Lo único que un agente puede hacer hacia afuera: proponer. Un humano aprueba."""

    accion_id: str
    tenant_id: str
    viaje_id: str
    bloqueo_id: str | None
    tipo: TipoAccion
    descripcion: str
    estado: EstadoAccion = EstadoAccion.pendiente_aprobacion
    propuesta_por: str  # nombre del agente
    propuesta_en: datetime
    aprobada_por: str | None = None  # humano
    aprobada_en: datetime | None = None

    @model_validator(mode="after")
    def _aprobada_por_humano(self) -> "AccionPropuesta":
        if self.estado in (EstadoAccion.aprobada, EstadoAccion.ejecutada) and not self.aprobada_por:
            raise ValueError("una acción aprobada requiere aprobada_por (humano)")
        return self


class Viaje(_Modelo):
    viaje_id: str
    tenant_id: str
    estado: EstadoViaje = EstadoViaje.borrador
    tractor_id: str
    caja_ids: list[str]
    operador_id: str
    transp_internac: bool
    entrada_salida_merc: Literal["Entrada", "Salida"] | None
    pais_origen_destino: str | None  # != "MEX" si transp_internac
    via_entrada_salida: str | None
    regimenes_aduaneros: list[str] = Field(default_factory=list, max_length=10)
    mercancias: list[Mercancia] = Field(default_factory=list)
    bloqueos: list[Bloqueo] = Field(default_factory=list)

    @model_validator(mode="after")
    def _coherencia_internacional(self) -> "Viaje":
        if self.transp_internac:
            faltan = [
                n
                for n in ("entrada_salida_merc", "pais_origen_destino", "via_entrada_salida")
                if getattr(self, n) is None
            ]
            if faltan:
                raise ValueError(f"transp_internac exige {faltan}")
            if self.pais_origen_destino == "MEX":
                raise ValueError("pais_origen_destino no puede ser MEX en transporte internacional")
        return self

    def bloqueos_duros_abiertos(self) -> list[Bloqueo]:
        return [b for b in self.bloqueos if b.severidad == "duro" and b.abierto]


class HallazgoCTPAT(_Modelo):
    hallazgo_id: str
    tenant_id: str
    criterio_msc: str  # p. ej. "MSC 5.1"
    descripcion: str
    estado: EstadoHallazgo
    evidencia_uri: str | None
    documento_id: str | None
    detectado_por: str
    detectado_en: datetime


class HandoffResult(_Modelo):
    """Resultado del contrato de handoff entre agentes (CLAUDE.md <failure_tolerance>)."""

    agente: str
    paso_id: str
    estado: EstadoHandoff
    intentos: int = Field(ge=0)  # 0 = no llegó a llamar al modelo (p. ej. fuga de PII detenida)
    payload: dict[str, Any] | None = None
    error_validacion: str | None = None


class EntradaLedger(_Modelo):
    """Solo la construye LedgerService.append(). Inmutable."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    secuencia: int = Field(ge=0)
    tenant_id: str
    viaje_id: str
    tipo_evento: str
    actor: str
    payload: dict[str, Any]
    registrado_en: datetime
    hash_anterior: str
    hash: str
    firma: str  # hex
    firmado_por: str  # key_id del firmador
    idempotency_key: str | None = None  # reejecutar el mismo paso no duplica la entrada
