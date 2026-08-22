# GARITA v2 — Spec Técnico de Ejecución

**Hackathon:** All Things Agentic (Google / Devpost)
**Categoría objetivo:** Fortified Enterprise Fleet · **Fallback:** Taskmaster
**Organización:** Gorilla Labs · **Cierre:** 31 ago 2026, 18:00 hora Juárez
**Cliente ancla:** Café 57 — transportista con equipo propio, mueve material de maquiladoras de México a EE.UU.
**Calendario recalibrado:** 22 ago 2026 · 9 días de ejecución + lunes de cierre

---

## 0. Contexto para el agente ejecutor

Fuente de verdad. Ejecución por fases secuenciales. Cada fase tiene criterios de aceptación verificables. No avanzar sin que los AC de la fase anterior pasen.

Reglas duras del hackathon:

1. Todo el código se escribe durante el periodo de submission (3–31 ago 2026). Declarar cualquier código preexistente en el README.
2. Obligatorio: Gemini 3.5+ vía Gemini API o Vertex AI · un framework de agentes de Google (ADK / GenAI SDK / Antigravity SDK / Genkit) · un servicio de infraestructura de GCP.
3. 60% del score es arquitectura (30%) + demo y documentación (30%).
4. El video debe mostrar ejecución en vivo, sin editar, con prueba visual de Google Cloud.

---

## 1. El problema

Café 57 opera equipo propio moviendo material de maquiladoras hacia EE.UU. Para que un tractor salga del patio, tres capas de papel deben estar simultáneamente correctas.

**La tesis, con dato de industria:** cerca del 80% de los permisionarios federales mexicanos son microempresas con alta madurez operativa en ruta y baja madurez documental. En CTPAT, 7 de cada 10 rechazos son por documentación, no por seguridad física.

> **Los camiones corren bien. Lo que los mata es el papeleo.**

### Los tres relojes

| Ciclo | Horizonte | Contenido |
|---|---|---|
| **Viaje** | Minutos | CFDI tipo "I" con Complemento Carta Porte 3.1, `TranspInternac="Sí"`, nodo `RegimenesAduaneros`, fracción arancelaria (`c_FraccionArancelaria`), pedimento, `EntradaSalidaMerc`, `ViaEntradaSalida`, inspección de 17 puntos, sello ISO 17712 |
| **Vigencias** | Semanas–meses | Permiso SICT (`c_TipoPermiso`, ej. TPAF01), tarjeta de circulación federal por unidad, verificación físico-mecánica, póliza de responsabilidad civil, licencia federal tipo E por operador, visa/FAST |
| **Certificación** | Años | Evidencia acumulada contra CTPAT MSC de transportista mexicano, revalidación, gestión de socios comerciales |

El mismo hecho físico (esta licencia, esta póliza, esta verificación) alimenta los tres. **Capturar una vez, usar tres veces, probar para siempre.**

### Costo de fallar

- Art. 84 fracc. IV CFF: $19,700 a $112,650 MXN por traslado sin Carta Porte exigible
- Flete mal documentado = no deducible
- Art. 103 y 108 CFF: contrabando presunto y defraudación fiscal, 3 meses a 9 años
- Art. 184 Ley Aduanera en comercio exterior: pérdida del bien
- SAT en 2026: verificadores en corredores carreteros, 347 multas en abril por $52M MXN
- ~90% de los errores vienen de captura manual

### El "Unlikely Hero"

El **coordinador de tráfico** de una transportista fronteriza. No es product manager ni analista. Es la persona que a las 5 de la mañana decide si un tractor sale o no, con una carpeta física y memoria.

---

## 2. Decisiones de arquitectura

### ADR-01 · ADK-Python sobre Genkit
Los criterios de juicio están redactados en vocabulario de ADK. Se paga el costo de salir de TypeScript. Frontend en Next.js.

### ADR-02 · Una sola nube
Sin Supabase ni Vercel. Firestore para estado, Cloud Run para cómputo, Pub/Sub para eventos, Cloud KMS para firma, Cloud Storage con retention policy para el archivo inmutable.

### ADR-03 · Frontera de residencia de datos
Todo lo que toca PII (CURP, licencia federal, domicilio del operador, RFC) vive en `northamerica-south1` (Querétaro): Cloud Run, Firestore y el servicio Gemma. Solo payloads **ya redactados** cruzan hacia la región donde se sirve Gemini en Vertex AI.

> ⚠️ **Verificar en D1:** disponibilidad de Gemini 3.5 en `northamerica-south1`. Si NO está, documentarlo como decisión de diseño, no esconderlo — la frontera de redacción se vuelve el argumento arquitectónico más fuerte del proyecto. Si SÍ está, todo el pipeline queda en territorio nacional y se muestra en consola.

### ADR-04 · Persistencia ≠ memoria
- **Expediente** (Firestore): estado de negocio durable y auditable. El viaje, el activo, el operador.
- **Memory Bank** (GEAP): memoria del agente entre sesiones. A quién ya se le pidió la renovación, qué canal funcionó, qué prometió el verificentro hace tres semanas.

### ADR-05 · Compuerta humana en todo efecto externo
Ningún agente notifica, agenda ni escribe a sistemas externos sin aprobación. Se propone, se persiste como `pending_approval`, un humano confirma.

### ADR-06 · Inmutabilidad sin blockchain
Ledger encadenado por hash: cada entrada guarda el hash de la anterior, se firma con Cloud KMS y se archiva en Cloud Storage con retention policy (WORM). Verificable, auditable, 100% GCP.

**No se usa blockchain ni smart contracts.** En México la validez jurídica de la conservación documental la da la NOM-151-SCFI-2016 mediante constancia de un Prestador de Servicios de Certificación acreditado por la Secretaría de Economía (sello RFC 3161 + SHA-256, vigencia mínima 10 años). Un smart contract no agrega peso legal ante el SAT ni ante un tribunal mexicano. El ledger de GARITA es el sustrato técnico sobre el que una constancia NOM-151 se emitiría en producción — se documenta como escalamiento futuro.

### ADR-07 · Tenant-shaped desde el día uno
Todo documento en Firestore lleva `tenant_id`, aunque se opere con un solo tenant y sin multi-tenancy real. Media hora ahora, semanas ahorradas al comercializar.

---

## 3. La flota

| Agente | Responsabilidad | Puede tocar |
|---|---|---|
| `coordinador` | Orquestador raíz. Planea, delega, decide si un viaje sale. Nunca ve documentos crudos ni PII. | Sub-agentes y expediente |
| `ingesta` | Extracción multimodal de lo desordenado: permisos escaneados, pólizas en PDF, fotos de la inspección de 17 puntos, licencia fotografiada con celular. Redacción PII con Gemma **antes** de cualquier llamada a Gemini. | Cloud Storage, Gemma, Firestore |
| `validador` | Valida el Complemento Carta Porte contra **XSD oficial y catálogos SAT reales**. Determinista, sin espacio para alucinación. | Solo tools deterministas + expediente |
| `cumplimiento` | El reloj. Estado rodante de vigencias por activo y por operador. Acumula evidencia contra CTPAT MSC. Justifica Memory Bank. | Expediente + Memory Bank + catálogo MSC |
| `seguimiento` | Larga duración. Persigue renovaciones durante semanas. Escala. Propone comunicaciones, nunca las envía solo. | Memory Bank + cola de aprobación |

`ledger` es un **servicio**, no un agente: append-only, firma KMS, verificación de cadena.

**Separación de concerns aplicada con test:** `coordinador` no tiene acceso a Cloud Storage. `validador` no tiene acceso a red. Se verifica automáticamente.

### Catálogos SAT a descargar en F1
`c_ClaveProdServCP` · `c_ConfigAutotransporte` · `c_TipoPermiso` · `c_FraccionArancelaria` · `c_RegimenAduanero` · `c_MaterialPeligroso` · `c_ClaveUnidad`

Validar contra catálogos oficiales en vez de reglas inventadas es un punto directo en "Architectural Discipline".

---

## 4. Tolerancia a fallas

Los jueces preguntan literalmente qué pasa si un worker entra en loop o alucina.

1. **Contrato de handoff validado.** Todo output de sub-agente se valida contra Pydantic. Si falla, reintento con el error inyectado en el prompt. A la tercera, dead-letter.
2. **Presupuesto de turnos.** `max_turns` por sub-agente. Al excederlo, `failed_budget_exceeded`.
3. **Idempotencia.** Toda tool con efecto lateral recibe `idempotency_key` derivada de `(viaje_id, paso_id, hash_input)`. Reejecutar no duplica.
4. **Dead-letter en Pub/Sub** con handler que escribe la falla al expediente.

Inyectar un fallo a propósito en el video y mostrar la recuperación.

---

## 5. Fases de ejecución

### 5.1 · Recortes por calendario comprimido

El plan original asumía 14 días. Hay 9. Estos recortes se aplican **desde el inicio**, no se negocian a media semana:

- **Catálogos SAT: 3, no 7.** Solo `c_ClaveProdServCP`, `c_TipoPermiso`, `c_FraccionArancelaria`. Los demás quedan como stub documentado.
- **Corpus sintético: 5 documentos, no 9.** Licencia federal fotografiada (borrosa), verificación físico-mecánica vencida, permiso SICT escaneado, póliza en PDF, hoja de 17 puntos manuscrita. Son los que sostienen la demo.
- **GEAP: Memory Bank + Model Armor son compromiso. Agent Registry y Observability solo si D6 cierra temprano.**
- **Bono Veo: descartado.** Gemma + blog + post social = +0.6 y alcanza.
- **Sin frontend elaborado.** Una vista de cola de aprobación y una de expediente. Nada más.

Lo que **no** se recorta: el ledger de hashes, el bloqueo del viaje, la prueba de caos, y los 2 días de F6.


### F0 · Fundación — D1 (SÁB 22 AGO — hoy)

- Proyecto GCP nuevo, facturación, alertas de presupuesto a $25 / $60 / $120
- Verificar Gemini 3.5 en `northamerica-south1` → escribir `docs/adr/003-data-residency.md`
- Repo público, primer commit fechado, README con declaración de "no preexisting code"
- ADK hello-world desplegado en Cloud Run, región Querétaro
- **Abrir el formulario de submission en Devpost y guardar borrador.** Admite ediciones ilimitadas antes del cierre. Pide URL del proyecto hospedado, qué SDK de Google se usó, si el README tiene instrucciones reproducibles, y **la fecha en que se inició el proyecto** — este último campo es el mecanismo de control de la regla "New Projects Only", y debe coincidir con la fecha del primer commit.
- **Diagrama de arquitectura v0.** No como entregable, como herramienta de diseño. Si no se puede dibujar con claridad cómo Gemini se conecta al backend, dónde vive el estado y qué servicios de GCP corren, el diseño necesita otra pasada — y hoy es barato descubrirlo.

**AC:** `curl` a la URL `.run` responde 200 · captura de consola con `northamerica-south1` · alertas activas · ADR-03 resuelto · borrador de submission guardado · diagrama v0 legible por un tercero.

---

### F1 · Núcleo determinista — D2 (dom 23 ago)

Sin LLM. Esqueleto que los agentes van a manipular.

- Modelos Pydantic: `Viaje`, `Activo`, `Operador`, `DocumentoVigencia`, `HallazgoCTPAT`, `AccionPropuesta`, `HandoffResult`, `EntradaLedger`
- Repositorio Firestore + máquina de estados del viaje (`borrador → validando → bloqueado | listo → en_ruta → cerrado`)
- Descarga y parseo de catálogos SAT a estructuras consultables
- Validador de XSD del Complemento Carta Porte 3.1
- Registro de tools con scopes por agente + test de aislamiento
- Servicio `ledger` con firma KMS y verificación de cadena

**AC:** suite verde · un viaje recorre todos los estados vía código · el test de aislamiento falla correctamente si `coordinador` intenta llamar una tool de Storage · `ledger.verify()` detecta una entrada alterada a mano.

---

### F2 · Ingesta multimodal + Gemma — D3 (lun 24 ago)

Generar **corpus sintético desordenado** (datos falsos, siempre):

- 2 permisos SICT escaneados con calidad distinta
- 1 póliza de RC en PDF de 12 páginas
- 2 licencias federales tipo E fotografiadas con celular, una con fecha de vencimiento borrosa
- 1 tarjeta de circulación federal
- 1 comprobante de verificación físico-mecánica **vencido**
- 1 hoja de inspección de 17 puntos llena a mano
- 1 correo con adjunto de la maquila con datos del embarque

Luego:

- Servicio Gemma en Cloud Run (región México): detección y redacción de PII → texto redactado + mapa de tokens
- Agente `ingesta`: documento → Gemma → Gemini multimodal → esquema estructurado con fecha de vencimiento extraída

**AC:** los 9 documentos procesados a esquema válido · **traza de logs que demuestra que ningún PII sin redactar salió de la región** (toma del video) · la verificación vencida queda marcada correctamente.

---

### F3 · Flota multi-agente — D4–D5 (mar 25 – mié 26)

- Los 5 agentes con sus tools y scopes
- Orquestación ADK: secuencial para el flujo del viaje, paralelo para `validador` + `cumplimiento`
- Los 4 mecanismos de tolerancia a fallas
- Pub/Sub para disparo asíncrono + dead-letter
- Cola de aprobación humana en Firestore
- **El bloqueo:** `coordinador` niega la salida de un viaje con motivo, evidencia y acción propuesta

**AC:** caso completo de extremo a extremo, de documentos desordenados a viaje bloqueado con renovación propuesta pendiente de aprobación · **prueba de caos:** forzar a `cumplimiento` a devolver JSON inválido y mostrar reintento y dead-letter en logs · reejecutar un paso no duplica · toda decisión quedó escrita en el ledger.

**🔴 Punto de no retorno.** Si al cierre de D5 (mié 26) esto no corre end-to-end, congelar alcance y saltar a F5.

---

### F3.5 · Ensayo de video — D5 por la noche (mié 26), 90 minutos

**Fase nueva, y probablemente la de mayor retorno de todo el plan.**

Grabar un video de 4 minutos completo, feo, con lo que exista en ese momento. Sin editar, sin guion pulido, sin audio decente. El objetivo no es el video: es descubrir qué evidencia falta **mientras todavía hay dos días para construirla**.

Justificación: los organizadores confirmaron por escrito que **los jueces no están obligados a descargar ni ejecutar el proyecto** y pueden calificar completamente desde el video, la descripción y el repo. Eso convierte la evidencia en el producto, y el código en el insumo. Casi todos los participantes van a descubrir sus huecos de evidencia el día 13, cuando ya no se pueden llenar.

**AC:** existe un archivo de 4 minutos · lista escrita de todo lo que no se pudo mostrar · esa lista se convierte en el backlog de F4 y F5.

---

### F4 · Capa GEAP — D6 (jue 27)

Orden por relación valor/riesgo, **priorizando lo que el ensayo reveló como hueco**:

1. **Memory Bank** — `seguimiento` recuerda entre sesiones separadas por semanas. Demo: tres sesiones con saltos de tiempo simulados sobre la misma renovación.
2. **Model Armor** — guardrails en el borde de ingesta. Demo: documento con inyección de prompt embebida, bloqueado.
3. **Agent Registry** — agentes publicados con versión, descubribles por tráfico, mantenimiento y contabilidad.
4. **Agent Observability** — trazas OpenTelemetry de la cadena de razonamiento.
5. **Agent Identity / Gateway** — solo si sobra tiempo real.

**AC:** cada componente tiene una captura o toma de video que lo prueba. Si no se puede mostrar, no cuenta.

> D6 (27 ago, 9:00 AM o 9:00 PM PT): webinar *Architecting Agent Memory*. Cae exacto en esta fase.

**🔵 Decisión de categoría al cierre de D6 (jue 27).** Con Memory Bank + Model Armor + Registry funcionando → Fleet. Con menos de dos → Taskmaster, y se reescribe la narrativa alrededor del workflow autónomo.

---

### F5 · Despliegue y evidencia — D7 (vie 28 ago) · **corte de features**

- Todos los servicios en Cloud Run, `min-instances=0`, tope de `max-instances`
- Ejecución completa en producción con trazas visibles
- **Grabar toda la evidencia mientras está caliente**, antes de apagar nada
- Endpoints protegidos

**AC:** ejecución completa en producción · trazas en Cloud Trace · capturas de Cloud Run, Vertex AI y Firestore con región visible · gasto acumulado bajo $60.

---

### F6 · Narrativa — D8–D9 (sáb 29 – dom 30)

**Diagrama de arquitectura** (v1 sobre el v0 del D1). Los organizadores pidieron tres cosas literales, y deben verse sin esfuerzo:
1. Cómo Gemini se conecta al backend
2. Dónde vive el estado
3. Qué servicios de Google Cloud corren

Encima de eso, la frontera de residencia de datos y los tres relojes. Compite por "Best Architectural Design" ($5,000, 2 ganadores).

**README escrito para ser leído, no solo ejecutado.** Como los jueces pueden calificar sin correr nada, el repo es un documento de venta: diagrama embebido, capturas del sistema funcionando, y el spin-up redactado como si un desconocido tuviera que levantarlo desde cero.

**Video, 4 minutos, en inglés:**

| Tiempo | Contenido |
|---|---|
| 0:00–0:25 | La garita. El coordinador de tráfico a las 5 AM. "Los camiones corren bien; lo que los mata es el papeleo." La cifra de multas. |
| 0:25–0:40 | **Declaración explícita del stack.** "GARITA runs on Gemini 3.5 Flash through Vertex AI, orchestrated with Google's Agent Development Kit, on Cloud Run in Google Cloud's Mexico region." Dicho de frente, no enterrado. Los organizadores lo pidieron con esas palabras. |
| 0:40–1:00 | Diagrama: tres relojes, una flota de agentes, la frontera de datos. |
| 1:00–2:40 | Ejecución real del agente. Licencia fotografiada con celular entra → Gemma redacta → Gemini extrae → `cumplimiento` cruza contra el viaje → **el agente bloquea la salida** → renovación propuesta en cola de aprobación. Logs y Firestore visibles. **La URL `.run` visible en la barra del navegador durante todo el bloque**, para que la prueba de Google Cloud sea continua y no dependa de que el juez llegue al final. |
| 2:40–3:10 | Prueba de caos + verificación del ledger recalculando la cadena de hashes. |
| 3:10–3:40 | Memory Bank: tres sesiones separadas por semanas sobre la misma renovación. |
| 3:40–4:00 | Consola GCP: Cloud Run en `northamerica-south1`, trazas de Vertex AI. |

**Reglas de edición (aclaradas por los organizadores):** se permite cortar pantallas de carga y pasos de setup, pegar credenciales en vez de teclearlas, y acelerar ligeramente la voz. Lo que **no** se permite es simular la ejecución. Regla de trabajo: el trabajo del agente va en una toma verificable y continua; solo se recorta el tiempo muerto alrededor.

**Narración:** los organizadores avalaron explícitamente el uso de voz sintética antes que silencio o murmullo. Intentar primero con voz propia — la historia del héroe fronterizo pega más fuerte contada por alguien de la frontera. Voz AI como respaldo, sin culpa.

**Subir el video con un día de anticipación.** YouTube y Vimeo pueden tardar horas en procesar. Verificar en ventana de incógnito que reproduce públicamente.

**Bonos (+1.0 punto, ~4 h):** blog público con la frase requerida (+0.2) · post en LinkedIn con `#AllThingsAgenticHackathon` (+0.2) · Gemma ya integrado (+0.2) · Veo solo si sobra tiempo (+0.2).

---

### F7 · Envío — D9 (dom 30 ago)

**Enviar el domingo 30, no el lunes 31.**

- [ ] Categoría seleccionada
- [ ] URL del proyecto hospedado · si está protegida, credenciales de prueba en las instrucciones
- [ ] Descripción: features, tecnologías, fuentes de datos, hallazgos y aprendizajes
- [ ] URL del repo · **verificada en ventana de incógnito**
- [ ] SDK de Google declarado en el formulario
- [ ] Fecha de inicio del proyecto — coincide con el primer commit
- [ ] README con spin-up reproducible
- [ ] Diagrama de arquitectura
- [ ] Video ≤4 min, público, en inglés, con prueba de GCP · **verificado en incógnito**
- [ ] Correo corporativo de Gorilla Labs si aplica a Startup Excellence
- [ ] Declaración de código preexistente
- [ ] Enlaces de bonos en la descripción

---

### F8 · Congelamiento post-cierre — a partir del 31 ago

Pasado el cierre, las submissions quedan bloqueadas. **No tocar el repo, el video ni ningún material enlazado hasta que se anuncien ganadores.** Un commit menor puede afectar elegibilidad.

Como el desarrollo comercial para Café 57 no se detiene, protocolo obligatorio el 30 de agosto:

1. Etiquetar el commit final: `git tag -a submission-devpost -m "..."` y empujar el tag
2. Crear un repo **privado y separado** para la línea comercial
3. Toda evolución posterior ocurre ahí, no en el repo enviado
4. No tocar el video de YouTube ni cambiar su visibilidad

---

## 6. Riesgos

| Riesgo | Prob. | Mitigación |
|---|---|---|
| GEAP nuevo, documentación con huecos | Alta | Punto de decisión D10. Fleet degrada a Taskmaster sin rehacer código. |
| Gemini no disponible en región México | Media | Se convierte en el argumento arquitectónico. Ver ADR-03. |
| ADK-Python fuera de tu stack | Media | F1 es determinista y sin LLM. Tres días de colchón antes de F3. |
| Catálogos SAT cambian o son difíciles de parsear | Media | Congelar snapshot de catálogos en el repo con fecha. Documentarlo. |
| Quemar créditos | Baja | Flash por defecto, Pro solo para razonamiento final. `min-instances=0`. |
| Se va el tiempo codeando y el video sale improvisado | **Alta** | El riesgo real. F6 son 2 días inamovibles. Corte de features el D7 (vie 28). |
| Calendario de 9 días en vez de 14 | **Cierta** | Recortes de §5.1 aplicados desde el inicio, no negociados a media semana. |

---

## 7. Fuera de alcance (documentar en README como escalamiento)

Escrito aquí para no negociarlo después, y en el README porque demuestra visión de producto:

- **Integración con PAC para timbrado real.** Requiere contrato, certificados y pruebas con un Proveedor Autorizado de Certificación. GARITA valida todo hasta el punto previo al timbrado, con mock de contrato definido. Se dice explícitamente en el video.
- **Constancia NOM-151 vía PSC acreditado.** El ledger de hashes es el sustrato; la constancia legal se emitiría por API de un PSC (~$26 MXN/documento) en producción.
- **Multi-tenant real.** El modelo ya es tenant-shaped, la lógica de aislamiento no está.
- **Integración con ERP / M3.** Mock con contrato definido.
- **Portal del lado embarcador.** El espejo del producto: la maquila valida las cartas porte que recibe de sus fleteros para proteger su deducción.
- **Sincronización con sistemas del lado estadounidense** (SCAC, DOT, FMCSA).

Datos sintéticos siempre. Ni un RFC, placa, CURP o licencia real de Café 57 ni de nadie, en un repo que Google va a revisar.
