from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from conftest import documento, viaje
from dominio.enums import EstadoAccion, EstadoVigencia, TipoAccion
from dominio.modelos import AccionPropuesta, Activo


def test_confianza_baja_fuerza_revision_humana():
    d = documento(confianza_extraccion=0.6, requiere_revision_humana=False)
    assert d.requiere_revision_humana is True


def test_fecha_ilegible_fuerza_revision_humana_y_no_se_inventa():
    d = documento(estado=EstadoVigencia.ilegible, fecha_vencimiento=None, requiere_revision_humana=False)
    assert d.fecha_vencimiento is None
    assert d.requiere_revision_humana is True


def test_vigente_sin_fecha_es_invalido():
    with pytest.raises(ValidationError):
        documento(estado=EstadoVigencia.vigente, fecha_vencimiento=None)


def test_internacional_exige_pais_distinto_de_mex():
    with pytest.raises(ValidationError):
        viaje(pais_origen_destino="MEX")
    with pytest.raises(ValidationError):
        viaje(entrada_salida_merc=None)


def test_maximo_diez_regimenes():
    with pytest.raises(ValidationError):
        viaje(regimenes_aduaneros=[f"R{i}" for i in range(11)])


def test_config_autotransporte_solo_en_tractor():
    campos = dict(
        activo_id="caja-1", tenant_id="t", placa="TEST-CAJA-01", numero_economico="C-01",
        tarjeta_circulacion=documento(), verificacion_fisico_mecanica=documento(),
        poliza_responsabilidad_civil=documento(),
    )
    with pytest.raises(ValidationError):
        Activo(tipo="caja", config_autotransporte="C2", **campos)
    assert Activo(tipo="caja", config_autotransporte=None, **campos).tipo == "caja"


def test_accion_aprobada_exige_humano():
    base = dict(
        accion_id="acc-1", tenant_id="t", viaje_id="viaje-1", bloqueo_id="blq-1",
        tipo=TipoAccion.renovar_documento, descripcion="Agendar verificación",
        propuesta_por="seguimiento", propuesta_en=datetime.now(timezone.utc),
    )
    with pytest.raises(ValidationError):
        AccionPropuesta(estado=EstadoAccion.aprobada, **base)
    ok = AccionPropuesta(estado=EstadoAccion.aprobada, aprobada_por="coordinador-trafico", **base)
    assert ok.aprobada_por == "coordinador-trafico"


def test_modelos_rechazan_campos_desconocidos():
    with pytest.raises(ValidationError):
        viaje(campo_inventado=1)
