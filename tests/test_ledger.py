import secrets

import pytest

from dominio.modelos import EntradaLedger
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

    assert repo.obtener("ledger", "000000000001", EntradaLedger) == ledger.entradas[1]


def test_rehidrata_la_cadena_desde_el_repositorio():
    """Cloud Run escala a cero: una instancia nueva continúa la cadena, no la pisa."""
    repo, clave = InMemoryRepository(), secrets.token_bytes(32)
    l1 = LedgerService(FirmadorLocalHmac(clave), repo=repo)
    _llenar(l1, 2)
    l1.append(tenant_id="t", viaje_id="v", tipo_evento="x", actor="a", payload={}, idempotency_key="k")
    l2 = LedgerService(FirmadorLocalHmac(clave), repo=repo)
    assert len(l2.entradas) == 3 and l2.verify()
    assert l2.append(tenant_id="t", viaje_id="v", tipo_evento="x", actor="a", payload={}, idempotency_key="k").secuencia == 2
    nueva = l2.append(tenant_id="t", viaje_id="v", tipo_evento="y", actor="a", payload={})
    assert nueva.secuencia == 3 and nueva.hash_anterior == l1.entradas[2].hash
    assert len(repo.listar("ledger", EntradaLedger)) == 4 and l2.verify()
    assert l2.ultimo_hash("v") == nueva.hash and l2.ultimo_hash("otro") == "0" * 64
