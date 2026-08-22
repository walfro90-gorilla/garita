"""Tool `storage_read`: URI → bytes. Scope: ingesta. `gs://` vía Cloud Storage (bucket en
northamerica-south1, ADR-003); rutas locales para tests y corpus."""

from pathlib import Path


def storage_read(uri: str) -> bytes:
    if uri.startswith("gs://"):
        from google.cloud import storage  # import tardío

        bucket, _, blob = uri[5:].partition("/")
        return storage.Client().bucket(bucket).blob(blob).download_as_bytes()
    return Path(uri.removeprefix("file://")).read_bytes()
