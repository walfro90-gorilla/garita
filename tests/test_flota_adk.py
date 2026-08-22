"""La flota corre como agentes ADK reales (Sequential + Parallel), sin LLM."""

from agentes.flota import procesar_viaje_adk
from dominio.enums import EstadoViaje as E, MotivoBloqueo
from test_flujo import s  # noqa: F401 — fixture


def test_flota_adk_bloquea_el_viaje(s):  # noqa: F811
    viaje, eventos = procesar_viaje_adk("viaje-1", s)
    assert viaje.estado == E.bloqueado
    assert [b.motivo for b in viaje.bloqueos_duros_abiertos()] == [MotivoBloqueo.documento_vencido]
    autores = [e.author for e in eventos]
    assert autores[0] == "coordinador" and autores[-1] == "coordinador"
    assert {"validador", "cumplimiento", "seguimiento"} <= set(autores)
    assert autores.index("seguimiento") > max(autores.index("validador"), autores.index("cumplimiento"))
    assert eventos[-1].actions.state_delta["decision"] == "bloqueado"
    assert [e.tipo_evento for e in s.ledger.entradas] == ["transicion_viaje", "decision_coordinador", "transicion_viaje"]
