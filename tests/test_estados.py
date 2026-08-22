"""AC F1: un viaje recorre todos los estados vía código; las guardas se cumplen."""

import secrets
from datetime import datetime, timezone
from pathlib import Path

import pytest

from conftest import bloqueo, viaje
from dominio.enums import EstadoAccion, EstadoViaje as E, TipoAccion
from dominio.estados import TransicionInvalida, transitar
from dominio.modelos import AccionPropuesta, Viaje
from infra.ledger import FirmadorLocalHmac, LedgerService
from infra.repository import InMemoryRepository
from tools.xsd_validate import xsd_validate

XML = (Path(__file__).resolve().parents[1] / "fixtures" / "carta_porte_31_sintetica.xml").read_bytes()


@pytest.fixture
def ctx():
    repo = InMemoryRepository()
    ledger = LedgerService(FirmadorLocalHmac(secrets.token_bytes(32)), repo=repo)
    return dict(ledger=ledger, repo=repo, actor="test")


def accion_aprobada(bloqueo_id="blq-1", estado=EstadoAccion.aprobada) -> AccionPropuesta:
    return AccionPropuesta(
        accion_id="acc-1", tenant_id="t", viaje_id="viaje-1", bloqueo_id=bloqueo_id,
        tipo=TipoAccion.renovar_documento, descripcion="Renovar verificación físico-mecánica",
        estado=estado, propuesta_por="seguimiento", propuesta_en=datetime.now(timezone.utc),
        aprobada_por="coordinador-trafico" if estado == EstadoAccion.aprobada else None,
    )


def test_viaje_recorre_todos_los_estados(ctx):
    v = viaje(bloqueos=[bloqueo()])
    v = transitar(v, E.validando, **ctx)

    with pytest.raises(TransicionInvalida, match="cero bloqueos duros"):
        transitar(v, E.listo, **ctx)
    v = transitar(v, E.bloqueado, **ctx)

    with pytest.raises(TransicionInvalida):
        transitar(v, E.validando, **ctx)  # sin acción
    with pytest.raises(TransicionInvalida, match="no está aprobada"):
        transitar(v, E.validando, accion=accion_aprobada(estado=EstadoAccion.pendiente_aprobacion), **ctx)
    with pytest.raises(TransicionInvalida, match="no resuelve"):
        transitar(v, E.validando, accion=accion_aprobada(bloqueo_id="otro"), **ctx)
    v = transitar(v, E.validando, accion=accion_aprobada(), **ctx)
    assert v.bloqueos[0].resuelto_por_accion_id == "acc-1"

    v = transitar(v, E.listo, **ctx)
    with pytest.raises(TransicionInvalida, match="exige el payload"):
        transitar(v, E.en_ruta, **ctx)
    with pytest.raises(TransicionInvalida, match="exige el payload"):
        transitar(v, E.en_ruta, carta_porte_xml=XML, **ctx)  # sin validador inyectado no hay guarda: no pasa
    with pytest.raises(TransicionInvalida, match="XSD"):
        transitar(v, E.en_ruta, carta_porte_xml=XML.replace(b'Version="3.1"', b'Version="3.0"'), xsd_validate=xsd_validate, **ctx)
    v = transitar(v, E.en_ruta, carta_porte_xml=XML, xsd_validate=xsd_validate, **ctx)
    v = transitar(v, E.cerrado, **ctx)

    with pytest.raises(TransicionInvalida):
        transitar(v, E.validando, **ctx)

    recorrido = [e.payload["a"] for e in ctx["ledger"].entradas]
    assert recorrido == ["validando", "bloqueado", "validando", "listo", "en_ruta", "cerrado"]
    assert ctx["ledger"].verify() is True
    assert ctx["repo"].obtener("viajes", "viaje-1", Viaje).estado == E.cerrado


def test_validando_a_bloqueado_exige_bloqueo_duro(ctx):
    v = transitar(viaje(bloqueos=[bloqueo(severidad="blando")]), E.validando, **ctx)
    with pytest.raises(TransicionInvalida):
        transitar(v, E.bloqueado, **ctx)
    assert transitar(v, E.listo, **ctx).estado == E.listo  # un bloqueo blando no detiene


def test_cancelado_desde_cualquier_estado_menos_terminales(ctx):
    for estado in (E.borrador, E.validando, E.bloqueado, E.listo, E.en_ruta):
        v = viaje(estado=estado, bloqueos=[bloqueo()])
        assert transitar(v, E.cancelado, **ctx).estado == E.cancelado
    for estado in (E.cerrado, E.cancelado):
        with pytest.raises(TransicionInvalida):
            transitar(viaje(estado=estado), E.cancelado, **ctx)


def test_ledger_se_escribe_antes_de_persistir(ctx):
    class RepoRoto(InMemoryRepository):
        def guardar(self, *a, **k):
            raise RuntimeError("Firestore caído")

    ctx["repo"] = RepoRoto()
    with pytest.raises(RuntimeError):
        transitar(viaje(), E.validando, **ctx)
    assert len(ctx["ledger"].entradas) == 1


def test_transitar_no_muta_el_viaje_original(ctx):
    v = viaje()
    transitar(v, E.validando, **ctx)
    assert v.estado == E.borrador
