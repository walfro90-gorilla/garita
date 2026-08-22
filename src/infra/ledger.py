"""LedgerService: append-only, encadenado por hash, firmado (ADR-006, ADR-008).

Única puerta de escritura: `LedgerService.append()`. Nadie más construye
`EntradaLedger`. La firma vive detrás de `Firmador`: HMAC local para desarrollo
y tests; Cloud KMS (MAC HMAC-SHA256) en producción, misma semántica.
"""

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any, Protocol

from dominio.modelos import EntradaLedger

HASH_GENESIS = "0" * 64


class Firmador(Protocol):
    key_id: str

    def firmar(self, digesto: bytes) -> bytes: ...

    def verificar(self, digesto: bytes, firma: bytes) -> bool: ...


class FirmadorLocalHmac:
    """Solo desarrollo y tests. La clave vive en memoria; jamás en producción."""

    def __init__(self, clave: bytes, key_id: str = "local-dev-hmac") -> None:
        self._clave = clave
        self.key_id = key_id

    def firmar(self, digesto: bytes) -> bytes:
        return hmac.new(self._clave, digesto, hashlib.sha256).digest()

    def verificar(self, digesto: bytes, firma: bytes) -> bool:
        return hmac.compare_digest(self.firmar(digesto), firma)


class FirmadorKms:
    """Adaptador Cloud KMS con llave MAC (HMAC_SHA256). Sin probar hasta tener
    facturación; el contrato es idéntico al local (ADR-008).

    `key_version`: projects/.../locations/northamerica-south1/keyRings/.../cryptoKeys/.../cryptoKeyVersions/1
    """

    def __init__(self, key_version: str, client: Any | None = None) -> None:
        self.key_id = key_version
        self._client = client

    def _kms(self) -> Any:
        if self._client is None:
            from google.cloud import kms  # import tardío: no se necesita en local

            self._client = kms.KeyManagementServiceClient()
        return self._client

    def firmar(self, digesto: bytes) -> bytes:
        return self._kms().mac_sign(name=self.key_id, data=digesto).mac

    def verificar(self, digesto: bytes, firma: bytes) -> bool:
        return self._kms().mac_verify(name=self.key_id, data=digesto, mac=firma).success


class LedgerAlterado(Exception):
    def __init__(self, secuencia: int, motivo: str) -> None:
        self.secuencia = secuencia
        super().__init__(f"entrada {secuencia}: {motivo}")


def _canonico(campos: dict[str, Any]) -> bytes:
    return json.dumps(campos, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()


def _hash(entrada: EntradaLedger) -> str:
    campos = entrada.model_dump(mode="json", exclude={"hash", "firma", "firmado_por"})
    return hashlib.sha256(_canonico(campos)).hexdigest()


class LedgerService:
    def __init__(self, firmador: Firmador, repo: Any | None = None) -> None:
        self._firmador = firmador
        self._repo = repo  # opcional: persiste cada entrada en la colección "ledger"
        self._entradas: list[EntradaLedger] = []

    @property
    def entradas(self) -> tuple[EntradaLedger, ...]:
        return tuple(self._entradas)

    def append(
        self, *, tenant_id: str, viaje_id: str, tipo_evento: str, actor: str, payload: dict[str, Any]
    ) -> EntradaLedger:
        anterior = self._entradas[-1].hash if self._entradas else HASH_GENESIS
        borrador = EntradaLedger(
            secuencia=len(self._entradas),
            tenant_id=tenant_id,
            viaje_id=viaje_id,
            tipo_evento=tipo_evento,
            actor=actor,
            payload=payload,
            registrado_en=datetime.now(timezone.utc),
            hash_anterior=anterior,
            hash="",
            firma="",
            firmado_por=self._firmador.key_id,
        )
        digesto = _hash(borrador)
        firma = self._firmador.firmar(bytes.fromhex(digesto)).hex()
        entrada = borrador.model_copy(update={"hash": digesto, "firma": firma})
        self._entradas.append(entrada)
        if self._repo is not None:
            self._repo.guardar("ledger", f"{tenant_id}:{entrada.secuencia}", entrada)
        return entrada

    def verify(self) -> bool:
        """Recalcula la cadena completa. Lanza LedgerAlterado en la primera entrada
        cuyo hash, enlace o firma no cuadre. Devuelve True si todo cuadra."""
        anterior = HASH_GENESIS
        for i, e in enumerate(self._entradas):
            if e.secuencia != i:
                raise LedgerAlterado(i, f"secuencia {e.secuencia} fuera de orden")
            if e.hash_anterior != anterior:
                raise LedgerAlterado(i, "enlace roto con la entrada anterior")
            if _hash(e) != e.hash:
                raise LedgerAlterado(i, "contenido no corresponde al hash")
            if not self._firmador.verificar(bytes.fromhex(e.hash), bytes.fromhex(e.firma)):
                raise LedgerAlterado(i, "firma inválida")
            anterior = e.hash
        return True
