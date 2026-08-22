"""F0: el servidor ADK levanta y expone el agente `hello`.

Misma ruta de código que usa el contenedor en Cloud Run (`adk api_server`),
así que si esto falla, el deploy también.
"""

from fastapi.testclient import TestClient
from google.adk.cli.fast_api import get_fast_api_app


def test_list_apps_incluye_hello():
    app = get_fast_api_app(agents_dir="src/agentes", web=False)
    with TestClient(app) as client:
        respuesta = client.get("/list-apps")
    assert respuesta.status_code == 200
    assert "hello" in respuesta.json()
