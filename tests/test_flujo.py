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
from dominio.modelos import AccionPropuesta, Viaje
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


def test_reentrega_tras_completar_no_duplica(s):
    """Pub/Sub reentrega 'procesar' después de un run completo: la guarda de estado lo rechaza sin tocar nada."""
    procesar_viaje("viaje-1", s)
    n_ledger, n_acc = len(s.ledger.entradas), len(s.repo.listar("acciones", AccionPropuesta))
    with pytest.raises(ValueError, match="solo se procesa en validando"):
        procesar_viaje("viaje-1", s)
    assert (len(s.ledger.entradas), len(s.repo.listar("acciones", AccionPropuesta))) == (n_ledger, n_acc)


def test_reintento_tras_caida_parcial_no_duplica(s):
    """Cae el proceso tras escribir la decisión al ledger y antes de persistir el viaje: el reintento
    produce exactamente una decisión y una acción (clave por versión del expediente)."""
    from agentes.coordinador.flujo import decidir, fusionar, paso_cumplimiento, paso_seguimiento, paso_validador

    class RepoCae(InMemoryRepository):
        def guardar(self, coleccion, doc_id, modelo):
            if coleccion == "viajes" and getattr(modelo, "estado", None) == E.bloqueado and not getattr(self, "ya", False):
                self.ya = True
                raise RuntimeError("Firestore caído a medio commit")
            super().guardar(coleccion, doc_id, modelo)

    s.repo = RepoCae(); expediente(s.repo); s.registro = registro_por_defecto(s.repo)
    s.ledger = LedgerService(FirmadorLocalHmac(secrets.token_bytes(32)), repo=s.repo)
    with pytest.raises(RuntimeError):
        procesar_viaje("viaje-1", s)
    assert procesar_viaje("viaje-1", s).estado == E.bloqueado  # el viaje quedó en validando: se reintenta
    assert [e.tipo_evento for e in s.ledger.entradas].count("decision_coordinador") == 1
    assert [e.tipo_evento for e in s.ledger.entradas].count("transicion_viaje") == 2  # borrador→validando, validando→bloqueado
    assert len(s.repo.listar("acciones", AccionPropuesta)) == 1 and s.ledger.verify()


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
    with pytest.raises(ValueError, match="humano"):
        despachar("viaje-1", s, humano="")
    v, timbre = despachar("viaje-1", s, humano="coordinador-trafico")
    assert v.estado == E.en_ruta and timbre.uuid.startswith("TEST-") and timbre.pac.startswith("PAC-MOCK")
    assert s.ledger.entradas[-2].actor == "coordinador-trafico" and s.ledger.entradas[-2].payload["autorizado_por"] == "coordinador-trafico"
    cp = s.repo.obtener("cartas_porte", "viaje-1", CartaPorteTimbrada)
    assert cp.id_ccp.startswith("CCC") and cp.hash_xml == timbre.hash_xml and "TEST001" in cp.xml
    assert [e.tipo_evento for e in s.ledger.entradas][-2:] == ["carta_porte_timbrada_mock", "transicion_viaje"]
    assert s.ledger.verify()


def test_despachar_bloqueado_no_sale(s):
    from agentes.coordinador.flujo import despachar

    procesar_viaje("viaje-1", s)
    with pytest.raises(ValueError, match="no está en listo"):
        despachar("viaje-1", s, humano="x")


def test_rechazar_no_deja_al_viaje_sin_salida(s):
    from agentes.coordinador.flujo import reproponer_tras_rechazo
    from dominio.acciones import rechazar

    procesar_viaje("viaje-1", s)
    primera = cola_de_aprobacion(s.repo, TENANT)[0]
    rechazar(primera, "coordinador-trafico", ledger=s.ledger, repo=s.repo)
    assert cola_de_aprobacion(s.repo, TENANT) == []
    v = reproponer_tras_rechazo("viaje-1", s)
    nueva = cola_de_aprobacion(s.repo, TENANT)
    assert len(nueva) == 1 and nueva[0].accion_id == f"{primera.accion_id}-2"
    assert v.bloqueos_duros_abiertos()[0].accion_propuesta_id == nueva[0].accion_id
    assert reproponer_tras_rechazo("viaje-1", s).bloqueos_duros_abiertos()[0].accion_propuesta_id == nueva[0].accion_id  # idempotente


def test_tool_que_revienta_va_a_dead_letter(s):
    def vigencias_rotas(**kwargs):
        raise KeyError("activo sin documentos")

    s.registro.registrar("vigencias_query", vigencias_rotas)
    v = procesar_viaje("viaje-1", s)
    assert [b.motivo for b in v.bloqueos_duros_abiertos()] == [MotivoBloqueo.verificacion_fallida]
    dl = [e for e in s.ledger.entradas if e.tipo_evento == "dead_letter"]
    assert len(dl) == 1 and "KeyError" in dl[0].payload["error_validacion"] and dl[0].payload["viaje_id"] == "viaje-1"
    assert s.repo.obtener("dead_letters", "dl-cumplimiento:viaje-1", DeadLetter) is not None
