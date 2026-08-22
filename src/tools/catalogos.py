"""Acceso a los snapshots de catálogos y XSD del SAT en `catalogos/`.

Regla dura: si el archivo no está, se falla ruidosamente. Jamás se inventa un
valor de catálogo.
"""

from pathlib import Path

RUTA_CATALOGOS = Path(__file__).resolve().parents[2] / "catalogos"

# Fuente oficial de cada snapshot. El nombre del archivo lleva la fecha: AAAA-MM-DD_<base>.xsd
URL_OFICIAL: dict[str, str] = {
    "CartaPorte31": "http://www.sat.gob.mx/sitio_internet/cfd/CartaPorte/CartaPorte31.xsd",
    "catCartaPorte": "http://www.sat.gob.mx/sitio_internet/cfd/catalogos/CartaPorte/catCartaPorte.xsd",
    "catComExt": "http://www.sat.gob.mx/sitio_internet/cfd/catalogos/ComExt/catComExt.xsd",
    "catCFDI": "http://www.sat.gob.mx/sitio_internet/cfd/catalogos/catCFDI.xsd",
    "tdCFDI": "http://www.sat.gob.mx/sitio_internet/cfd/tipoDatos/tdCFDI/tdCFDI.xsd",
}


class CatalogoNoDisponible(LookupError):
    pass


def ruta_snapshot(base: str) -> Path:
    """Snapshot más reciente de `base` (por fecha en el nombre). Falla si no hay ninguno."""
    candidatos = sorted(RUTA_CATALOGOS.glob(f"????-??-??_{base}.xsd"))
    if not candidatos:
        raise CatalogoNoDisponible(
            f"No hay snapshot de {base} en {RUTA_CATALOGOS}. Descargar de {URL_OFICIAL.get(base, '?')}"
        )
    return candidatos[-1]
