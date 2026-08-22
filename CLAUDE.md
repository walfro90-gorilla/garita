# CLAUDE.md — GARITA

<mission>
Flota de agentes que mantiene a un transportista de cruce fronterizo en estado de poder cruzar.
Valida cada Complemento Carta Porte 3.1 antes del timbrado, y mantiene vigente todo aquello de lo que la Carta Porte depende.

Entregable: submission al hackathon All Things Agentic (Google/Devpost), categoría Fortified Enterprise Fleet.
Cierre: 31 ago 2026, 17:00 PT. Contexto completo del dominio en `docs/SPEC.md`.
</mission>

<non_negotiables>
Violarlos causa descalificación, no solo pérdida de puntos.

1. Todo el código se escribe entre el 3 y el 31 de agosto de 2026. Cero código preexistente sin declararlo en README.
2. Debe usarse Gemini 3.5+ vía Vertex AI, Google ADK como framework de agentes, y servicios de infraestructura de GCP.
3. Cero datos reales. Ningún RFC, CURP, placa, licencia o razón social de una persona o empresa existente.
4. El repo se congela el 31 de agosto. Nada de commits después del envío.
</non_negotiables>

<stack>
Python 3.12 · `google-adk` · `google-genai` · `google-cloud-firestore` · `google-cloud-pubsub` · `google-cloud-kms` · `google-cloud-storage` · `pydantic` v2 · `lxml` (validación XSD) · `pytest`
Frontend: Next.js 15, mínimo, solo dos vistas.
Infra: Cloud Run · Firestore · Pub/Sub · Cloud KMS · Cloud Storage · Vertex AI

REGLA: fijar versiones exactas en `requirements.txt` después del primer `pip install` real.
No asumas números de versión. Verifícalos.
No agregues ninguna dependencia fuera de esta lista sin preguntar primero.
</stack>

<naming_convention>
Línea única, sin excepciones:

- **Capa de dominio en español.** `Viaje`, `Activo`, `Operador`, `DocumentoVigencia`, `Bloqueo`, `Mercancia`, `AccionPropuesta`.
  Razón: el XSD del SAT y sus catálogos están en español. Traducir `fracción arancelaria` a `tariff_code` crea una capa de mapeo que es pérdida pura y fuente de bugs.
- **Capa de infraestructura en inglés.** `FirestoreRepository`, `LedgerService`, `ToolRegistry`, `HandoffValidator`, `CircuitBreaker`.
- Campos siempre `snake_case`. Clases `PascalCase`.
- Los campos que mapean 1:1 al XSD conservan el nombre del SAT: `transp_internac`, `entrada_salida_merc`, `via_entrada_salida`, `regimenes_aduaneros`, `fraccion_arancelaria`, `clave_prod_serv_cp`, `config_autotransporte`.
- Comentarios y docstrings en español. README y video en inglés.
</naming_convention>

<repo_structure>
```
garita/
├── CLAUDE.md
├── README.md
├── requirements.txt
├── docs/
│   ├── SPEC.md
│   ├── PROGRESS.md          # bitácora de sesión — leer al abrir, escribir al cerrar
│   ├── architecture.png
│   └── adr/
├── catalogos/               # snapshot fechado de catálogos SAT + XSD (versionado)
├── src/
│   ├── dominio/             # modelos Pydantic, enums, máquina de estados
│   ├── agentes/             # coordinador, ingesta, validador, cumplimiento, seguimiento
│   ├── tools/               # una tool por archivo, con scope declarado
│   ├── infra/               # firestore, pubsub, kms, storage, ledger
│   └── api/                 # entrypoint FastAPI para Cloud Run
├── tests/
├── fixtures/                # corpus sintético — 5 documentos
└── web/                     # Next.js, dos vistas
```
</repo_structure>

<data_models>
Definir en `src/dominio/`. Estas son las formas obligatorias; los campos auxiliares se pueden agregar.

**Todo modelo persistido lleva `tenant_id: str`.** Se transporta, no se aplica aislamiento (ver `<forbidden_actions>`).

```python
class DocumentoVigencia(BaseModel):
    documento_id: str
    tenant_id: str
    tipo: TipoDocumento                      # enum
    folio: str | None
    fecha_emision: date | None
    fecha_vencimiento: date | None
    estado: EstadoVigencia                   # vigente|por_vencer|vencido|no_localizado|ilegible
    fuente_uri: str                          # gs:// del original
    confianza_extraccion: float              # 0.0–1.0 reportada por el extractor
    requiere_revision_humana: bool           # True si confianza < 0.85 o campo crítico ausente
    hash_documento: str                      # SHA-256 del binario original
```

`confianza_extraccion` y `requiere_revision_humana` son obligatorios. Un agente que sabe lo que no sabe es el diferenciador; nunca inventar una fecha de vencimiento ilegible.

```python
class Operador(BaseModel):
    operador_id: str
    tenant_id: str
    nombre: str                              # PII
    curp: str | None                         # PII
    licencia_federal: DocumentoVigencia      # tipo E
    visa_fast: DocumentoVigencia | None

class Activo(BaseModel):
    activo_id: str
    tenant_id: str
    tipo: Literal["tractor", "caja", "dolly"]
    placa: str
    numero_economico: str
    config_autotransporte: str | None        # c_ConfigAutotransporte, solo tractor
    tarjeta_circulacion: DocumentoVigencia
    verificacion_fisico_mecanica: DocumentoVigencia
    poliza_responsabilidad_civil: DocumentoVigencia

class Bloqueo(BaseModel):
    bloqueo_id: str
    motivo: MotivoBloqueo                    # enum
    severidad: Literal["duro", "blando"]
    explicacion: str                         # legible por el coordinador de tráfico
    documento_id: str | None
    evidencia_uri: str
    accion_propuesta_id: str | None
    detectado_por: str                       # nombre del agente
    detectado_en: datetime

class Viaje(BaseModel):
    viaje_id: str
    tenant_id: str
    estado: EstadoViaje
    tractor_id: str
    caja_ids: list[str]
    operador_id: str
    transp_internac: bool
    entrada_salida_merc: Literal["Entrada", "Salida"] | None
    pais_origen_destino: str | None          # != "MEX" si transp_internac
    via_entrada_salida: str | None
    regimenes_aduaneros: list[str]           # máximo 10
    mercancias: list[Mercancia]
    bloqueos: list[Bloqueo]
```

`Bloqueo` **es el producto**. Es lo que se demuestra en el video. Modelarlo con cuidado.
</data_models>

<state_machine>
```
borrador → validando → bloqueado ⇄ validando → listo → en_ruta → cerrado
                                                    ↓
                                              cancelado (desde cualquier estado)
```

Guardas obligatorias, implementadas y con test:
- `validando → listo` exige cero bloqueos con `severidad="duro"`
- `validando → bloqueado` si existe al menos un bloqueo duro
- `bloqueado → validando` solo tras una `AccionPropuesta` aprobada por humano que resuelva el bloqueo
- `listo → en_ruta` exige payload de Carta Porte validado contra el XSD
- Toda transición se escribe al ledger antes de persistirse
</state_machine>

<agent_contracts>
| Agente | Tools permitidas | Prohibido |
|---|---|---|
| `coordinador` | delegación a sub-agentes, lectura de expediente | Cloud Storage, PII cruda, red externa |
| `ingesta` | storage_read, gemma_redact, gemini_extract, firestore_write | Decidir bloqueos |
| `validador` | xsd_validate, catalogo_lookup, cross_check | Red externa, escritura a Storage |
| `cumplimiento` | vigencias_query, ctpat_msc_lookup, memory_bank | Enviar comunicaciones |
| `seguimiento` | memory_bank, proponer_accion | Ejecutar cualquier efecto externo |

`ledger` es un **servicio**, no un agente.

El aislamiento se verifica con un test que falla si un agente puede resolver una tool fuera de su scope. Ese test es entregable de F1.
</agent_contracts>

<failure_tolerance>
Los cuatro son obligatorios, no opcionales:

1. **Handoff validado.** Todo output de sub-agente se valida contra Pydantic. Falla → reintento con el error de validación inyectado en el prompt. Tercera falla → dead-letter.
2. **Presupuesto de turnos.** `max_turns` por sub-agente. Excedido → `failed_budget_exceeded`, sin reintento.
3. **Idempotencia.** Toda tool con efecto lateral recibe `idempotency_key = sha256(viaje_id + paso_id + hash(input))`. Reejecutar no duplica.
4. **Dead-letter en Pub/Sub** con handler que escribe la falla al expediente. Nunca tragarse una excepción.
</failure_tolerance>

<parallel_execution>
Fan-out permitido SOLO entre D3 y D5, tras el congelamiento de contratos de F1.
Máximo 2 worktrees de código: garita-ingesta y garita-validacion.
Prohibido tocar src/dominio/ desde un worktree — cambios al dominio van a main, en serie, con ADR.
Integración a main cada noche. Rama paralela con más de 24h de vida = detenerse e integrar.
PROGRESS.md lleva una sección por pista; el merge nocturno las consolida.
</parallel_execution>

<forbidden_actions>
Nunca, sin excepción:

- **Inventar valores de catálogo del SAT.** Si el catálogo no está descargado en `catalogos/`, fallar ruidosamente. Jamás alucinar una fracción arancelaria o una clave de permiso.
- **Usar datos reales.** Los sintéticos usan prefijo `XAXX` para RFC y `TEST-` para placas y folios.
- **Implementar multi-tenancy.** `tenant_id` se transporta en todos los modelos; la lógica de aislamiento queda fuera de alcance y documentada en README.
- **Llamar a un PAC o intentar timbrado real.** El mock tiene contrato definido y se declara en el video.
- **Permitir que un agente ejecute un efecto externo.** Solo propone; un humano aprueba.
- **Escribir al ledger fuera de `LedgerService.append()`.**
- **Commitear secretos, claves de servicio o `.env`.**
- **Agregar dependencias fuera de `<stack>`** sin preguntar.
- **Construir UI más allá de dos vistas:** cola de aprobación y detalle de expediente.
</forbidden_actions>

<definition_of_done>
Un paso está terminado cuando cumple los cinco:
1. Los criterios de aceptación de su fase en `docs/SPEC.md` pasan
2. Tiene test que falla si se rompe
3. `docs/PROGRESS.md` está actualizado
4. Commit con prefijo de fase: `F1: ...`
5. Si se tomó una decisión de arquitectura, existe un ADR nuevo en `docs/adr/`
</definition_of_done>

<session_protocol>
**Al abrir sesión:** leer `CLAUDE.md`, luego `docs/PROGRESS.md`. No releer `SPEC.md` completo salvo que se necesite contexto de dominio.

**Al cerrar sesión:** actualizar `docs/PROGRESS.md` con exactamente cuatro cosas:
- Fase actual y criterios de aceptación cumplidos
- Decisiones tomadas y ADRs creados
- Bloqueos abiertos o preguntas para el humano
- **Siguiente acción concreta**, redactada para ejecutarse sin contexto adicional

Este archivo es el mecanismo de memoria entre sesiones. Si está desactualizado, la siguiente sesión reinventa cosas.
</session_protocol>

<current_phase>
**F1 completa (22 ago) → F2 · Ingesta multimodal**

ADR-003: Gemini NO se sirve desde `northamerica-south1`; PII se queda en México, solo payloads redactados van a Vertex AI (`global`). ADR-008: firma del ledger detrás de `Firmador` (HMAC local / KMS MAC).

Bloqueos abiertos: facturación de `garita-hackathon` (pendiente del humano) y librería para generar el corpus sintético (pregunta 4 en `docs/PROGRESS.md`).

Siguiente acción: ver "Siguiente acción concreta" en `docs/PROGRESS.md`.
</current_phase>
