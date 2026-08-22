"""Tool `gemini_extract`: texto REDACTADO → ExtraccionDocumento (JSON con esquema).

Scope: ingesta. Es la única tool que habla con Vertex AI, y solo recibe texto
que ya pasó `infra.frontera.afirmar_sin_pii`. El estado de vigencia NO lo
decide Gemini: lo calcula `dominio.vigencias` a partir de la fecha extraída.
"""

from datetime import date
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from dominio.enums import TipoDocumento


class ExtraccionDocumento(BaseModel):
    """Contrato de handoff. Se valida con Pydantic; si falla, reintento con el error."""

    model_config = ConfigDict(extra="forbid")

    tipo: TipoDocumento
    folio: str | None
    fecha_emision: date | None
    fecha_vencimiento: date | None  # None si no se lee. Nunca inventada.
    confianza: float = Field(ge=0.0, le=1.0)
    observaciones: str = ""


class Extractor(Protocol):
    def extraer(self, texto_redactado: str, tipo_sugerido: TipoDocumento, error_previo: str | None) -> str:
        """Devuelve JSON crudo (str). La validación la hace quien llama."""
        ...


PROMPT = """Eres el extractor documental de GARITA. Recibes la transcripción REDACTADA de un documento
mexicano de autotransporte federal (tipo sugerido: {tipo}). Devuelve JSON con el esquema dado.
Reglas: si la vigencia dice [ILEGIBLE] o no aparece, fecha_vencimiento = null y confianza <= 0.5.
Nunca inventes fechas. `folio` es el número de licencia/permiso/póliza/constancia o el sello.
{error}
TRANSCRIPCION:
{texto}"""


class ExtractorGemini:
    """google-genai contra Vertex AI. Endpoint `global` (ADR-003). Sin probar hasta facturación."""

    def __init__(self, client=None, modelo: str = "gemini-3.5-flash") -> None:
        if client is None:
            from google import genai

            client = genai.Client()  # GOOGLE_GENAI_USE_ENTERPRISE/VERTEXAI, PROJECT y LOCATION del entorno
        self._client, self._modelo = client, modelo

    def extraer(self, texto_redactado: str, tipo_sugerido: TipoDocumento, error_previo: str | None) -> str:
        error = f"Tu respuesta anterior no pasó validación: {error_previo}. Corrígela." if error_previo else ""
        r = self._client.models.generate_content(
            model=self._modelo,
            contents=PROMPT.format(tipo=tipo_sugerido, error=error, texto=texto_redactado),
            config={"response_mime_type": "application/json", "response_schema": ExtraccionDocumento, "temperature": 0},
        )
        return r.text
