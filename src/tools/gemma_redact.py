"""Tool `gemma_redact`: documento (bytes) → transcripción YA REDACTADA + mapa de tokens.

Scope: ingesta. Corre en la zona de PII (Cloud Run, northamerica-south1).
Dos capas, siempre (ADR-009):
  1. Gemma (multimodal, CPU) transcribe y sustituye PII por tokens.
  2. `RedactorPatron` repasa el texto: CURP y RFC por regex, nombres por
     diccionario del expediente. La regex nunca falla un formato fijo.
En tests, la capa 1 es `RedactorFijo` (transcripciones del manifiesto).
El mapa token→valor nunca sale de la región: se guarda en Firestore MX.
"""

import json
import re
import urllib.request
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from infra.frontera import PATRONES_PII

# Etiquetas de PII en documentos oficiales. La OCR puede deformar el VALOR (una CURP sin una
# letra ya no cumple la regex), pero la ETIQUETA sobrevive: se redacta lo que sigue a la etiqueta.
# Gemma a veces deja "[CURP]: valor" — el corchete opcional lo cubre.
ETIQUETA_VALOR_CORTO = re.compile(r"\[?\b(CURP|RFC)\]?\s*:\s*(?!\[)(\S+)")
ETIQUETA_LINEA = re.compile(r"(?im)^\[?(NOMBRE|DOMICILIO|DIRECCI[OÓ]N)\]?\s*:\s*(?!\[)(.+?)\s*$")
NORMALIZA = {"DIRECCION": "DOMICILIO", "DIRECCIÓN": "DOMICILIO"}


class Redaccion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    texto_redactado: str
    mapa_tokens: dict[str, str]  # "[CURP_1]" → valor original. PII. No cruza la frontera.


class Transcriptor(Protocol):
    def transcribir(self, contenido: bytes, mime: str) -> str: ...


class RedactorFijo:
    """Tests y desarrollo sin Gemma: transcripción conocida por documento."""

    def __init__(self, transcripciones: dict[bytes, str]) -> None:
        self._t = transcripciones

    def transcribir(self, contenido: bytes, mime: str) -> str:
        return self._t[contenido]


class RedactorGemma:
    """Gemma vía API de Ollama (mismo contenedor en local y en Cloud Run).
    `url` p. ej. http://localhost:11434 o la URL .run.app del servicio en MX."""

    PROMPT = (
        "Transcribe literalmente todo el texto de este documento mexicano de autotransporte. "
        "Si una fecha o campo no se lee con claridad escribe [ILEGIBLE] en su lugar; nunca adivines. "
        "Sustituye nombres de personas por [NOMBRE], CURP por [CURP], RFC por [RFC] y domicilios por [DOMICILIO]. "
        "Responde solo con la transcripción."
    )

    def __init__(self, url: str, modelo: str = "gemma3:4b", timeout: float = 300) -> None:
        self._url, self._modelo, self._timeout = url.rstrip("/"), modelo, timeout

    def transcribir(self, contenido: bytes, mime: str) -> str:
        import base64

        cuerpo = {"model": self._modelo, "prompt": self.PROMPT, "stream": False, "options": {"temperature": 0}}
        if mime.startswith("image/"):
            cuerpo["images"] = [base64.b64encode(contenido).decode()]
        else:  # PDF/texto: Gemma recibe el texto tal cual (extracción de PDF: F3)
            cuerpo["prompt"] = self.PROMPT + "\n\nDOCUMENTO:\n" + contenido.decode("utf-8", "replace")
        req = urllib.request.Request(
            f"{self._url}/api/generate", data=json.dumps(cuerpo).encode(), headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=self._timeout) as r:
            return json.loads(r.read())["response"]


class RedactorPatron:
    """Segunda capa determinista. Numera tokens por tipo: [CURP_1], [RFC_1], [NOMBRE_1], [DOMICILIO_1]."""

    def __init__(self, transcriptor: Transcriptor) -> None:
        self._transcriptor = transcriptor

    def redactar(self, contenido: bytes, mime: str, nombres_conocidos: tuple[str, ...] = ()) -> Redaccion:
        texto = self._transcriptor.transcribir(contenido, mime)
        mapa: dict[str, str] = {}

        def token(tipo: str, valor: str) -> str:
            for t, v in mapa.items():
                if v == valor:
                    return t
            t = f"[{tipo}_{sum(1 for k in mapa if k.startswith(f'[{tipo}_')) + 1}]"
            mapa[t] = valor
            return t

        for tipo, patron in PATRONES_PII.items():
            texto = patron.sub(lambda m: token(tipo, m.group(0)), texto)
        def por_etiqueta(m: re.Match[str]) -> str:
            tipo = NORMALIZA.get(m.group(1).upper(), m.group(1).upper())
            return f"{tipo}: {token(tipo, m.group(2).strip())}"

        texto = ETIQUETA_VALOR_CORTO.sub(por_etiqueta, texto)
        texto = ETIQUETA_LINEA.sub(por_etiqueta, texto)
        for nombre in sorted(nombres_conocidos, key=len, reverse=True):
            if nombre:
                texto = re.sub(re.escape(nombre), lambda m: token("NOMBRE", m.group(0)), texto, flags=re.IGNORECASE)
        return Redaccion(texto_redactado=texto, mapa_tokens=mapa)
