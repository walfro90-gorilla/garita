import re

import pytest

from dominio.modelos import Activo, Operador, Transportista, Viaje
from dominio.sintetico import TENANT, sembrar_expediente
from infra.pac_mock import PacMock, TimbradoRechazado
from infra.repository import InMemoryRepository
from tools.carta_porte import CartaPorteIncompleta, construir_carta_porte, id_ccp
from tools.xsd_validate import xsd_validate


@pytest.fixture
def exp():
    repo = InMemoryRepository()
    sembrar_expediente(repo)
    return dict(viaje=repo.obtener("viajes", "viaje-1", Viaje), tractor=repo.obtener("activos", "tractor-1", Activo),
                cajas=[repo.obtener("activos", "caja-1", Activo)], operador=repo.obtener("operadores", "operador-1", Operador),
                transportista=repo.obtener("transportistas", TENANT, Transportista))


def test_carta_porte_construida_valida_contra_xsd_oficial(exp):
    xml = construir_carta_porte(**exp)
    assert xsd_validate(xml) == []
    assert b'TranspInternac="S\xc3\xad"' in xml and b'FraccionArancelaria="01011001"' in xml
    assert b'PermSCT="TPAF01"' in xml and b'SubTipoRem="CTR004"' in xml and b'NumLicencia="TEST-LIC-0001"' in xml
    assert b'TotalDistRec="350.00"' in xml and b'PesoBrutoTotal="1200.000"' in xml


def test_id_ccp_determinista_con_formato_sat():
    a, b = id_ccp("viaje-1"), id_ccp("viaje-1")
    assert a == b and re.fullmatch(r"CCC[0-9A-F]{5}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}", a)
    assert id_ccp("viaje-2") != a


def test_faltantes_se_reportan_todos_sin_emitir_xml(exp):
    exp["tractor"] = exp["tractor"].model_copy(update={"anio_modelo": None, "peso_bruto_vehicular": None})
    exp["cajas"][0] = exp["cajas"][0].model_copy(update={"sub_tipo_rem": None})
    with pytest.raises(CartaPorteIncompleta) as e:
        construir_carta_porte(**exp)
    assert len(e.value.faltantes) == 3 and any("anio_modelo" in f for f in e.value.faltantes)


def test_nacional_sin_fraccion_es_valida(exp):
    exp["viaje"] = exp["viaje"].model_copy(update={"transp_internac": False, "entrada_salida_merc": None,
                                                   "pais_origen_destino": None, "via_entrada_salida": None, "regimenes_aduaneros": []})
    exp["viaje"].mercancias[0].fraccion_arancelaria = None
    xml = construir_carta_porte(**exp)
    assert xsd_validate(xml) == [] and b'TranspInternac="No"' in xml and b"RegimenesAduaneros" not in xml


def test_pac_mock_timbra_valido_y_rechaza_invalido(exp):
    xml = construir_carta_porte(**exp)
    t1, t2 = PacMock().timbrar(xml), PacMock().timbrar(xml)
    assert t1.uuid == t2.uuid and t1.uuid.startswith("TEST-") and t1.no_certificado_sat.startswith("TEST-")
    with pytest.raises(TimbradoRechazado):
        PacMock().timbrar(xml.replace(b'Version="3.1"', b'Version="3.0"'))
