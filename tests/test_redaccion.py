from tools.gemma_redact import RedactorFijo, RedactorPatron

TEXTO = "NOMBRE: Operador Sintetico Uno CURP: TEST900101HCHRST01 RFC: XAXX010101000 RFC2: XAXX010101000 PLACA: TEST001"


def test_redactor_patron_tokeniza_y_conserva_mapa():
    r = RedactorPatron(RedactorFijo({b"x": TEXTO})).redactar(b"x", "text/plain", ("OPERADOR SINTETICO UNO",))
    assert r.texto_redactado == "NOMBRE: [NOMBRE_1] CURP: [CURP_1] RFC: [RFC_1] RFC2: [RFC_1] PLACA: TEST001"
    assert r.mapa_tokens == {"[CURP_1]": "TEST900101HCHRST01", "[RFC_1]": "XAXX010101000",
                             "[NOMBRE_1]": "Operador Sintetico Uno"}


def test_valor_deformado_por_ocr_se_redacta_por_etiqueta():
    """Hallazgo real (Gemma 3 4B, 22 ago): transcribió la CURP sin una letra y dejó '[CURP]: valor'."""
    texto = "NOMBRE: OPERADOR NUEVO NO CONOCIDO\n[CURP]: TEST900101HCRST01\nNo. LICENCIA: TEST-LIC-0001\n[DOMICILIO]: CALLE X 1"
    r = RedactorPatron(RedactorFijo({b"x": texto})).redactar(b"x", "text/plain")
    assert r.texto_redactado == "NOMBRE: [NOMBRE_1]\nCURP: [CURP_1]\nNo. LICENCIA: TEST-LIC-0001\nDOMICILIO: [DOMICILIO_1]"
    assert r.mapa_tokens == {"[NOMBRE_1]": "OPERADOR NUEVO NO CONOCIDO", "[CURP_1]": "TEST900101HCRST01",
                             "[DOMICILIO_1]": "CALLE X 1"}


def test_frontera_rechaza_etiqueta_sin_token():
    import pytest

    from infra.frontera import FugaPII, afirmar_sin_pii

    with pytest.raises(FugaPII, match="CURP"):
        afirmar_sin_pii("CURP: TEST900101HCRST01", (), documento_id="d")
    afirmar_sin_pii("CURP: [CURP_1] NOMBRE: [NOMBRE_1] FOLIO: TEST-1", (), documento_id="d")


def test_domicilio_etiquetado_se_redacta():
    r = RedactorPatron(RedactorFijo({b"x": "FOLIO: TEST-1\nDOMICILIO: CALLE SINTETICA 123 CD JUAREZ CHIH\nFIN"})).redactar(b"x", "text/plain")
    assert r.texto_redactado == "FOLIO: TEST-1\nDOMICILIO: [DOMICILIO_1]\nFIN"
    assert r.mapa_tokens == {"[DOMICILIO_1]": "CALLE SINTETICA 123 CD JUAREZ CHIH"}
