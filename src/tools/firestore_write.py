"""Tool `firestore_write`: persiste un modelo en una colección. Scope: ingesta.
Se registra ligada a un `Repository` (memoria en tests, Firestore MX en producción)."""

from pydantic import BaseModel


def firestore_write(repo, coleccion: str, doc_id: str, modelo: BaseModel) -> None:
    repo.guardar(coleccion, doc_id, modelo)
