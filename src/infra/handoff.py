"""Contrato de handoff entre agentes (CLAUDE.md <failure_tolerance> 1 y 2).

Todo output de sub-agente se valida contra Pydantic. Falla → reintento con el
error inyectado. Tercera falla → dead-letter (ledger + Pub/Sub si hay publisher).
Nunca se traga una excepción: la falla queda escrita en el expediente.
"""

import logging
from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import ValidationError

from dominio.enums import EstadoHandoff
from dominio.modelos import HandoffResult

log = logging.getLogger("garita.handoff")
T = TypeVar("T")
MAX_INTENTOS = 3


def ejecutar_handoff(
    *,
    agente: str,
    paso_id: str,
    llamar: Callable[[str | None], Any],
    validar: Callable[[Any], T],
    ledger,
    tenant_id: str,
    viaje_id: str,
    publisher=None,
    max_intentos: int = MAX_INTENTOS,
) -> tuple[T | None, HandoffResult]:
    """`llamar(error_previo)` produce la salida cruda del agente; `validar` la convierte
    al tipo esperado o lanza ValidationError/ValueError."""
    error_previo: str | None = None
    intentos = 0
    while intentos < max_intentos:
        intentos += 1
        try:
            crudo = llamar(error_previo)
            return validar(crudo), HandoffResult(agente=agente, paso_id=paso_id, estado=EstadoHandoff.ok, intentos=intentos)
        except ValidationError as e:
            error_previo = str(e)
            log.warning("handoff inválido agente=%s paso=%s intento=%d", agente, paso_id, intentos)
        except Exception as e:  # la tool reventó: también es un intento fallido, y queda registrado
            error_previo = f"{type(e).__name__}: {e}"
            log.warning("handoff con excepción agente=%s paso=%s intento=%d error=%s", agente, paso_id, intentos, error_previo)

    resultado = HandoffResult(agente=agente, paso_id=paso_id, estado=EstadoHandoff.dead_letter,
                              intentos=intentos, error_validacion=error_previo)
    mensaje = resultado.model_dump(mode="json") | {"tenant_id": tenant_id, "viaje_id": viaje_id}
    clave = f"dl:{paso_id}:{ledger.ultimo_hash(viaje_id)}"
    ledger.append(tenant_id=tenant_id, viaje_id=viaje_id, tipo_evento="dead_letter", actor=agente,
                  payload=mensaje, idempotency_key=clave)
    if publisher is not None:
        publisher.publicar("garita-dead-letter", mensaje, idempotency_key=clave)
    return None, resultado
