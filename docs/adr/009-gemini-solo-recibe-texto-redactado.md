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

## Consecuencias

- "Gemini multimodal" de SPEC §F2 se reinterpreta: lo multimodal es Gemma.
  Gemini hace extracción estructurada sobre texto. Se dice así en el video.
- La calidad de extracción depende de la transcripción de Gemma en CPU. Si
  resulta insuficiente, el plan B es Gemma con GPU en `us-central1`, lo cual
  **rompe** ADR-003 y requeriría un ADR nuevo, no un cambio silencioso.
- Los tests sustituyen a Gemma con `RedactorFijo` (transcripciones del
  manifiesto) y a Gemini con un extractor simulado; la frontera y el handoff
  se prueban de verdad.
