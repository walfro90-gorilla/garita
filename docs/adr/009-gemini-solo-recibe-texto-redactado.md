# ADR 009: Gemini solo recibe texto redactado; Gemma transcribe y redacta en México

- **Estado:** aceptado
- **Fecha:** 2026-08-22

## Contexto

SPEC §F2 describe `documento → Gemma → Gemini multimodal → esquema`. Pero un
documento escaneado o fotografiado **es** PII en píxeles: nombre, CURP, RFC,
domicilio. Si Gemini recibe la imagen, la PII cruza la frontera de ADR-003 sin
importar lo que haga Gemma antes. Y no hay manera fiable de "redactar píxeles"
con un modelo pequeño en CPU (ADR-003 §4: no hay GPU de Cloud Run en México).

## Decisión

1. **Gemma es el único modelo que ve el documento.** Corre en la zona de PII
   (Cloud Run `northamerica-south1`, CPU) y produce una **transcripción ya
   redactada**: `[NOMBRE]`, `[CURP]`, `[RFC]`, `[DOMICILIO]`, y `[ILEGIBLE]`
   donde no lee con claridad.
2. **Segunda capa determinista, siempre.** `RedactorPatron` repasa la salida de
   Gemma: CURP y RFC por regex (formato fijo, la regex no falla), nombres por
   diccionario del expediente. Numera tokens (`[CURP_1]`) y construye el mapa
   token→valor.
3. **`infra.frontera.afirmar_sin_pii` es la compuerta.** Justo antes de
   `gemini_extract` se verifica que el payload no contenga ningún valor del
   mapa ni ningún patrón de PII. Si falla: dead-letter y entrada en el ledger
   `fuga_pii_detenida`. Nunca "se limpia y sigue". El log
   `frontera.ok documento_id=… destino=vertex-ai` es la toma del video.
4. **Gemini recibe texto.** `gemini_extract` manda la transcripción redactada a
   `gemini-3.5-flash` (endpoint `global`) con `response_schema =
   ExtraccionDocumento`. Gemini no decide el estado de vigencia:
   `dominio.vigencias.estado_vigencia` lo calcula de la fecha extraída.
5. **El mapa de tokens vive en Firestore MX** (`mapas_redaccion`) y nunca se
   adjunta a ningún prompt ni respuesta.

## Runtime de Gemma

API de Ollama (`/api/generate`) en los dos entornos: `ollama` local para
desarrollo y el contenedor oficial de Ollama en Cloud Run para producción (ruta
documentada por Google para Gemma 3). Modelo base `gemma3:4b` (multimodal);
el tamaño final se fija midiendo latencia en CPU en F3/F5. Ollama es runtime,
no dependencia de Python: `<stack>` no cambia.

## Medición (22 ago, Ollama local, `gemma3:4b`, 100 % CPU, 8 cores, 5 GB libres)

- Transcripción de la licencia borrosa: correcta; la línea de vigencia
  emborronada **se omite, no se inventa**.
- Redacción por Gemma: **no ocurre**. Deja nombre, CURP y domicilio en claro;
  a lo sumo antepone la etiqueta `[CURP]:` al valor. Además deforma la CURP
  (`TEST900101HCRST01`, una letra menos), con lo que la regex de formato ya no
  la reconoce.
- Por eso la capa 2 y la compuerta trabajan **por etiqueta**, no solo por
  formato: lo que sigue a `CURP:`, `RFC:`, `NOMBRE:`, `DOMICILIO:` se tokeniza
  siempre, y la frontera rechaza cualquier etiqueta de PII sin token.
- Latencia: 231 s de prompt-eval por imagen (encoder de visión en CPU) + 12 s
  de generación. Medición contaminada por presión de memoria; se repite en
  Cloud Run (8 vCPU / 16 GiB) antes de fijar tamaño de modelo y guion del video.

## Consecuencias

- "Gemini multimodal" de SPEC §F2 se reinterpreta: lo multimodal es Gemma.
  Gemini hace extracción estructurada sobre texto. Se dice así en el video.
- La calidad de extracción depende de la transcripción de Gemma en CPU. Si
  resulta insuficiente, el plan B es Gemma con GPU en `us-central1`, lo cual
  **rompe** ADR-003 y requeriría un ADR nuevo, no un cambio silencioso.
- Los tests sustituyen a Gemma con `RedactorFijo` (transcripciones del
  manifiesto) y a Gemini con un extractor simulado; la frontera y el handoff
  se prueban de verdad.
