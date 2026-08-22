"""Fábricas de datos sintéticos. Prefijos obligatorios: XAXX (RFC), TEST- (placas, folios)."""

from datetime import datetime, timezone

import pytest

from dominio.enums import MotivoBloqueo
from dominio.modelos import Bloqueo
from dominio.sintetico import TENANT, documento, viaje  # noqa: F401 — reexportadas para los tests


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


@pytest.fixture
def tenant() -> str:
    return TENANT
