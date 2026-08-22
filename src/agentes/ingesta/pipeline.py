"""Pipeline determinista del agente `ingesta` (F2). El envoltorio ADK llega en F3.

documento → storage_read → gemma_redact (zona PII) → frontera → gemini_extract
→ validación Pydantic (reintento ×3, luego dead-letter) → DocumentoVigencia
→ firestore_write (documento + mapa de tokens) → ledger.

`ingesta` no decide bloqueos (CLAUDE.md <agent_contracts>): solo produce el
DocumentoVigencia con su estado de vigencia calculado.
"""

import hashlib
import logging
from datetime import date

from pydantic import BaseModel, ConfigDict

from dominio.enums import EstadoHandoff, TipoDocumento
from dominio.modelos import DocumentoVigencia, HandoffResult
from dominio.vigencias import estado_vigencia
from infra.frontera import FugaPII, afirmar_sin_pii
from infra.handoff import ejecutar_handoff
from tools.gemini_extract import ExtraccionDocumento
from tools.registry import ToolRegistry

log = logging.getLogger("garita.ingesta")
AGENTE = "ingesta"


class MapaRedaccion(BaseModel):
    """Token → valor original. Vive solo en Firestore MX. Nunca se envía a nadie."""

    model_config = ConfigDict(extra="forbid")

    documento_id: str
    tenant_id: str
    mapa_tokens: dict[str, str]


def ingerir(
    *,
    documento_id: str,
    tenant_id: str,
    fuente_uri: str,
    mime: str,
    tipo_sugerido: TipoDocumento,
    registro: ToolRegistry,
    ledger,
    hoy: date,
    nombres_conocidos: tuple[str, ...] = (),
    publisher=None,
) -> HandoffResult:
    paso_id = f"ingesta:{documento_id}"
    storage_read = registro.resolver(AGENTE, "storage_read")
    gemma_redact = registro.resolver(AGENTE, "gemma_redact")
    gemini_extract = registro.resolver(AGENTE, "gemini_extract")
    firestore_write = registro.resolver(AGENTE, "firestore_write")

    contenido = storage_read(fuente_uri)
    hash_documento = hashlib.sha256(contenido).hexdigest()

    redaccion = gemma_redact(contenido, mime, nombres_conocidos)
    try:
        afirmar_sin_pii(redaccion.texto_redactado, tuple(redaccion.mapa_tokens.values()), documento_id=documento_id)
    except FugaPII as e:
        ledger.append(tenant_id=tenant_id, viaje_id="", tipo_evento="fuga_pii_detenida", actor=AGENTE,
                      payload={"documento_id": documento_id, "motivo": str(e)})
        return HandoffResult(agente=AGENTE, paso_id=paso_id, estado=EstadoHandoff.dead_letter, intentos=0,
                             error_validacion=str(e))

    extraccion, resultado = ejecutar_handoff(
        agente=AGENTE, paso_id=paso_id,
        llamar=lambda error_previo: gemini_extract(redaccion.texto_redactado, tipo_sugerido, error_previo),
        validar=ExtraccionDocumento.model_validate_json, ledger=ledger, tenant_id=tenant_id, viaje_id="",
        publisher=publisher,
    )
    if extraccion is None:
        return resultado
    intentos = resultado.intentos

    documento = DocumentoVigencia(
        documento_id=documento_id,
        tenant_id=tenant_id,
        tipo=extraccion.tipo,
        folio=extraccion.folio,
        fecha_emision=extraccion.fecha_emision,
        fecha_vencimiento=extraccion.fecha_vencimiento,
        estado=estado_vigencia(extraccion.fecha_vencimiento, hoy),
        fuente_uri=fuente_uri,
        confianza_extraccion=extraccion.confianza,
        requiere_revision_humana=False,  # el validador del modelo lo sube a True si corresponde
        hash_documento=hash_documento,
    )
    firestore_write("documentos", documento_id, documento)
    firestore_write("mapas_redaccion", documento_id,
                    MapaRedaccion(documento_id=documento_id, tenant_id=tenant_id, mapa_tokens=redaccion.mapa_tokens))
    ledger.append(tenant_id=tenant_id, viaje_id="", tipo_evento="documento_ingresado", actor=AGENTE,
                  payload={"documento_id": documento_id, "hash_documento": hash_documento,
                           "estado": documento.estado, "intentos": intentos,
                           "requiere_revision_humana": documento.requiere_revision_humana})
    return HandoffResult(agente=AGENTE, paso_id=paso_id, estado=EstadoHandoff.ok, intentos=intentos,
                         payload=documento.model_dump(mode="json"))
