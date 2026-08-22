"""La frontera de residencia (ADR-003, ADR-009): nada con PII cruza hacia Gemini.

`afirmar_sin_pii` es la última línea antes de la llamada a Vertex AI. Si falla,
la ingesta se detiene y se registra; nunca se "limpia y sigue".
"""

import logging
import re

log = logging.getLogger("garita.frontera")

PATRONES_PII: dict[str, re.Pattern[str]] = {
    "CURP": re.compile(r"\b[A-Z]{4}\d{6}[HM][A-Z]{5}[0-9A-Z]\d\b"),
    "RFC": re.compile(r"\b[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}\b"),
}


# Toda etiqueta de PII debe ir seguida de un token "[...]". Cubre valores deformados por OCR
# que ya no cumplen el patrón (p. ej. una CURP a la que le falta una letra).
ETIQUETA_SIN_TOKEN = re.compile(r"\[?\b(CURP|RFC|NOMBRE|DOMICILIO|DIRECCI[OÓ]N)\]?\s*:\s*(?!\[)\S", re.IGNORECASE)


class FugaPII(RuntimeError):
    pass


def afirmar_sin_pii(texto: str, valores_redactados: tuple[str, ...], *, documento_id: str) -> None:
    for nombre, patron in PATRONES_PII.items():
        if patron.search(texto):
            raise FugaPII(f"{documento_id}: patrón {nombre} presente en el payload hacia Gemini")
    if m := ETIQUETA_SIN_TOKEN.search(texto):
        raise FugaPII(f"{documento_id}: etiqueta {m.group(1).upper()} sin token en el payload hacia Gemini")
    for valor in valores_redactados:
        if valor and valor.upper() in texto.upper():
            raise FugaPII(f"{documento_id}: un valor del mapa de tokens reapareció en el payload")
    log.info(
        "frontera.ok documento_id=%s destino=vertex-ai tokens_redactados=%d bytes=%d",
        documento_id, len(valores_redactados), len(texto.encode()),
    )
