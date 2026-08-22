"""Tool `catalogo_lookup`: ¿existe `clave` en el catálogo SAT `catalogo`?

Scope: validador. Determinista. Lee las enumeraciones de los XSD oficiales
descargados en `catalogos/`. Solo los tres catálogos del recorte de F1
(SPEC §5.1); cualquier otro lanza CatalogoNoDisponible, no se adivina.
"""

from functools import lru_cache

from lxml import etree

from tools.catalogos import CatalogoNoDisponible, ruta_snapshot

XS = "http://www.w3.org/2001/XMLSchema"

# catálogo → archivo base del snapshot que lo contiene
ARCHIVO_POR_CATALOGO: dict[str, str] = {
    "c_ClaveProdServCP": "catCartaPorte",
    "c_TipoPermiso": "catCartaPorte",
    "c_FraccionArancelaria": "catComExt",
}


@lru_cache(maxsize=None)
def _enumeraciones(base: str) -> dict[str, frozenset[str]]:
    arbol = etree.parse(str(ruta_snapshot(base)))
    resultado: dict[str, frozenset[str]] = {}
    for tipo in arbol.iter(f"{{{XS}}}simpleType"):
        nombre = tipo.get("name")
        if nombre:
            resultado[nombre] = frozenset(
                e.get("value") for e in tipo.iter(f"{{{XS}}}enumeration") if e.get("value") is not None
            )
    return resultado


def catalogo_lookup(catalogo: str, clave: str) -> bool:
    base = ARCHIVO_POR_CATALOGO.get(catalogo)
    if base is None:
        raise CatalogoNoDisponible(
            f"{catalogo} no forma parte del snapshot de F1 (SPEC §5.1: solo "
            f"{sorted(ARCHIVO_POR_CATALOGO)}). No se inventa."
        )
    valores = _enumeraciones(base).get(catalogo)
    if valores is None:
        raise CatalogoNoDisponible(f"{catalogo} no aparece en {ruta_snapshot(base).name}")
    return clave in valores
