from pathlib import Path

from tools.xsd_validate import xsd_validate

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "carta_porte_31_sintetica.xml"


def test_carta_porte_sintetica_es_valida():
    assert xsd_validate(FIXTURE.read_bytes()) == []


def test_clave_fuera_de_catalogo_es_invalida():
    xml = FIXTURE.read_bytes().replace(b'BienesTransp="10101500"', b'BienesTransp="00000000"')
    errores = xsd_validate(xml)
    assert errores and "BienesTransp" in errores[0]


def test_atributo_obligatorio_ausente_es_invalido():
    xml = FIXTURE.read_bytes().replace(b' PermSCT="TPAF01"', b"")
    assert any("PermSCT" in e for e in xsd_validate(xml))


def test_xml_mal_formado_no_revienta():
    errores = xsd_validate(b"<CartaPorte")
    assert len(errores) == 1 and errores[0].startswith("XML mal formado: ")
