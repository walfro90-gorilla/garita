"""Tool `xsd_validate`: valida un Complemento Carta Porte 3.1 contra el XSD oficial.

Scope: validador. Sin red: los `xs:import` del XSD apuntan a URLs del SAT y se
reescriben a los snapshots locales antes de compilar el esquema.
"""

from functools import lru_cache

from lxml import etree

from tools.catalogos import URL_OFICIAL, ruta_snapshot

XS = "http://www.w3.org/2001/XMLSchema"


@lru_cache(maxsize=1)
def _esquema() -> etree.XMLSchema:
    doc = etree.parse(str(ruta_snapshot("CartaPorte31")))
    locales = {url: base for base, url in URL_OFICIAL.items()}
    for imp in doc.iter(f"{{{XS}}}import"):
        url = imp.get("schemaLocation")
        if url in locales:
            imp.set("schemaLocation", ruta_snapshot(locales[url]).as_uri())
        else:  # una URL que no tenemos en snapshot: fallar ruidosamente, nunca ir a red
            raise RuntimeError(f"xs:import sin snapshot local: {url}")
    return etree.XMLSchema(doc)


def xsd_validate(xml: bytes) -> list[str]:
    """Lista de errores. Vacía = válido."""
    try:
        arbol = etree.fromstring(xml)
    except etree.XMLSyntaxError as e:
        return [f"XML mal formado: {e}"]
    esquema = _esquema()
    if esquema.validate(arbol):
        return []
    return [f"línea {e.line}: {e.message}" for e in esquema.error_log]
