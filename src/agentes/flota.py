"""La flota como agentes ADK (F3). Sin LLM en los deterministas.

    coordinador (BaseAgent)
    └── flujo (SequentialAgent)
        ├── verificacion (ParallelAgent)
        │   ├── validador    (BaseAgent → cross_check)
        │   └── cumplimiento (BaseAgent → vigencias_query)
        └── seguimiento (BaseAgent → proponer_accion)

`ingesta` llega aquí en cuanto haya Gemini (LlmAgent con sus 4 tools); hoy vive
en agentes/ingesta/pipeline.py. El coordinador como LlmAgent que *explica* la
decisión también espera a Gemini: la decisión misma es `flujo.decidir`, siempre.
"""

import asyncio
from collections.abc import AsyncGenerator

from google.adk.agents import BaseAgent, ParallelAgent, SequentialAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import ConfigDict, Field, TypeAdapter

from agentes.coordinador import flujo
from dominio.enums import EstadoViaje
from dominio.estados import transitar
from dominio.modelos import Bloqueo, Viaje

LISTA = TypeAdapter(list[Bloqueo])


class _Agente(BaseAgent):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    servicios: flujo.Servicios = Field(exclude=True)

    def _viaje(self, ctx: InvocationContext) -> Viaje:
        return Viaje.model_validate(ctx.session.state["viaje"])

    def _evento(self, ctx: InvocationContext, **delta) -> Event:
        ctx.session.state.update(delta)  # visible de inmediato para el siguiente sub-agente
        return Event(author=self.name, invocation_id=ctx.invocation_id, actions=EventActions(state_delta=delta))


class Validador(_Agente):
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        bloqueos, r = flujo.paso_validador(self._viaje(ctx), self.servicios)
        yield self._evento(ctx, bloqueos_validador=LISTA.dump_python(bloqueos, mode="json"), handoff_validador=r.model_dump(mode="json"))


class Cumplimiento(_Agente):
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        bloqueos, r = flujo.paso_cumplimiento(self._viaje(ctx), self.servicios)
        yield self._evento(ctx, bloqueos_cumplimiento=LISTA.dump_python(bloqueos, mode="json"), handoff_cumplimiento=r.model_dump(mode="json"))


class Seguimiento(_Agente):
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        viaje = self._viaje(ctx)
        detectados = LISTA.validate_python(ctx.session.state["bloqueos_validador"] + ctx.session.state["bloqueos_cumplimiento"])
        bloqueos = flujo.paso_seguimiento(viaje, flujo.fusionar(viaje, detectados), self.servicios)
        yield self._evento(ctx, bloqueos=LISTA.dump_python(bloqueos, mode="json"))


class Coordinador(_Agente):
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        s = self.servicios
        viaje = s.repo.obtener("viajes", ctx.session.state["viaje_id"], Viaje)
        if viaje.estado == EstadoViaje.borrador:
            viaje = transitar(viaje, EstadoViaje.validando, ledger=s.ledger, repo=s.repo, actor=flujo.AGENTE)
        yield self._evento(ctx, viaje=viaje.model_dump(mode="json"))
        async for evento in self.sub_agents[0].run_async(ctx):
            yield evento
        final = flujo.decidir(viaje, LISTA.validate_python(ctx.session.state["bloqueos"]), s)
        yield self._evento(ctx, viaje=final.model_dump(mode="json"), decision=final.estado)


def construir_flota(servicios: flujo.Servicios) -> Coordinador:
    verificacion = ParallelAgent(name="verificacion", sub_agents=[
        Validador(name="validador", servicios=servicios), Cumplimiento(name="cumplimiento", servicios=servicios)])
    flujo_agente = SequentialAgent(name="flujo", sub_agents=[verificacion, Seguimiento(name="seguimiento", servicios=servicios)])
    return Coordinador(name="coordinador", servicios=servicios, sub_agents=[flujo_agente])


def procesar_viaje_adk(viaje_id: str, servicios: flujo.Servicios) -> tuple[Viaje, list[Event]]:
    """Corre la flota con el Runner de ADK (sesión en memoria). Devuelve el viaje final y los eventos."""
    runner = InMemoryRunner(agent=construir_flota(servicios), app_name="garita")

    async def _correr() -> list[Event]:
        await runner.session_service.create_session(app_name="garita", user_id="coordinador-trafico",
                                                    session_id=viaje_id, state={"viaje_id": viaje_id})
        mensaje = types.Content(role="user", parts=[types.Part(text=f"procesar {viaje_id}")])
        return [e async for e in runner.run_async(user_id="coordinador-trafico", session_id=viaje_id, new_message=mensaje)]

    eventos = asyncio.run(_correr())
    return servicios.repo.obtener("viajes", viaje_id, Viaje), eventos
