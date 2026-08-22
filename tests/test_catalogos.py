import pytest

from tools.catalogo_lookup import catalogo_lookup
from tools.catalogos import CatalogoNoDisponible, ruta_snapshot


def test_snapshots_de_f1_existen_con_fecha():
    for base in ("CartaPorte31", "catCartaPorte", "catComExt"):
        assert ruta_snapshot(base).name[:10].count("-") == 2


def test_tipo_permiso_oficial():
    assert catalogo_lookup("c_TipoPermiso", "TPAF01") is True
    assert catalogo_lookup("c_TipoPermiso", "TPAF99") is False


def test_fraccion_arancelaria_oficial():
    assert catalogo_lookup("c_FraccionArancelaria", "01011001") is True
    assert catalogo_lookup("c_FraccionArancelaria", "XXXXXXXX") is False


def test_clave_prod_serv_cp_oficial():
    assert catalogo_lookup("c_ClaveProdServCP", "10101500") is True
    assert catalogo_lookup("c_ClaveProdServCP", "00000000") is False


def test_catalogo_fuera_del_recorte_falla_ruidosamente():
    with pytest.raises(CatalogoNoDisponible):
        catalogo_lookup("c_MaterialPeligroso", "1001")


def test_snapshot_ausente_falla_ruidosamente():
    with pytest.raises(CatalogoNoDisponible, match="Descargar de"):
        ruta_snapshot("catInexistente")
