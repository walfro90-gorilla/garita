"""AC F3 (local): de documentos a viaje BLOQUEADO con renovación propuesta pendiente de
aprobación · prueba de caos (cumplimiento devuelve basura → reintento → dead-letter) ·
reejecutar un paso no duplica · toda decisión está en el ledger."""

import secrets
from datetime import date

import pytest

from agentes.coordinador.flujo import Servicios, procesar_viaje, reanudar_tras_aprobacion
from conftest import TENANT
from dominio.sintetico import sembrar_expediente as expediente
from dominio.acciones import aprobar, cola_de_aprobacion
from dominio.enums import EstadoAccion, EstadoViaje as E, MotivoBloqueo, TipoAccion
from dominio.modelos import Viaje
from infra.ledger import FirmadorLocalHmac, LedgerService
from infra.pubsub import DeadLetter, InMemoryPublisher, handler_dead_letter
from infra.repository import InMemoryRepository
from tools.registry import registro_por_defecto

HOY = date(2026, 8, 22)


@pytest.fixture
def s():
    repo = InMemoryRepository()
    ledger = LedgerService(FirmadorLocalHmac(secrets.token_bytes(32)), repo=repo)
    publisher = InMemoryPublisher()
    publisher.suscribir("garita-dead-letter", handler_dead_letter(repo, ledger, TENANT))
    expediente(repo)
    return Servicios(repo=repo, ledger=ledger, registro=registro_por_defecto(repo), hoy=HOY, publisher=publisher)


def test_el_bloqueo_es_el_producto(s):
    v = procesar_viaje("viaje-1", s)
    assert v.estado == E.bloqueado
    duros = v.bloqueos_duros_abiertos()
    assert [b.motivo for b in duros] == [MotivoBloqueo.documento_vencido]
    b = duros[0]
    assert "2026-07-01" in b.explicacion and b.detectado_por == "cumplimiento"
    assert b.evidencia_uri.endswith("verificacion_fisico_mecanica_vencida.jpg")
    assert b.accion_propuesta_id == f"acc-{b.bloqueo_id}"
    blandos = [x for x in v.bloqueos if x.severidad == "blando"]
    assert {x.documento_id for x in blandos} == {"doc-pol-0001"}  # póliza vence en 19 días: aviso, no bloqueo

    cola = cola_de_aprobacion(s.repo, TENANT)
    assert len(cola) == 1 and cola[0].tipo == TipoAccion.renovar_documento and cola[0].estado == EstadoAccion.pendiente_aprobacion
    assert cola[0].propuesta_por == "seguimiento" and "Evidencia" in cola[0].descripcion

    eventos = [e.tipo_evento for e in s.ledger.entradas]
    assert eventos == ["transicion_viaje", "decision_coordinador", "transicion_viaje"]
    decision = s.ledger.entradas[1].payload
    assert decision["decision"] == "bloqueado" and decision["acciones_propuestas"] == [b.accion_propuesta_id]
    assert s.ledger.verify()


def test_reejecutar_no_duplica(s):
    procesar_viaje("viaje-1", s)
    n_ledger, n_acciones = len(s.ledger.entradas), len(s.repo.listar("acciones", type(cola_de_aprobacion(s.repo, TENANT)[0])))
    v = s.repo.obtener("viajes", "viaje-1", Viaje)
    # Reejecución del mismo paso sobre el mismo estado de entrada (p. ej. reentrega de Pub/Sub).
    from agentes.coordinador.flujo import decidir, fusionar, paso_cumplimiento, paso_seguimiento, paso_validador

    v_val = v.model_copy(update={"estado": E.validando})
    bloqueos = paso_seguimiento(v_val, fusionar(v_val, paso_validador(v_val, s)[0] + paso_cumplimiento(v_val, s)[0]), s)
    decidir(v_val, bloqueos, s)
    assert len(cola_de_aprobacion(s.repo, TENANT)) == 1
    assert len(s.repo.listar("acciones", type(cola_de_aprobacion(s.repo, TENANT)[0]))) == n_acciones
    assert sum(1 for e in s.ledger.entradas if e.tipo_evento == "decision_coordinador") == 1  # misma clave: no se duplica
    assert len(s.ledger.entradas) == n_ledger + 1  # solo la transición (bloqueado→bloqueado no existe: ver abajo)


def test_aprobar_sin_evidencia_nueva_sigue_bloqueado_y_con_evidencia_sale(s):
    procesar_viaje("viaje-1", s)
    accion = aprobar(cola_de_aprobacion(s.repo, TENANT)[0], "coordinador-trafico", ledger=s.ledger, repo=s.repo)
    assert accion.estado == EstadoAccion.aprobada and accion.aprobada_por == "coordinador-trafico"

    v = reanudar_tras_aprobacion("viaje-1", accion.accion_id, s)
    assert v.estado == E.bloqueado  # aprobar la renovación no hace legal al tractor
    assert len(cola_de_aprobacion(s.repo, TENANT)) == 0  # la acción existente (aprobada) se reutiliza, no se duplica

    expediente(s.repo, verificacion_vencida=False)  # llega la verificación renovada (ingesta)
    s.repo.guardar("viajes", "viaje-1", v)
    v = reanudar_tras_aprobacion("viaje-1", accion.accion_id, s)
    assert v.estado == E.listo and v.bloqueos_duros_abiertos() == []
    assert s.ledger.verify()


def test_caos_cumplimiento_devuelve_basura(s, caplog):
    llamadas = {"n": 0}

    def vigencias_rotas(**kwargs):
        llamadas["n"] += 1
        return [{"bloqueo_id": "x", "motivo": "alucinado", "severidad": "tal vez"}]

    s.registro.registrar("vigencias_query", vigencias_rotas)
    with caplog.at_level("WARNING", logger="garita.handoff"):
        v = procesar_viaje("viaje-1", s)
    assert llamadas["n"] == 3
    assert sum("handoff inválido" in m for m in caplog.messages) == 3
    assert v.estado == E.bloqueado
    assert [b.motivo for b in v.bloqueos_duros_abiertos()] == [MotivoBloqueo.verificacion_fallida]
    assert "dead_letter" in [e.tipo_evento for e in s.ledger.entradas]
    assert s.repo.obtener("dead_letters", "dl-cumplimiento:viaje-1", DeadLetter).mensaje["intentos"] == 3
    assert [a.tipo for a in cola_de_aprobacion(s.repo, TENANT)] == [TipoAccion.notificar]


def test_validador_bloquea_catalogo_y_datos(s):
    v = s.repo.obtener("viajes", "viaje-1", Viaje)
    v.mercancias[0].clave_prod_serv_cp = "00000000"
    v.caja_ids.append("caja-fantasma")
    s.repo.guardar("viajes", "viaje-1", v)
    v = procesar_viaje("viaje-1", s)
    motivos = sorted(b.motivo for b in v.bloqueos_duros_abiertos() if b.detectado_por == "validador")
    assert motivos == [MotivoBloqueo.catalogo_invalido, MotivoBloqueo.dato_inconsistente]


def test_coordinador_no_puede_resolver_tools_de_otros(s):
    from tools.registry import ToolFueraDeScope

    for tool in ("cross_check", "vigencias_query", "proponer_accion", "storage_read"):
        with pytest.raises(ToolFueraDeScope):
            s.registro.resolver("coordinador", tool)


def test_despachar_timbra_con_mock_y_sale(s):
    from agentes.coordinador.flujo import CartaPorteTimbrada, despachar

    expediente(s.repo, verificacion_vencida=False)
    assert procesar_viaje("viaje-1", s).estado == E.listo
    v, timbre = despachar("viaje-1", s)
    assert v.estado == E.en_ruta and timbre.uuid.startswith("TEST-") and timbre.pac.startswith("PAC-MOCK")
    cp = s.repo.obtener("cartas_porte", "viaje-1", CartaPorteTimbrada)
    assert cp.id_ccp.startswith("CCC") and cp.hash_xml == timbre.hash_xml and "TEST001" in cp.xml
    assert [e.tipo_evento for e in s.ledger.entradas][-2:] == ["carta_porte_timbrada_mock", "transicion_viaje"]
    assert s.ledger.verify()


def test_despachar_bloqueado_no_sale(s):
    from agentes.coordinador.flujo import despachar

    procesar_viaje("viaje-1", s)
    with pytest.raises(ValueError, match="no está en listo"):
        despachar("viaje-1", s)
