"""AC F2 (local): los 5 documentos del corpus → DocumentoVigencia válido; la
verificación vencida queda marcada; la traza demuestra que nada con PII cruzó;
handoff inválido → reintento → dead-letter."""

import json
import logging
import re
import secrets
from datetime import date
from functools import partial
from pathlib import Path

import pytest

from agentes.ingesta.pipeline import MapaRedaccion, ingerir
from dominio.enums import EstadoHandoff, EstadoVigencia, TipoDocumento
from dominio.modelos import DocumentoVigencia
from infra.frontera import PATRONES_PII
from infra.ledger import FirmadorLocalHmac, LedgerService
from infra.repository import InMemoryRepository
from tools.firestore_write import firestore_write
from tools.gemma_redact import RedactorFijo, RedactorPatron
from tools.registry import ToolRegistry
from tools.storage_read import storage_read

CORPUS = Path(__file__).resolve().parents[1] / "fixtures" / "corpus"
MANIFIESTO = json.loads((CORPUS / "manifiesto.json").read_text(encoding="utf-8"))
HOY = date.fromisoformat(MANIFIESTO["hoy"])


class ExtractorSimulado:
    """Sustituye a Gemini: extrae folio y vigencia de la transcripción redactada con regex.
    `fallos` hace que las primeras N respuestas sean JSON inválido (prueba de caos)."""

    def __init__(self, fallos: int = 0) -> None:
        self.fallos, self.llamadas, self.textos_recibidos = fallos, 0, []

    def __call__(self, texto: str, tipo: TipoDocumento, error_previo: str | None) -> str:
        self.llamadas += 1
        self.textos_recibidos.append(texto)
        if self.llamadas <= self.fallos:
            return json.dumps({"tipo": "documento_misterioso", "confianza": 7})
        vig = re.search(r"VIGENCIA(?: HASTA)?:\s*(\S+)", texto)
        folio = re.search(r"(?:No\. LICENCIA|FOLIO|NUMERO DE PERMISO|NUMERO DE POLIZA|SELLO ISO 17712):\s*(\S+)", texto)
        fecha = vig.group(1) if vig and vig.group(1) != "[ILEGIBLE]" else None
        if tipo == TipoDocumento.inspeccion_17_puntos:
            fecha = (date.fromisoformat(re.search(r"FECHA:\s*(\S+)", texto).group(1)).toordinal() + 1)
            fecha = date.fromordinal(fecha).isoformat()
        return json.dumps({"tipo": tipo, "folio": folio.group(1) if folio else None, "fecha_emision": None,
                           "fecha_vencimiento": fecha, "confianza": 0.95 if fecha else 0.4,
                           "observaciones": "simulado"})


def _registro(repo, extractor) -> ToolRegistry:
    transcripciones = {(CORPUS / d["archivo"]).read_bytes(): d["transcripcion"] for d in MANIFIESTO["documentos"]}
    r = ToolRegistry()
    r.registrar("storage_read", storage_read)
    r.registrar("gemma_redact", RedactorPatron(RedactorFijo(transcripciones)).redactar)
    r.registrar("gemini_extract", extractor)
    r.registrar("firestore_write", partial(firestore_write, repo))
    return r


def _ingerir(doc, repo, extractor, ledger=None):
    ledger = ledger or LedgerService(FirmadorLocalHmac(secrets.token_bytes(32)))
    mime = "application/pdf" if doc["archivo"].endswith(".pdf") else "image/jpeg"
    return ingerir(documento_id=doc["documento_id"], tenant_id=MANIFIESTO["tenant_id"],
                   fuente_uri=str(CORPUS / doc["archivo"]), mime=mime, tipo_sugerido=TipoDocumento(doc["tipo"]),
                   registro=_registro(repo, extractor), ledger=ledger, hoy=HOY,
                   nombres_conocidos=tuple(MANIFIESTO["operadores_conocidos"]))


@pytest.mark.parametrize("doc", MANIFIESTO["documentos"], ids=[d["documento_id"] for d in MANIFIESTO["documentos"]])
def test_documento_del_corpus_llega_a_esquema_valido(doc, caplog):
    repo, extractor = InMemoryRepository(), ExtractorSimulado()
    with caplog.at_level(logging.INFO, logger="garita.frontera"):
        resultado = _ingerir(doc, repo, extractor)
    assert resultado.estado == EstadoHandoff.ok
    guardado = repo.obtener("documentos", doc["documento_id"], DocumentoVigencia)
    esperado = doc["esperado"]
    assert guardado.folio == esperado["folio"]
    assert guardado.estado == EstadoVigencia(esperado["estado"])
    assert (guardado.fecha_vencimiento.isoformat() if guardado.fecha_vencimiento else None) == esperado["fecha_vencimiento"]
    assert guardado.requiere_revision_humana is esperado["requiere_revision_humana"]
    assert guardado.hash_documento == __import__("hashlib").sha256((CORPUS / doc["archivo"]).read_bytes()).hexdigest()

    # Traza de la frontera: lo que recibió "Gemini" no contiene PII ni por valor ni por patrón.
    assert any("frontera.ok" in m for m in caplog.messages)
    for texto in extractor.textos_recibidos:
        for valor in doc["pii"]:
            assert valor.upper() not in texto.upper(), f"PII cruzó la frontera: {valor}"
        for patron in PATRONES_PII.values():
            assert not patron.search(texto)
    mapa = repo.obtener("mapas_redaccion", doc["documento_id"], MapaRedaccion).mapa_tokens
    assert set(mapa.values()) >= set(doc["pii"])


def test_verificacion_vencida_queda_marcada():
    repo = InMemoryRepository()
    doc = next(d for d in MANIFIESTO["documentos"] if d["tipo"] == "verificacion_fisico_mecanica")
    _ingerir(doc, repo, ExtractorSimulado())
    assert repo.obtener("documentos", doc["documento_id"], DocumentoVigencia).estado == EstadoVigencia.vencido


def test_fecha_ilegible_no_se_inventa_y_pide_humano():
    repo = InMemoryRepository()
    doc = next(d for d in MANIFIESTO["documentos"] if d["tipo"] == "licencia_federal")
    _ingerir(doc, repo, ExtractorSimulado())
    g = repo.obtener("documentos", doc["documento_id"], DocumentoVigencia)
    assert g.fecha_vencimiento is None and g.estado == EstadoVigencia.ilegible and g.requiere_revision_humana


def test_handoff_invalido_reintenta_con_el_error_y_luego_dead_letter():
    repo, doc = InMemoryRepository(), MANIFIESTO["documentos"][2]
    ledger = LedgerService(FirmadorLocalHmac(secrets.token_bytes(32)))

    dos_fallos = ExtractorSimulado(fallos=2)
    r = _ingerir(doc, repo, dos_fallos, ledger)
    assert r.estado == EstadoHandoff.ok and r.intentos == 3

    siempre_falla = ExtractorSimulado(fallos=99)
    r = _ingerir(doc, InMemoryRepository(), siempre_falla, ledger)
    assert r.estado == EstadoHandoff.dead_letter and r.intentos == 3 and siempre_falla.llamadas == 3
    assert "documento_misterioso" in r.error_validacion or "tipo" in r.error_validacion
    assert ledger.entradas[-1].tipo_evento == "dead_letter"
    assert ledger.verify()


def test_fuga_de_pii_detiene_la_ingesta():
    """Si la redacción falla (un transcriptor que devuelve PII y un redactor sin patrones), la frontera corta."""
    from tools.gemma_redact import Redaccion

    repo, doc = InMemoryRepository(), MANIFIESTO["documentos"][0]
    extractor = ExtractorSimulado()
    registro = _registro(repo, extractor)
    registro.registrar("gemma_redact", lambda c, m, n: Redaccion(texto_redactado=doc["transcripcion"], mapa_tokens={}))
    ledger = LedgerService(FirmadorLocalHmac(secrets.token_bytes(32)))
    r = ingerir(documento_id="x", tenant_id="t", fuente_uri=str(CORPUS / doc["archivo"]), mime="image/jpeg",
                tipo_sugerido=TipoDocumento.licencia_federal, registro=registro, ledger=ledger, hoy=HOY)
    assert r.estado == EstadoHandoff.dead_letter and extractor.llamadas == 0
    assert ledger.entradas[-1].tipo_evento == "fuga_pii_detenida"
