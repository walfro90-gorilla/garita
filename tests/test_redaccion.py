from tools.gemma_redact import RedactorFijo, RedactorPatron

TEXTO = "NOMBRE: Operador Sintetico Uno CURP: TEST900101HCHRST01 RFC: XAXX010101000 RFC2: XAXX010101000 PLACA: TEST001"


def test_redactor_patron_tokeniza_y_conserva_mapa():
    r = RedactorPatron(RedactorFijo({b"x": TEXTO})).redactar(b"x", "text/plain", ("OPERADOR SINTETICO UNO",))
    assert r.texto_redactado == "NOMBRE: [NOMBRE_1] CURP: [CURP_1] RFC: [RFC_1] RFC2: [RFC_1] PLACA: TEST001"
    assert r.mapa_tokens == {"[CURP_1]": "TEST900101HCHRST01", "[RFC_1]": "XAXX010101000",
                             "[NOMBRE_1]": "Operador Sintetico Uno"}


def test_domicilio_etiquetado_se_redacta():
    r = RedactorPatron(RedactorFijo({b"x": "FOLIO: TEST-1\nDOMICILIO: CALLE SINTETICA 123 CD JUAREZ CHIH\nFIN"})).redactar(b"x", "text/plain")
    assert r.texto_redactado == "FOLIO: TEST-1\nDOMICILIO: [DOMICILIO_1]\nFIN"
    assert r.mapa_tokens == {"[DOMICILIO_1]": "CALLE SINTETICA 123 CD JUAREZ CHIH"}
