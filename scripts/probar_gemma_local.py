"""Prueba REAL de la capa 1 de ADR-009 con Gemma en Ollama local (CPU).

No es test de pytest: tarda minutos y necesita `ollama pull gemma3:4b`.
Imprime, por documento, la transcripción redactada por Gemma + RedactorPatron,
el mapa de tokens (se queda aquí, en la "zona MX") y si la frontera lo deja pasar.

Uso: .venv/bin/python scripts/probar_gemma_local.py [url_ollama] [modelo]
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from infra.frontera import FugaPII, afirmar_sin_pii  # noqa: E402
from tools.gemma_redact import RedactorGemma, RedactorPatron  # noqa: E402

CORPUS = Path(__file__).resolve().parents[1] / "fixtures" / "corpus"
url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:11434"
modelo = sys.argv[2] if len(sys.argv) > 2 else "gemma3:4b"
manifiesto = json.loads((CORPUS / "manifiesto.json").read_text(encoding="utf-8"))
redactor = RedactorPatron(RedactorGemma(url, modelo))
nombres = tuple(manifiesto["operadores_conocidos"])

for doc in manifiesto["documentos"]:
    if doc["archivo"].endswith(".pdf"):
        continue  # extracción de texto de PDF: F3
    t = time.time()
    r = redactor.redactar((CORPUS / doc["archivo"]).read_bytes(), "image/jpeg", nombres)
    seg = round(time.time() - t, 1)
    try:
        afirmar_sin_pii(r.texto_redactado, tuple(r.mapa_tokens.values()), documento_id=doc["documento_id"])
        frontera = "PASA"
    except FugaPII as e:
        frontera = f"DETENIDO: {e}"
    fugas = [p for p in doc["pii"] if p.upper() in r.texto_redactado.upper()]
    print(f"\n===== {doc['archivo']} · {seg}s · frontera={frontera} · PII que cruzó={fugas or 'ninguna'}")
    print(r.texto_redactado.strip())
    print("--- mapa_tokens (se queda en MX):", r.mapa_tokens)
