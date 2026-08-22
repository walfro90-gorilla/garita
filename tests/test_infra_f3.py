import secrets

from infra.idempotencia import clave_idempotencia
from infra.ledger import FirmadorLocalHmac, LedgerService
from infra.pubsub import InMemoryPublisher


def test_clave_idempotencia_estable_y_sensible_al_input():
    a = clave_idempotencia("v1", "paso", {"x": 1, "y": [1, 2]})
    assert a == clave_idempotencia("v1", "paso", {"y": [1, 2], "x": 1})
    assert a != clave_idempotencia("v1", "paso", {"x": 2}) and a != clave_idempotencia("v2", "paso", {"x": 1})


def test_ledger_no_duplica_con_misma_clave():
    ledger = LedgerService(FirmadorLocalHmac(secrets.token_bytes(32)))
    e1 = ledger.append(tenant_id="t", viaje_id="v", tipo_evento="x", actor="a", payload={}, idempotency_key="k")
    e2 = ledger.append(tenant_id="t", viaje_id="v", tipo_evento="x", actor="a", payload={}, idempotency_key="k")
    assert e1 == e2 and len(ledger.entradas) == 1 and ledger.verify()


def test_publisher_en_memoria_deduplica_y_entrega():
    p, recibidos = InMemoryPublisher(), []
    p.suscribir("t", recibidos.append)
    p.publicar("t", {"a": 1}, idempotency_key="k")
    p.publicar("t", {"a": 1}, idempotency_key="k")
    assert recibidos == [{"a": 1}]
