"""Las dos vistas (cola de aprobación, expediente) y el recorrido del demo por HTTP."""

from datetime import date

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("GARITA_BACKEND", "memoria")
    monkeypatch.setenv("GARITA_SEED_DEMO", "1")
    from api.deps import construir_servicios
    from api.main import app

    app.state.servicios = construir_servicios(hoy=date(2026, 8, 22))
    with TestClient(app) as c:
        yield c


def test_recorrido_del_demo(client):
    assert client.get("/api/salud").json()["pac"] == "mock"
    assert client.get("/list-apps").status_code == 200  # el servidor ADK sigue montado

    r = client.post("/api/viajes/viaje-1/procesar")
    assert r.status_code == 200 and r.json()["estado"] == "bloqueado"
    cola = client.get("/api/acciones").json()
    assert len(cola) == 1 and cola[0]["tipo"] == "renovar_documento"
    accion_id = cola[0]["accion_id"]

    exp = client.get("/api/viajes/viaje-1").json()
    assert exp["viaje"]["estado"] == "bloqueado" and exp["tractor"]["placa"] == "TEST001"
    assert [e["tipo_evento"] for e in exp["ledger"]] == ["transicion_viaje", "decision_coordinador", "transicion_viaje"]

    r = client.post(f"/api/acciones/{accion_id}/aprobar", json={"humano": "coordinador-trafico"})
    assert r.status_code == 200 and r.json()["accion"]["estado"] == "aprobada"
    assert r.json()["viaje"]["estado"] == "bloqueado"  # sin evidencia nueva sigue bloqueado
    assert client.post(f"/api/acciones/{accion_id}/aprobar", json={"humano": "x"}).status_code == 409

    # Bloqueado y con acción aprobada, pero sin evidencia nueva: reprocesar lo deja bloqueado.
    assert client.post("/api/viajes/viaje-1/procesar").json()["estado"] == "bloqueado"

    # Llega la verificación renovada (alta manual; con Gemini la hará ingesta) y se revalida.
    doc = exp["tractor"]["verificacion_fisico_mecanica"] | {"fecha_vencimiento": "2027-07-01", "estado": "vigente",
                                                           "hash_documento": "b" * 64, "folio": "TEST-VFM-0002"}
    assert client.put("/api/documentos/doc-verif-0001", json=doc).status_code == 200
    r = client.post("/api/viajes/viaje-1/procesar")
    assert r.status_code == 200 and r.json()["estado"] == "listo" and r.json()["bloqueos"][0]["resuelto_por_accion_id"] is None
    assert client.post("/api/viajes/viaje-1/procesar").status_code == 409  # listo: ya no se procesa, se despacha

    r = client.post("/api/viajes/viaje-1/despachar")
    assert r.status_code == 200 and r.json()["viaje"]["estado"] == "en_ruta" and r.json()["timbre"]["uuid"].startswith("TEST-")
    assert client.post("/api/viajes/viaje-1/despachar").status_code == 409
    assert client.get("/api/ledger/verify").json()["integro"] is True


def test_404_y_validacion(client):
    assert client.get("/api/viajes/nope").status_code == 404
    assert client.post("/api/acciones/nope/aprobar", json={"humano": "x"}).status_code == 404
    assert client.put("/api/documentos/x", json={"documento_id": "y"}).status_code == 422
