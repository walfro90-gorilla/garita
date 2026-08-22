# ADR 010: Flota ADK con agentes deterministas y reglas del coordinador

- **Estado:** aceptado
- **Fecha:** 2026-08-22

## Contexto

F3 pide los cinco agentes orquestados con ADK, los cuatro mecanismos de
tolerancia a fallas y "el bloqueo" como producto. No hay facturación: no hay
Gemini. Y aunque la hubiera, SPEC §3 exige que `validador` sea determinista y
que `cumplimiento` y `seguimiento` no tengan espacio para alucinar.

## Decisiones

1. **`validador`, `cumplimiento` y `seguimiento` son `BaseAgent` de ADK sin
   LLM.** Envuelven funciones puras (`agentes/coordinador/flujo.py`) que llaman
   tools por `ToolRegistry` dentro de su scope. Un LLM no decide si un camión
   sale; una regla sí. Gemini entra donde hay ambigüedad real: extracción de
   documentos (`ingesta`) y, más adelante, la explicación de la decisión del
   `coordinador` en lenguaje del coordinador de tráfico.
2. **Orquestación:** `coordinador` → `SequentialAgent(ParallelAgent(validador,
   cumplimiento), seguimiento)`. ADK 2.7.1 marca `SequentialAgent` y
   `ParallelAgent` como deprecados a favor de `Workflow` (grafo de nodos), pero
   `Workflow` "aún no puede ser sub-agente de un `LlmAgent`", que es exactamente
   lo que el coordinador será cuando Gemini explique decisiones. Se mantienen
   los agentes clásicos; se migra a `Workflow` cuando ADK lo permita bajo un
   `LlmAgent`, en un commit aislado.
3. **Un sub-agente que va a dead-letter bloquea el viaje.** Si `cumplimiento`
   o `validador` no producen una lista válida de `Bloqueo` tras 3 intentos, el
   coordinador crea un bloqueo duro `verificacion_fallida`. Lo que no se pudo
   verificar no sale. La falla queda en `dead_letters` y en el ledger.
4. **La detección nueva manda; aprobar no hace legal al camión.** Al reprocesar
   un viaje, los bloqueos que ya no se detectan desaparecen y los re-detectados
   se reabren aunque un humano haya aprobado la acción. La aprobación autoriza
   el *efecto externo* (ADR-005: pedir la renovación); solo la evidencia nueva
   (el documento renovado ingresado) libera el viaje. La acción ya propuesta se
   reutiliza para no duplicar.
5. **Ids deterministas = idempotencia gratis.** `bloqueo_id` deriva de
   `(viaje, motivo, documento|clave)` y `accion_id` de `bloqueo_id`. Además la
   decisión del coordinador se escribe al ledger con
   `idempotency_key = sha256(viaje_id + "decision" + hash(bloqueos))`, y
   `LedgerService.append` devuelve la entrada existente si la clave se repite.

## Consecuencias

- La prueba de caos del video (SPEC §F3) es `tests/test_caos_cumplimiento_devuelve_basura`:
  tres reintentos en los logs, dead-letter en el expediente, viaje bloqueado
  con `verificacion_fallida` y una acción `notificar` en la cola.
- `flujo.procesar_viaje` (síncrono) y `flota.procesar_viaje_adk` (ADK) producen
  el mismo resultado y se prueban ambos; la API de F5 usa el de ADK.
- Pendiente para cuando haya Gemini: `ingesta` como `LlmAgent` con sus 4 tools,
  `coordinador` como `LlmAgent` que explica pero no decide, `max_turns` por
  sub-agente en ADK.
