# PROGRESS — bitácora de sesión

> Leer al abrir sesión. Escribir al cerrar. Este archivo es la memoria entre sesiones de Claude Code.
> Si está desactualizado, la siguiente sesión reinventa decisiones ya tomadas.

---

## Estado actual

**Fase:** F0 · Fundación — código listo, deploy bloqueado por facturación
**Fecha:** 22 ago 2026
**Días restantes hasta el envío (dom 30 ago):** 8

**Identidades en uso (no mezclar):**
- gcloud: `wallyagui87@gmail.com` · proyecto `garita-hackathon` (número `557054263872`)
- GitHub: `walfro90-gorilla` · https://github.com/walfro90-gorilla/garita (público)
- La config global de gcloud apunta a `cafe57-analytics` (proyecto inexistente). Todos los scripts pasan `--project` explícito; no se tocó la config global.

---

## Criterios de aceptación

### F0 — en curso
- [x] Proyecto GCP creado: `garita-hackathon` (22 ago 06:59 UTC). APIs habilitadas sin facturación: aiplatform, firestore, pubsub, cloudkms, storage, billingbudgets.
- [ ] **Facturación activa** — ⛔ pendiente del humano (ver abajo). Ambas cuentas de facturación existentes están CERRADAS (`013DD2-22DA75-5AAD71`, `01CEA2-C30F6A-70F055`). Sin esto no se pueden habilitar `run`, `cloudbuild` ni `artifactregistry`.
- [ ] Alertas de presupuesto a $25 / $60 / $120 — script listo (`scripts/budget_alerts.sh`), requiere facturación.
- [ ] Formulario de créditos enviado (⚠️ cierra vie 28 ago, 12:00 PM PT) — pendiente del humano.
- [ ] Borrador del formulario de submission abierto en Devpost — pendiente del humano.
- [x] Repo público, primer commit fechado (`12cbcee`, 2026-08-22 00:34 -0600).
- [x] README (en inglés) con declaración de "no preexisting code".
- [x] **ADR-003 resuelto:** Gemini 3.5 **NO** se sirve desde `northamerica-south1`. Evidencia verificable en `docs/adr/003-data-residency.md`.
- [ ] ADK hello-world respondiendo 200 en Cloud Run, región Querétaro — código y test listos (`src/agentes/hello`, `tests/test_hello.py`, 1 passed), `adk api_server` local responde 200 en `/list-apps`. Deploy bloqueado por facturación; `scripts/deploy_hello.sh` lo hace en un comando.
- [ ] Captura de consola mostrando la región — tras el deploy.
- [x] Diagrama de arquitectura v0 — `docs/architecture-v0.md` (Mermaid, con la frontera de redacción).

---

## Decisiones tomadas

| ADR | Decisión | Estado |
|---|---|---|
| 001 | ADK-Python sobre Genkit | Aceptado |
| 002 | Una sola nube — sin Supabase ni Vercel | Aceptado |
| 003 | Frontera de residencia de datos: PII en `northamerica-south1`; Gemini 3.5 Flash vía endpoint `global` con payloads redactados; Gemma en CPU (no hay GPU de Cloud Run en México) | **Aceptado — 22 ago** |
| 004 | Persistencia ≠ memoria (Firestore vs Memory Bank) | Aceptado |
| 005 | Compuerta humana en todo efecto externo | Aceptado |
| 006 | Inmutabilidad por hash-chain + KMS, sin blockchain | Aceptado |
| 007 | Tenant-shaped desde el primer commit | Aceptado |

Hallazgos colaterales de ADR-003 que afectan fases posteriores:
- No existe Gemini 3.5 **Pro**. Modelos 3.x GA en Vertex: `gemini-3.5-flash` (05/2026), `gemini-3.5-flash-lite` y `gemini-3.6-flash` (07/2026), `gemini-3.7-flash` (13 ago 2026). Solo 3.5 Flash tiene endpoints regionales; el resto solo `global`/`us`/`eu`. El "Pro solo para razonamiento final" del SPEC §riesgos no aplica: usar 3.7 Flash si se quiere más razonamiento.
- `adk deploy cloud_run` (ADK 2.7.1) genera Dockerfile con `python:3.11-slim` y `ENV GOOGLE_CLOUD_LOCATION=<región de Run>`. Para el servicio real de `src/api` conviene Dockerfile propio (3.12) en F3; el hello-world usa el generado con override de env.
- Versiones fijadas en `requirements.txt`: google-adk 2.7.1, google-genai 2.19.0, pydantic 2.13.4, lxml 6.1.2, pytest 9.1.1, etc.

---

## Pendiente del humano — instrucciones paso a paso

### 1. Activar facturación (bloquea todo lo demás de F0)
1. Abrir https://console.cloud.google.com/billing con `wallyagui87@gmail.com`.
2. Reabrir una cuenta cerrada ("My Billing Account" `01CEA2-C30F6A-70F055` → *Reopen billing account*) **o** crear una nueva con tarjeta.
3. Vincular el proyecto (sustituir `XXXXXX-XXXXXX-XXXXXX` por el ID de la cuenta abierta):
   ```bash
   gcloud billing projects link garita-hackathon --billing-account=XXXXXX-XXXXXX-XXXXXX
   gcloud billing projects describe garita-hackathon --format='value(billingEnabled)'   # → True
   ```
4. Alertas de presupuesto:
   ```bash
   scripts/budget_alerts.sh XXXXXX-XXXXXX-XXXXXX
   ```
5. Deploy del hello-world y captura:
   ```bash
   scripts/deploy_hello.sh
   ```
   El script imprime la URL `.run.app`, hace `curl` a `/list-apps` (esperado: `HTTP 200`) y la URL de la consola. Tomar captura donde se vea `northamerica-south1` y guardarla en `docs/capturas/f0-cloud-run-queretaro.png`.

### 2. Formulario de créditos de GCP (cierra **vie 28 ago, 12:00 PM PT**)
- La URL no está en `SPEC.md`. Buscarla en el correo de confirmación de Devpost / página del hackathon ("Google Cloud credits").
- Datos que pide normalmente: correo de la cuenta GCP (`wallyagui87@gmail.com`), ID de proyecto (`garita-hackathon`), número de proyecto (`557054263872`).

### 3. Borrador en Devpost
1. https://devpost.com → hackathon *All Things Agentic* → **Start a submission** (se guarda como borrador; ediciones ilimitadas hasta el cierre).
2. Campos conocidos:
   - Project start date: **August 22, 2026** (coincide con el primer commit `12cbcee`).
   - Google SDK used: **Google ADK (Python) + Vertex AI (Gemini 3.5 Flash)**.
   - Repo URL: https://github.com/walfro90-gorilla/garita
   - Hosted project URL: la `.run.app` que imprime `scripts/deploy_hello.sh` (actualizar en F5 con la URL real).
   - README con instrucciones reproducibles: sí (sección *Run locally*).
3. Guardar borrador; no enviar.

---

## Bloqueos y preguntas para el humano

1. ~~ADR-003~~ — resuelto.
2. **Categoría CTPAT de Café 57.** ¿Cruza físicamente el puente (Highway Carrier: requiere SCAC + DOT) o entrega en patio para transfer (Long Haul mexicano: requiere número SCT)? Cambia campos del modelo `Tenant`.
3. **Escala de la flota.** Número aproximado de unidades y operadores — para la narrativa del video, no para la arquitectura.
4. **Modelo por defecto.** ADR-003 fija `gemini-3.5-flash` (GA más antigua, endpoints regionales). Si prefieres `gemini-3.7-flash` (GA 13 ago, solo global/us/eu), es cambiar `GARITA_MODELO`. Decidir antes de grabar el video para que el guion diga el nombre correcto.

---

## Siguiente acción concreta

**Si la facturación ya está activa:** ejecutar en este orden y pegar el resultado aquí:
```bash
gcloud billing projects describe garita-hackathon --format='value(billingEnabled)'
scripts/budget_alerts.sh <BILLING_ACCOUNT_ID>
scripts/deploy_hello.sh
```
Luego marcar los tres criterios de F0 restantes, commitear la captura como `F0: hello-world en Cloud Run Querétaro` y arrancar **F1 · Núcleo determinista** (SPEC §F1, D2): `src/dominio/` con los modelos Pydantic de `CLAUDE.md <data_models>`, enums, máquina de estados con guardas y tests; primero el test de aislamiento de tools por agente.

**Si la facturación sigue sin activar:** no esperar. Arrancar F1 igual — `src/dominio/` y sus tests no necesitan GCP. El deploy de F0 se hace en cuanto haya facturación, en paralelo.

---

## Bitácora

### 22 ago — sesión 1
- Repo inicializado. Estructura de archivos creada.
- `CLAUDE.md`, `docs/SPEC.md` y `docs/PROGRESS.md` en su lugar.

### 22 ago — sesión 2
- gcloud 580.0.0 verificado, autenticado como `wallyagui87@gmail.com`.
- Proyecto `garita-hackathon` creado; 6 APIs habilitadas; `run`/`cloudbuild`/`artifactregistry` rechazadas por falta de facturación.
- ADR-003 resuelto con evidencia: sonda HTTP al endpoint regional (404 vs 403 en otras regiones) + 9 páginas oficiales de docs fechadas 11–21 ago 2026.
- venv con el stack instalado; `requirements.txt` fijado.
- Hello-world ADK + test (`1 passed`) + `adk api_server` local → `GET /list-apps` 200.
- `scripts/deploy_hello.sh`, `scripts/budget_alerts.sh`, `.env.example`.
- README reescrito en inglés. `docs/architecture-v0.md` con Mermaid.
