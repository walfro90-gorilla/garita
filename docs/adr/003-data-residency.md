# ADR 003: Frontera de residencia de datos

- **Estado:** aceptado
- **Fecha:** 2026-08-22
- **Decide:** dónde vive la PII, desde dónde se sirve Gemini, y qué cruza entre ambos.

## Contexto

GARITA procesa PII de operadores (CURP, licencia federal, domicilio) y RFC del
transportista. La intención original (SPEC §ADR-03) era que **todo** el pipeline,
incluido Gemini, corriera en `northamerica-south1` (Querétaro). Había que verificar
si Vertex AI sirve Gemini 3.5+ desde esa región antes de diseñar nada en F1.

## Evidencia (verificada 2026-08-22, no de memoria)

### 1. Consulta real al endpoint regional de Vertex AI

```
GET https://northamerica-south1-aiplatform.googleapis.com/v1beta1/publishers/google/models
→ HTTP 404
GET https://northamerica-south1-aiplatform.googleapis.com/v1/projects/<p>/locations/northamerica-south1/models
→ HTTP 404

Misma petición contra us-central1, europe-west9, southamerica-east1,
me-central2, asia-south2, us-east5
→ HTTP 403 (API no habilitada en el proyecto de prueba — el endpoint existe)
```

El host `northamerica-south1-aiplatform.googleapis.com` resuelve en DNS, pero no
sirve los recursos de Vertex AI. 404 vs 403 es la diferencia entre "no existe"
y "existe pero no tienes permiso".

### 2. Documentación oficial (docs.cloud.google.com)

| Fuente | Última actualización | Hallazgo |
|---|---|---|
| Vertex AI · *Deployments and endpoints* | 2026-08-21 | Endpoints regionales en América: `northamerica-northeast1` (Montréal) y `southamerica-east1` (São Paulo). **`northamerica-south1` no aparece.** |
| *Gemini 3.5 Flash* (`gemini-3.5-flash`) | 2026-08-21 | GA desde 2026-05-19, retiro ≥ 2027-05-19. Disponible en: `global`; `us`, `eu`; `northamerica-northeast1`; `europe-west2`, `europe-west3`; `asia-northeast1`, `asia-south1`, `asia-southeast1`. |
| *Gemini 3.6 Flash* (`gemini-3.6-flash`) | 2026-08-21 | GA desde 2026-07-21. Solo `global`, `us`, `eu`. |
| *Gemini 3.7 Flash* (`gemini-3.7-flash`) | 2026-08-21 | GA desde 2026-08-13. Solo `global`, `us`, `eu`. |
| *Gemini 3.5 Pro* | — | La página no existe (404). No hay modelo 3.5 Pro en Vertex AI. |
| Vertex AI · *Data residency* | 2026-08-21 | Regiones con garantía de residencia (reposo + procesamiento ML): US, EU, Brasil, Canadá, Francia, Alemania, Países Bajos, Reino Unido, Australia, India, Japón, Singapur, Corea. **México no está.** |

### 3. Servicios de GCP que SÍ están en `northamerica-south1`

| Servicio | Querétaro | Fuente (fecha) |
|---|---|---|
| Cloud Run | ✅ | run/docs/locations (2026-08-19) |
| Firestore | ✅ | firestore/docs/locations |
| Cloud Storage | ✅ `NORTHAMERICA-SOUTH1` | storage/docs/locations (2026-08-11) |
| Cloud KMS | ✅ (multi-tenant) | kms/docs/locations (2026-08-11) |
| Cloud Build | ✅ | build/docs/locations (2026-08-11) |
| Artifact Registry | ✅ | artifact-registry repo-locations (2026-08-19) |
| Pub/Sub | global, con *message storage policy* por región | — |
| **Cloud Run GPU** | ❌ | run/docs/configuring/services/gpu (2026-08-19): GPUs solo en `us-central1`, `europe-west4`, `asia-southeast1`, `asia-south1/2` |
| **Vertex AI (Gemini)** | ❌ | ver §1 y §2 |

## Decisión

**Gemini 3.5 no se sirve desde México. Se adopta la frontera de redacción como
arquitectura, no como limitación.**

1. **Zona de PII = `northamerica-south1`.** Ahí corren Cloud Run (`api`,
   `ingesta`, servicio Gemma), Firestore, el bucket de originales, el keyring de
   KMS y la *message storage policy* de Pub/Sub. Ningún byte con PII sale de la
   región.
2. **Gemini vía Vertex AI, endpoint `global`, modelo `gemini-3.5-flash`.**
   Se eligen `global` (mayor disponibilidad, menos 429 en el demo) y 3.5 Flash
   (GA, el único 3.x con endpoints regionales; 3.6/3.7 son solo global/us/eu).
   Ambos son variables de entorno (`GOOGLE_CLOUD_LOCATION`, `GARITA_MODELO`),
   no constantes.
3. **Solo payloads ya redactados cruzan a Vertex AI.** El agente `ingesta`
   redacta con Gemma **antes** de cualquier llamada a Gemini. El extractor recibe
   tokens (`[CURP_1]`, `[NOMBRE_1]`), no valores. El mapa token→valor nunca deja
   Firestore en México.
4. **Gemma corre en CPU.** No hay GPU de Cloud Run en México; el redactor usa un
   Gemma pequeño en CPU (tamaño exacto se decide en F2 con medición, no ahora).
   Si la latencia no alcanza, el fallback es redacción determinista por patrón
   (CURP, RFC, placa tienen formato fijo) y Gemma solo para nombres y domicilios.
5. **Si un cliente exige jurisdicción nombrada para el procesamiento ML**, el
   único endpoint regional de 3.5 Flash en América con garantía de residencia es
   `northamerica-northeast1` (Canadá, T-MEC). Es un cambio de variable, no de
   código.

## Consecuencias

- La "frontera" es el argumento arquitectónico más fuerte del proyecto para
  *Best Architectural Design*: se dibuja, se muestra en consola (Cloud Run en
  `northamerica-south1`, trazas de Vertex en `global`) y se explica en 15 s.
- `adk deploy cloud_run` escribe `ENV GOOGLE_CLOUD_LOCATION=<región de Run>` en
  su Dockerfile. Hay que sobreescribirlo con `--set-env-vars` o Gemini recibirá
  404. Está en `scripts/deploy_hello.sh`.
- Todo test de aislamiento de F1 debe incluir: ninguna tool con acceso a PII
  cruda puede ser resuelta por un agente que llame a Gemini.
- El video declara de frente: "Gemini 3.5 Flash through Vertex AI's global
  endpoint; all PII stays in Google Cloud's Mexico region."
