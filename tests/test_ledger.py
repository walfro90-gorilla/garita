import secrets

import pytest

from infra.ledger import FirmadorLocalHmac, LedgerAlterado, LedgerService
from infra.repository import InMemoryRepository


def _ledger(repo=None) -> LedgerService:
    return LedgerService(FirmadorLocalHmac(secrets.token_bytes(32)), repo=repo)


def _llenar(ledger: LedgerService, n: int = 3) -> None:
    for i in range(n):
        ledger.append(tenant_id="t", viaje_id="viaje-1", tipo_evento="evento", actor="test", payload={"i": i})


def test_cadena_integra_verifica():
    ledger = _ledger()
    _llenar(ledger)
    assert ledger.verify() is True
    assert ledger.entradas[0].hash_anterior == "0" * 64
    assert ledger.entradas[2].hash_anterior == ledger.entradas[1].hash


def test_detecta_payload_alterado_a_mano():
    ledger = _ledger()
    _llenar(ledger)
    alterada = ledger.entradas[1].model_copy(update={"payload": {"i": 999}})
    ledger._entradas[1] = alterada  # alteración directa, fuera de append()
    with pytest.raises(LedgerAlterado) as exc:
        ledger.verify()
    assert exc.value.secuencia == 1


def test_detecta_hash_recalculado_sin_la_llave():
    """Un atacante recalcula el hash para que cuadre, pero no puede firmar."""
    from infra.ledger import _hash

    ledger = _ledger()
    _llenar(ledger)
    e = ledger.entradas[2].model_copy(update={"payload": {"i": 999}})
    ledger._entradas[2] = e.model_copy(update={"hash": _hash(e)})
    with pytest.raises(LedgerAlterado, match="firma inválida"):
        ledger.verify()


def test_detecta_entrada_eliminada():
    ledger = _ledger()
    _llenar(ledger)
    del ledger._entradas[1]
    with pytest.raises(LedgerAlterado):
        ledger.verify()


def test_entradas_son_inmutables():
    ledger = _ledger()
    _llenar(ledger, 1)
    with pytest.raises(Exception):
        ledger.entradas[0].payload = {}  # type: ignore[misc]


def test_persiste_en_repositorio():
    repo = InMemoryRepository()
    ledger = _ledger(repo)
    _llenar(ledger, 2)
    from dominio.modelos import EntradaLedger

    assert repo.obtener("ledger", "t:1", EntradaLedger) == ledger.entradas[1]
