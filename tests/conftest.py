"""Fábricas de datos sintéticos. Prefijos obligatorios: XAXX (RFC), TEST- (placas, folios)."""

from datetime import date, datetime, timezone

import pytest

from dominio.enums import EstadoVigencia, MotivoBloqueo, TipoDocumento
from dominio.modelos import Bloqueo, DocumentoVigencia, Viaje

TENANT = "tenant-cafe57-sintetico"


def documento(**cambios) -> DocumentoVigencia:
    base = dict(
        documento_id="doc-1",
        tenant_id=TENANT,
        tipo=TipoDocumento.licencia_federal,
        folio="TEST-LIC-0001",
        fecha_emision=date(2025, 1, 10),
        fecha_vencimiento=date(2027, 1, 10),
        estado=EstadoVigencia.vigente,
        fuente_uri="gs://garita-sintetico/doc-1.jpg",
        confianza_extraccion=0.97,
        requiere_revision_humana=False,
        hash_documento="a" * 64,
    )
    return DocumentoVigencia(**(base | cambios))


def bloqueo(**cambios) -> Bloqueo:
    base = dict(
        bloqueo_id="blq-1",
        motivo=MotivoBloqueo.documento_vencido,
        severidad="duro",
        explicacion="Verificación físico-mecánica del tractor TEST-001 vencida el 2026-07-01.",
        documento_id="doc-verif-1",
        evidencia_uri="gs://garita-sintetico/verif-1.pdf",
        accion_propuesta_id=None,
        detectado_por="cumplimiento",
        detectado_en=datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc),
    )
    return Bloqueo(**(base | cambios))


def viaje(**cambios) -> Viaje:
    base = dict(
        viaje_id="viaje-1",
        tenant_id=TENANT,
        tractor_id="tractor-1",
        caja_ids=["caja-1"],
        operador_id="operador-1",
        transp_internac=True,
        entrada_salida_merc="Salida",
        pais_origen_destino="USA",
        via_entrada_salida="01",
        regimenes_aduaneros=["EXD"],
    )
    return Viaje(**(base | cambios))


@pytest.fixture
def tenant() -> str:
    return TENANT
