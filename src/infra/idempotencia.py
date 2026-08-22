"""idempotency_key = sha256(viaje_id + paso_id + hash(input)) (CLAUDE.md <failure_tolerance>)."""

import hashlib
import json
from typing import Any


def clave_idempotencia(viaje_id: str, paso_id: str, entrada: Any) -> str:
    hash_entrada = hashlib.sha256(
        json.dumps(entrada, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()
    ).hexdigest()
    return hashlib.sha256(f"{viaje_id}{paso_id}{hash_entrada}".encode()).hexdigest()
