# Snapshots SAT — congelados el 2026-08-22

Descargados sin modificar de las URLs oficiales del SAT. El nombre lleva la
fecha del snapshot; `tools/catalogos.ruta_snapshot()` toma el más reciente.
Si un catálogo no está aquí, el código falla ruidosamente: nunca se inventa.

| Archivo | SHA-256 (prefijo) |
|---|---|
| `2026-08-22_CartaPorte31.xsd` | `31d40c4d96aea02b…` |
| `2026-08-22_catCartaPorte.xsd` | `d2281b5fbe414914…` |
| `2026-08-22_catCFDI.xsd` | `6c58936cb77576f8…` |
| `2026-08-22_catComExt.xsd` | `6c2d60cb8f92810d…` |
| `2026-08-22_tdCFDI.xsd` | `b3b81fe4017b95d5…` |

| Base | URL oficial |
|---|---|
| CartaPorte31 | http://www.sat.gob.mx/sitio_internet/cfd/CartaPorte/CartaPorte31.xsd |
| catCartaPorte | http://www.sat.gob.mx/sitio_internet/cfd/catalogos/CartaPorte/catCartaPorte.xsd |
| catComExt | http://www.sat.gob.mx/sitio_internet/cfd/catalogos/ComExt/catComExt.xsd |
| catCFDI | http://www.sat.gob.mx/sitio_internet/cfd/catalogos/catCFDI.xsd |
| tdCFDI | http://www.sat.gob.mx/sitio_internet/cfd/tipoDatos/tdCFDI/tdCFDI.xsd |

Catálogos consultables en F1 (SPEC §5.1): `c_ClaveProdServCP` (48 757 claves) y
`c_TipoPermiso` (26) en catCartaPorte; `c_FraccionArancelaria` (26 045) en
catComExt. catCFDI y tdCFDI están solo porque CartaPorte31.xsd los importa.
Los demás catálogos (c_ConfigAutotransporte, c_RegimenAduanero,
c_MaterialPeligroso, c_ClaveUnidad…) existen en los archivos pero
`catalogo_lookup` los rechaza a propósito hasta que una fase los habilite.
