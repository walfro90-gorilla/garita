"""AC F3 (local): de documentos a viaje BLOQUEADO con renovación propuesta pendiente de
aprobación · prueba de caos (cumplimiento devuelve basura → reintento → dead-letter) ·
reejecutar un paso no duplica · toda decisión está en el ledger."""

import secrets
from datetime import date

import pytest

from agentes.coordinador.flujo import Servicios, procesar_viaje, reanudar_tras_aprobacion
from conftest import TENANT, documento, viaje
from dominio.acciones import aprobar, cola_de_aprobacion
from dominio.enums import EstadoAccion, EstadoViaje as E, EstadoVigencia, MotivoBloqueo, TipoAccion, TipoDocumento
from dominio.modelos import Activo, Mercancia, Operador, Viaje
from infra.ledger import FirmadorLocalHmac, LedgerService
from infra.pubsub import DeadLetter, InMemoryPublisher, handler_dead_letter
from infra.repository import InMemoryRepository
from tools.registry import registro_por_defecto

HOY = date(2026, 8, 22)


def expediente(repo, *, verificacion_vencida=True):
    """Café 57 sintético: tractor TEST001 con verificación vencida el 2026-07-01, caja, operador."""
    verif = documento(documento_id="doc-verif-0001", tipo=TipoDocumento.verificacion_fisico_mecanica, folio="TEST-VFM-0001",
                      fecha_vencimiento=date(2026, 7, 1) if verificacion_vencida else date(2027, 7, 1),
                      estado=EstadoVigencia.vencido if verificacion_vencida else EstadoVigencia.vigente,
                      fuente_uri="gs://garita-sintetico/verificacion_fisico_mecanica_vencida.jpg")
    poliza = documento(documento_id="doc-pol-0001", tipo=TipoDocumento.poliza_responsabilidad_civil, folio="TEST-POL-0001",
                       fecha_vencimiento=date(2026, 9, 10), estado=EstadoVigencia.vigente)
    tarjeta = documento(documento_id="doc-tc-0001", tipo=TipoDocumento.tarjeta_circulacion, folio="TEST-TC-0001")
    repo.guardar("activos", "tractor-1", Activo(activo_id="tractor-1", tenant_id=TENANT, tipo="tractor", placa="TEST001",
                 numero_economico="T-01", config_autotransporte="T3S2", tarjeta_circulacion=tarjeta,
                 verificacion_fisico_mecanica=verif, poliza_responsabilidad_civil=poliza))
    repo.guardar("activos", "caja-1", Activo(activo_id="caja-1", tenant_id=TENANT, tipo="caja", placa="TEST002",
                 numero_economico="C-01", config_autotransporte=None,
                 tarjeta_circulacion=documento(documento_id="doc-tc-0002"),
                 verificacion_fisico_mecanica=documento(documento_id="doc-verif-0002", tipo=TipoDocumento.verificacion_fisico_mecanica),
                 poliza_responsabilidad_civil=documento(documento_id="doc-pol-0002", tipo=TipoDocumento.poliza_responsabilidad_civil)))
    repo.guardar("operadores", "operador-1", Operador(operador_id="operador-1", tenant_id=TENANT, nombre="OPERADOR SINTETICO UNO",
                 curp="TEST900101HCHRST01", licencia_federal=documento(documento_id="doc-lic-0001"), visa_fast=None))
    repo.guardar("viajes", "viaje-1", viaje(mercancias=[Mercancia(clave_prod_serv_cp="10101500", descripcion="Arneses sintéticos",
                 cantidad=10, clave_unidad="H87", peso_en_kg=1200, fraccion_arancelaria="01011001")]))


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
