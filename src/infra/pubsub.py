"""Publisher de eventos + handler de dead-letter (CLAUDE.md <failure_tolerance> 4).

`InMemoryPublisher` para tests (entrega síncrona a los suscriptores, deduplica
por idempotency_key). `PubSubPublisher` para producción: tema en Pub/Sub con
message storage policy en northamerica-south1 (ADR-003) y dead-letter topic
configurado en la suscripción; sin probar hasta tener facturación.
"""

import json
from collections.abc import Callable
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict


class Publisher(Protocol):
    def publicar(self, topico: str, mensaje: dict[str, Any], *, idempotency_key: str) -> str: ...


class InMemoryPublisher:
    def __init__(self) -> None:
        self.mensajes: dict[str, tuple[str, dict[str, Any]]] = {}
        self._suscriptores: dict[str, list[Callable[[dict[str, Any]], None]]] = {}

    def suscribir(self, topico: str, handler: Callable[[dict[str, Any]], None]) -> None:
        self._suscriptores.setdefault(topico, []).append(handler)

    def publicar(self, topico: str, mensaje: dict[str, Any], *, idempotency_key: str) -> str:
        if idempotency_key in self.mensajes:
            return idempotency_key  # reentrega: no se duplica
        self.mensajes[idempotency_key] = (topico, mensaje)
        for handler in self._suscriptores.get(topico, []):
            handler(mensaje)
        return idempotency_key


class PubSubPublisher:
    def __init__(self, project: str, client: Any | None = None) -> None:
        if client is None:
            from google.cloud import pubsub_v1

            client = pubsub_v1.PublisherClient()
        self._client, self._project = client, project

    def publicar(self, topico: str, mensaje: dict[str, Any], *, idempotency_key: str) -> str:
        ruta = self._client.topic_path(self._project, topico)
        return self._client.publish(ruta, json.dumps(mensaje, default=str).encode(), idempotency_key=idempotency_key).result()


class DeadLetter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dead_letter_id: str
    tenant_id: str
    mensaje: dict[str, Any]


def handler_dead_letter(repo, ledger, tenant_id: str) -> Callable[[dict[str, Any]], None]:
    """Escribe la falla al expediente (colección dead_letters) y al ledger. Nunca la traga."""

    def manejar(mensaje: dict[str, Any]) -> None:
        dl_id = f"dl-{mensaje.get('paso_id', 'sin-paso')}"
        repo.guardar("dead_letters", dl_id, DeadLetter(dead_letter_id=dl_id, tenant_id=tenant_id, mensaje=mensaje))
        ledger.append(tenant_id=tenant_id, viaje_id=mensaje.get("viaje_id", ""), tipo_evento="dead_letter_expediente",
                      actor="pubsub", payload={"dead_letter_id": dl_id}, idempotency_key=f"dlx:{dl_id}")

    return manejar
