# PROGRESS — bitácora de sesión

> Leer al abrir sesión. Escribir al cerrar. Este archivo es la memoria entre sesiones de Claude Code.
> Si está desactualizado, la siguiente sesión reinventa decisiones ya tomadas.

---

## Estado actual

**Fase:** F3 completa en local + Carta Porte + API (F5 adelantada) + revisión adversarial aplicada. Suite 91 verde. Gemini/Gemma/Pub/Sub/Cloud Run esperan facturación. F0 sigue con 3 criterios bloqueados por facturación.
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

### F1 — completa (22 ago, adelantada un día)
- [x] Modelos Pydantic en `src/dominio/modelos.py`: `DocumentoVigencia`, `Operador`, `Activo`, `Mercancia`, `Bloqueo`, `AccionPropuesta`, `Viaje`, `HallazgoCTPAT`, `HandoffResult`, `EntradaLedger`. `extra="forbid"`. Validadores: confianza < 0.85 o fecha ausente ⇒ `requiere_revision_humana=True`; internacional ⇒ país ≠ MEX; acción aprobada ⇒ humano.
- [x] Máquina de estados `src/dominio/estados.py` con las 4 guardas + cancelado; ledger antes de persistir (test con repo roto).
- [x] Repositorio: `Repository` protocolo + `InMemoryRepository` (probado) + `FirestoreRepository` (adaptador, sin probar hasta facturación).
- [x] Catálogos: 5 snapshots fechados en `catalogos/` con SHA-256 en `catalogos/README.md`. `catalogo_lookup` solo acepta los 3 del recorte; el resto lanza `CatalogoNoDisponible`.
- [x] `xsd_validate`: CartaPorte31.xsd compilado sin red (imports reescritos a snapshots locales, 0.5 s). Fixture sintético `fixtures/carta_porte_31_sintetica.xml` válido contra el XSD oficial.
- [x] `ToolRegistry` con scopes de `<agent_contracts>`; **test de aislamiento** (`tests/test_registry.py`, 17 casos parametrizados): `coordinador`→`storage_read` lanza `ToolFueraDeScope`.
- [x] `LedgerService` (`src/infra/ledger.py`): hash-chain SHA-256 + firma detrás de `Firmador` (ADR-008). `verify()` detecta payload alterado, hash recalculado sin llave, entrada eliminada.
- [x] **AC:** suite verde (52) · viaje recorre borrador→…→cerrado vía código (`tests/test_estados.py`) · aislamiento falla correctamente · `ledger.verify()` detecta alteración.

### F2 — en curso (22 ago, adelantada)
- [x] Corpus sintético: 5 documentos (recorte §5.1) en `fixtures/corpus/` + `manifiesto.json` con transcripción, PII y valores esperados. Generador `scripts/generar_corpus.py` (Pillow/reportlab en `requirements-dev.txt`).
- [x] **ADR-009:** Gemini solo recibe texto redactado; Gemma (multimodal, CPU, MX) transcribe y redacta; `RedactorPatron` segunda capa; `infra.frontera.afirmar_sin_pii` compuerta antes de Vertex.
- [x] Tools de `ingesta`: `storage_read`, `gemma_redact` (Ollama API, mismo contrato local/Cloud Run), `gemini_extract` (google-genai, `response_schema=ExtraccionDocumento`), `firestore_write`.
- [x] `agentes/ingesta/pipeline.ingerir()`: handoff validado con Pydantic, reintento ×3 con el error inyectado, dead-letter al ledger, mapa de tokens a `mapas_redaccion` (MX).
- [x] **AC local:** 5/5 documentos → `DocumentoVigencia` válido · verificación vencida marcada `vencido` · licencia con fecha ilegible → `fecha_vencimiento=None`, `ilegible`, `requiere_revision_humana=True` · traza `frontera.ok` y aserción de que ningún valor PII ni patrón CURP/RFC llegó al extractor.
- [x] **Gemma real probada** (`gemma3:4b`, Ollama local, 100 % CPU, 8 cores con solo 5 GB libres): transcribe bien la licencia borrosa, **omite la línea VIGENCIA en vez de inventarla** (bien), pero (a) deforma la CURP (`TEST900101HCRST01`, falta una letra → la regex ya no la atrapa) y (b) **no redacta**: deja nombre, CURP y domicilio en claro, a lo sumo etiqueta `[CURP]: valor`. Consecuencia aplicada: redacción y compuerta **por etiqueta** (lo que sigue a `CURP:`/`RFC:`/`NOMBRE:`/`DOMICILIO:` se tokeniza sin importar el formato; la frontera rechaza cualquier etiqueta sin token). Test con el hallazgo literal en `tests/test_redaccion.py`.
- [x] **Latencia medida:** visión en CPU = **231 s** de prompt-eval para una imagen (359 tokens) + 12 s de generación; segunda llamada con la misma imagen 0.3 s (caché). Medición bajo presión de memoria; **re-medir en Cloud Run 8 vCPU / 16 GiB** antes de decidir. Si sigue en minutos: el bloque en vivo del video muestra la ingesta ya corrida (logs + Firestore) y la grabación continua empieza en `cumplimiento`; o plan B de ADR-009 con ADR nuevo.
- [ ] Servicio Gemma en Cloud Run `northamerica-south1` — requiere facturación (contenedor Ollama + `gemma3:4b`, CPU).
- [ ] `gemini_extract` contra Vertex AI real — requiere facturación. Código listo, sin probar.
- [ ] Extracción de texto de PDF (póliza de 12 páginas) para Gemma — hoy el PDF se cubre con la transcripción del manifiesto.

### F3 — parte local completa (22 ago, adelantada)
- [x] Tools: `cross_check` (validador: expediente + catálogos), `vigencias_query` (cumplimiento: documentos → `Bloqueo` duro/blando), `proponer_accion` (seguimiento: `AccionPropuesta` idempotente). `registro_por_defecto(repo)` liga las que tocan el expediente.
- [x] Coordinador: `agentes/coordinador/flujo.py` (pasos puros + `procesar_viaje` + `reanudar_tras_aprobacion`) y `agentes/flota.py` (ADK: `Coordinador` → `SequentialAgent(ParallelAgent(validador, cumplimiento), seguimiento)`, corre con `InMemoryRunner`, sin LLM).
- [x] Tolerancia a fallas: `infra/handoff.ejecutar_handoff` (Pydantic, reintento con error inyectado, dead-letter) compartido por ingesta y coordinador · `infra/idempotencia` + `LedgerService.append(idempotency_key)` · `infra/pubsub` (`Publisher`, `InMemoryPublisher`, `PubSubPublisher` sin probar, `handler_dead_letter` escribe `dead_letters` + ledger) · `max_turns`: pendiente, aplica a `LlmAgent`.
- [x] Cola de aprobación: `dominio/acciones.py` (`aprobar`, `rechazar`, `cola_de_aprobacion`), colección `acciones`. `Repository.listar`.
- [x] **ADR-010:** agentes deterministas; dead-letter ⇒ `verificacion_fallida`; la detección nueva manda (aprobar no libera, la evidencia sí); ids deterministas.
- [x] **AC:** caso E2E (`tests/test_flujo.py`): expediente con verificación vencida → viaje `bloqueado` con motivo, evidencia (`…vencida.jpg`) y `renovar_documento` en cola `pendiente_aprobacion` · caos: `vigencias_query` devuelve basura → 3 `handoff inválido` en logs → dead-letter en expediente → bloqueo `verificacion_fallida` + acción `notificar` · reejecutar no duplica (acciones ni decisión en ledger) · toda decisión en el ledger (`decision_coordinador` + transiciones), `verify()` OK · flota ADK produce lo mismo (`tests/test_flota_adk.py`).
- [ ] `ingesta` y `coordinador` como `LlmAgent` (Gemini) — facturación.
- [ ] Pub/Sub real con dead-letter topic en `northamerica-south1` — facturación.
- [x] Constructor de Carta Porte 3.1 (`tools/carta_porte.py`, scope validador): desde `Viaje` + `Activo` + `Operador` + `Transportista`; lanza `CartaPorteIncompleta` con todos los faltantes; válido contra el XSD oficial (nacional e internacional). `IdCCP` determinista (UUID v5 con prefijo CCC).
- [x] Mock de PAC (`infra/pac_mock.py`): valida XSD, UUID `TEST-…`, sello ficticio; contrato `Pac.timbrar(xml) -> Timbre`. Nunca timbra de verdad.
- [x] `flujo.despachar`: `listo → en_ruta`, XML + timbre en `cartas_porte`, hash del XML en el ledger.
- [x] **API** (`src/api/main.py`, monta el servidor ADK + rutas `/api`): `salud`, `GET viajes/{id}` (expediente + acciones + ledger), `POST viajes/{id}/procesar` (flota ADK; si está bloqueado y hay acción aprobada, reanuda), `POST viajes/{id}/despachar`, `GET acciones`, `POST acciones/{id}/aprobar|rechazar`, `PUT documentos/{id}` (alta manual hasta que ingesta tenga Gemini), `GET ledger/verify`. `api/deps.py`: memoria+HMAC local / Firestore+KMS por `GARITA_BACKEND`. `GARITA_SEED_DEMO=1` siembra `dominio/sintetico.py`.
- [x] Demo por HTTP probado con uvicorn real (`curl`): procesar → bloqueado → cola → aprobar (sigue bloqueado) → PUT documento renovado → procesar → listo → despachar (con humano) → en_ruta con UUID `TEST-`.
- [x] **Revisión adversarial** (workflow, 4 lentes, 48 hallazgos, 23 verificados; el resto se agotó la cuota de subagentes y los triagué a mano). Aplicado: ledger se rehidrata del repo y serializa `append` (Cloud Run escala a cero); claves de idempotencia por contenido persistido (reintento tras caída parcial no duplica, test); `flota.Coordinador` comparte la guarda de estado con el síncrono (no deja decisiones fantasma); excepción de tool ⇒ dead-letter; despacho exige humano (ADR-005); `xsd_validate` inyectado en la guarda (el dominio no importa tools); el expediente con PII lo carga el paso del validador, no el coordinador; rechazar ⇒ nueva propuesta; `PUT /documentos` valida tipo y revalida el objeto (antes 500 con operador); la API no monta el servidor de desarrollo de ADK; cola siempre por tenant; `hoy` dinámico; seed no pisa estado; error claro si faltan variables de Firestore/KMS; Carta Porte: `Domicilio` obligatorio, `NumRegIdTrib`/`ResidenciaFiscal` para RFC extranjero, `TipoMateria`, `RFCFigura`, auto-validación XSD antes de devolver, importación marcada como no implementada (pedimento). Descartado con razón en ADR-010 §11.
- [ ] `ctpat_msc_lookup` y `memory_bank` — F4 (GEAP).

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
| 008 | Firma del ledger detrás de `Firmador`: HMAC local en tests, Cloud KMS MAC en producción | **Aceptado — 22 ago** |
| 009 | Gemini solo recibe texto redactado; Gemma transcribe y redacta en México; compuerta `afirmar_sin_pii` | **Aceptado — 22 ago** |
| 010 | Flota ADK determinista; dead-letter bloquea; la evidencia libera, la aprobación no; ids deterministas; despacho por humano; idempotencia por contenido | **Aceptado — 22 ago (addendum)** |

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
4. ~~Dependencia para el corpus~~ — autorizada (Pillow + reportlab como dev-deps).
5. **Modelo por defecto.** ADR-003 fija `gemini-3.5-flash` (GA más antigua, endpoints regionales). Si prefieres `gemini-3.7-flash` (GA 13 ago, solo global/us/eu), es cambiar `GARITA_MODELO`. Decidir antes de grabar el video para que el guion diga el nombre correcto.

---

## Siguiente acción concreta

**Sin facturación, en este orden:**
1. **F3.5 ensayo de video** con lo local: `GARITA_SEED_DEMO=1 PYTHONPATH=src .venv/bin/uvicorn api.main:app --port 8000` y recorrer con curl/`/docs`: procesar → bloqueado (mostrar explicación + evidencia), cola, aprobar, `PUT /documentos` renovado, procesar → listo, despachar con humano → en_ruta, `/ledger/verify`; `pytest -k caos -s` para la prueba de caos. Anotar lo que no se puede mostrar → backlog de F4/F5.
2. **Frontend** (`web/`, Next.js, dos vistas): cola de aprobación (`GET /api/acciones`, botones aprobar/rechazar) y expediente (`GET /api/viajes/{id}`: estado, bloqueos con explicación y evidencia, ledger). Mínimo, sin diseño.
3. **Dockerfile propio** para `src/api` (Python 3.12, `PYTHONPATH=/app/src`, uvicorn) listo para `gcloud run deploy --source` en cuanto haya facturación; variables: `GARITA_BACKEND=firestore`, `GOOGLE_CLOUD_PROJECT`, `GARITA_KMS_KEY_VERSION`, `GOOGLE_CLOUD_LOCATION=global`.
4. Importación (`EntradaSalidaMerc=Entrada`): `DocumentacionAduanera` con pedimento — solo si el guion lo necesita; hoy `CartaPorteIncompleta` explícita.

**Con facturación:** `scripts/deploy_hello.sh` → Gemma en Cloud Run MX → `ingesta` y `coordinador` como `LlmAgent` con `max_turns` → Pub/Sub + dead-letter topic → F4 (Memory Bank, Model Armor).

**F0 pendiente — si la facturación ya está activa:** ejecutar en este orden y pegar el resultado aquí:
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

### 22 ago — sesión 7 (revisión adversarial aplicada)
- 48 hallazgos → 30 cambios aplicados, 8 descartados con razón (ADR-010 §11). 91 tests en 2.8 s. API verificada de nuevo con uvicorn.
- Los subagentes agotaron la cuota de sesión a mitad de la verificación (reset 8 am Chihuahua): 25 hallazgos verificados a mano.

### 22 ago — sesión 6 (Carta Porte + API)
- Modelos ampliados para la Carta Porte: `Transportista`, `Ubicacion`, `Activo.peso_bruto_vehicular/anio_modelo/sub_tipo_rem`, `DocumentoVigencia.emisor`.
- Constructor + PAC mock + despachar + API. 85 tests en 2.5 s. API arrancada con uvicorn y recorrida con curl.
- Revisión adversarial con workflow (4 lentes: SAT/XSD, contratos de agentes, API/residencia, tests/idempotencia) — hallazgos abajo.

### 22 ago — sesión 5 (F3)
- Tools de validador/cumplimiento/seguimiento, flujo del coordinador, flota ADK (`InMemoryRunner`, sin LLM). 76 tests en 2.1 s.
- Handoff genérico compartido con ingesta; idempotencia en ledger; Pub/Sub en memoria + handler de dead-letter; cola de aprobación.
- ADK 2.7.1 deprecó `SequentialAgent`/`ParallelAgent` a favor de `Workflow`, pero `Workflow` no puede ir bajo un `LlmAgent`: se mantienen (ADR-010).

### 22 ago — sesión 4 (F2)
- Corpus sintético generado y verificado visualmente (licencia: vigencia emborronada, foto inclinada).
- ADR-009 decide que Gemini nunca ve imágenes: Gemma transcribe y redacta en MX.
- Pipeline `ingerir()` + 12 tests nuevos (64 total, 1.9 s). Prueba de caos del handoff (JSON inválido ×2 → ok en 3; ×∞ → dead-letter) y de fuga de PII.
- `gemma3:4b` local (Ollama, CPU): transcripción correcta, no inventa la vigencia borrosa, pero no redacta y deforma la CURP. Se añadió redacción/compuerta por etiqueta. 231 s por imagen en CPU con 5 GB libres.

### 22 ago — sesión 3 (F1)
- Catálogos SAT descargados (5 XSD, 9.2 MB) con fecha y SHA-256. `c_FraccionArancelaria` vive en `catComExt.xsd`, no en `catCartaPorte.xsd`.
- Dominio, máquina de estados, ledger (ADR-008), repositorio, tools deterministas, registro de scopes.
- 52 tests verdes en 1.9 s. Fixture Carta Porte 3.1 sintético válido contra XSD oficial al primer intento.
- Hallazgo: `99999999` es una fracción arancelaria válida en el catálogo (genérica); no usarla como "inválida" en tests.

### 22 ago — sesión 2
- gcloud 580.0.0 verificado, autenticado como `wallyagui87@gmail.com`.
- Proyecto `garita-hackathon` creado; 6 APIs habilitadas; `run`/`cloudbuild`/`artifactregistry` rechazadas por falta de facturación.
- ADR-003 resuelto con evidencia: sonda HTTP al endpoint regional (404 vs 403 en otras regiones) + 9 páginas oficiales de docs fechadas 11–21 ago 2026.
- venv con el stack instalado; `requirements.txt` fijado.
- Hello-world ADK + test (`1 passed`) + `adk api_server` local → `GET /list-apps` 200.
- `scripts/deploy_hello.sh`, `scripts/budget_alerts.sh`, `.env.example`.
- README reescrito en inglés. `docs/architecture-v0.md` con Mermaid.
