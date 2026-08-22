# PROGRESS — bitácora de sesión

> Leer al abrir sesión. Escribir al cerrar. Este archivo es la memoria entre sesiones de Claude Code.
> Si está desactualizado, la siguiente sesión reinventa decisiones ya tomadas.

---

## Estado actual

**Fase:** F0 · Fundación
**Fecha:** 22 ago 2026
**Días restantes hasta el envío (dom 30 ago):** 8

---

## Criterios de aceptación

### F0 — en curso
- [ ] Proyecto GCP creado, facturación activa
- [ ] Alertas de presupuesto a $25 / $60 / $120
- [ ] Formulario de créditos enviado (⚠️ cierra vie 28 ago, 12:00 PM PT)
- [ ] Borrador del formulario de submission abierto en Devpost
- [ ] Repo público, primer commit fechado
- [ ] README con declaración de "no preexisting code"
- [ ] **ADR-003 resuelto:** disponibilidad de Gemini 3.5 en `northamerica-south1`
- [ ] ADK hello-world respondiendo 200 en Cloud Run, región Querétaro
- [ ] Captura de consola mostrando la región
- [ ] Diagrama de arquitectura v0 (herramienta de diseño, no entregable)

---

## Decisiones tomadas

| ADR | Decisión | Estado |
|---|---|---|
| 001 | ADK-Python sobre Genkit | Aceptado |
| 002 | Una sola nube — sin Supabase ni Vercel | Aceptado |
| 003 | Frontera de residencia de datos | **Abierto — bloquea F1** |
| 004 | Persistencia ≠ memoria (Firestore vs Memory Bank) | Aceptado |
| 005 | Compuerta humana en todo efecto externo | Aceptado |
| 006 | Inmutabilidad por hash-chain + KMS, sin blockchain | Aceptado |
| 007 | Tenant-shaped desde el primer commit | Aceptado |

---

## Bloqueos y preguntas para el humano

1. **ADR-003.** ¿Gemini 3.5 está servido desde `northamerica-south1`? Si no, la arquitectura queda: PII e ingesta en región México, solo payloads redactados cruzan a la región de Vertex. Se documenta como decisión, no como limitación.
2. **Categoría CTPAT de Café 57.** ¿Cruza físicamente el puente (Highway Carrier: requiere SCAC + DOT) o entrega en patio para transfer (Long Haul mexicano: requiere número SCT)? Cambia campos del modelo `Tenant`.
3. **Escala de la flota.** Número aproximado de unidades y operadores — para la narrativa del video, no para la arquitectura.

---

## Siguiente acción concreta

Resolver ADR-003: consultar disponibilidad regional de Gemini 3.5 en Vertex AI para `northamerica-south1`, escribir el ADR con el resultado y su consecuencia arquitectónica, commitear.

---

## Bitácora

### 22 ago — sesión 1
- Repo inicializado. Estructura de archivos creada.
- `CLAUDE.md`, `docs/SPEC.md` y `docs/PROGRESS.md` en su lugar.
