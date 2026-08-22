"""Mock del PAC (Proveedor Autorizado de Certificación). NUNCA timbra de verdad.

Contrato (el mismo que tendría un adaptador real, SPEC §7):
    timbrar(xml) -> Timbre   | lanza TimbradoRechazado si el XML no pasa el XSD
El mock valida contra el XSD oficial, genera un UUID determinista con prefijo
TEST- y un sello ficticio. Se declara como mock en el video y en el README.
"""

import hashlib
from datetime import datetime, timezone
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from tools.xsd_validate import xsd_validate


class Timbre(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    uuid: str  # TEST-… nunca un folio fiscal real
    fecha_timbrado: datetime
    sello_sat: str
    no_certificado_sat: str
    hash_xml: str  # SHA-256 del XML timbrado, va al ledger
    pac: str


class TimbradoRechazado(ValueError):
    def __init__(self, errores: list[str]) -> None:
        self.errores = errores
        super().__init__("PAC rechazó el XML: " + " | ".join(errores[:3]))


class Pac(Protocol):
    def timbrar(self, xml: bytes) -> Timbre: ...


class PacMock:
    nombre = "PAC-MOCK (sin timbrado real)"

    def timbrar(self, xml: bytes) -> Timbre:
        errores = xsd_validate(xml)
        if errores:
            raise TimbradoRechazado(errores)
        h = hashlib.sha256(xml).hexdigest()
        return Timbre(
            uuid=f"TEST-{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}".upper(),
            fecha_timbrado=datetime.now(timezone.utc),
            sello_sat="MOCK-SELLO-" + h[:16],
            no_certificado_sat="TEST-00000000000000000000",
            hash_xml=h,
            pac=self.nombre,
        )
