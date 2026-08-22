from datetime import date

from dominio.enums import EstadoVigencia as V
from dominio.vigencias import estado_vigencia

HOY = date(2026, 8, 22)


def test_estados_de_vigencia():
    assert estado_vigencia(date(2026, 7, 1), HOY) == V.vencido
    assert estado_vigencia(date(2026, 8, 22), HOY) == V.por_vencer  # vence hoy: todavía no vencido
    assert estado_vigencia(date(2026, 9, 21), HOY) == V.por_vencer  # día 30
    assert estado_vigencia(date(2026, 9, 22), HOY) == V.vigente  # día 31
    assert estado_vigencia(None, HOY) == V.ilegible
    assert estado_vigencia(None, HOY, localizado=False) == V.no_localizado
