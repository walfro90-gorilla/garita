"""Repositorio de documentos: protocolo + memoria (tests) + Firestore.

Sin aislamiento por tenant (CLAUDE.md <forbidden_actions>): `tenant_id` viaja
dentro del documento y nada más.
"""

from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

M = TypeVar("M", bound=BaseModel)


class Repository(Protocol):
    def guardar(self, coleccion: str, doc_id: str, modelo: BaseModel) -> None: ...

    def obtener(self, coleccion: str, doc_id: str, tipo: type[M]) -> M | None: ...

    def listar(self, coleccion: str, tipo: type[M], **igual: Any) -> list[M]: ...


class InMemoryRepository:
    def __init__(self) -> None:
        self._docs: dict[tuple[str, str], dict[str, Any]] = {}

    def guardar(self, coleccion: str, doc_id: str, modelo: BaseModel) -> None:
        self._docs[(coleccion, doc_id)] = modelo.model_dump(mode="json")

    def obtener(self, coleccion: str, doc_id: str, tipo: type[M]) -> M | None:
        datos = self._docs.get((coleccion, doc_id))
        return None if datos is None else tipo.model_validate(datos)

    def listar(self, coleccion: str, tipo: type[M], **igual: Any) -> list[M]:
        return [
            tipo.model_validate(d)
            for (c, _), d in self._docs.items()
            if c == coleccion and all(d.get(k) == v for k, v in igual.items())
        ]


class FirestoreRepository:
    """Adaptador Firestore. Base de datos en northamerica-south1 (ADR-003).
    Sin prueba automática hasta tener facturación; misma interfaz que memoria."""

    def __init__(self, project: str, database: str = "(default)", client: Any | None = None) -> None:
        if client is None:
            from google.cloud import firestore  # import tardío: no se necesita en local

            client = firestore.Client(project=project, database=database)
        self._client = client

    def guardar(self, coleccion: str, doc_id: str, modelo: BaseModel) -> None:
        self._client.collection(coleccion).document(doc_id).set(modelo.model_dump(mode="json"))

    def obtener(self, coleccion: str, doc_id: str, tipo: type[M]) -> M | None:
        snap = self._client.collection(coleccion).document(doc_id).get()
        return tipo.model_validate(snap.to_dict()) if snap.exists else None

    def listar(self, coleccion: str, tipo: type[M], **igual: Any) -> list[M]:
        from google.cloud.firestore_v1 import FieldFilter

        q = self._client.collection(coleccion)
        for k, v in igual.items():
            q = q.where(filter=FieldFilter(k, "==", v))
        return [tipo.model_validate(d.to_dict()) for d in q.stream()]
