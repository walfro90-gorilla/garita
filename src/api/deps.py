"""Cableado de servicios para la API. Local: memoria + HMAC; producción: Firestore + KMS (ADR-003/008).

GARITA_BACKEND=memoria|firestore · GARITA_SEED_DEMO=1 siembra el expediente sintético.
"""

import os
import secrets
from datetime import date

from agentes.coordinador.flujo import Servicios
from dominio.sintetico import sembrar_expediente
from infra.ledger import FirmadorKms, FirmadorLocalHmac, LedgerService
from infra.pac_mock import PacMock
from infra.pubsub import InMemoryPublisher, handler_dead_letter
from infra.repository import FirestoreRepository, InMemoryRepository
from tools.registry import registro_por_defecto


def construir_servicios(*, hoy: date | None = None) -> Servicios:
    backend = os.environ.get("GARITA_BACKEND", "memoria")
    if backend == "firestore":
        repo = FirestoreRepository(project=os.environ["GOOGLE_CLOUD_PROJECT"], database=os.environ.get("GARITA_FIRESTORE_DB", "(default)"))
        firmador = FirmadorKms(os.environ["GARITA_KMS_KEY_VERSION"])
    else:
        repo = InMemoryRepository()
        firmador = FirmadorLocalHmac(secrets.token_bytes(32))  # clave efímera: solo desarrollo
    ledger = LedgerService(firmador, repo=repo)
    publisher = InMemoryPublisher()  # Pub/Sub real: cuando haya facturación (PROGRESS.md)
    tenant = os.environ.get("GARITA_TENANT", "tenant-cafe57-sintetico")
    publisher.suscribir("garita-dead-letter", handler_dead_letter(repo, ledger, tenant))
    if os.environ.get("GARITA_SEED_DEMO") == "1":
        sembrar_expediente(repo)
    return Servicios(repo=repo, ledger=ledger, registro=registro_por_defecto(repo), hoy=hoy or date.today(),
                     publisher=publisher, pac=PacMock())
