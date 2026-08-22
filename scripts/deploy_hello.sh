#!/usr/bin/env bash
# F0: despliega el agente hello-world a Cloud Run en Querétaro.
# Requiere: facturación activa en el proyecto (ver docs/PROGRESS.md).
#
# Por qué el override de GOOGLE_CLOUD_LOCATION: `adk deploy cloud_run` escribe
# en el Dockerfile ENV GOOGLE_CLOUD_LOCATION=<región de Cloud Run>. Vertex AI no
# sirve Gemini desde northamerica-south1 (ADR-003), así que el modelo se pide
# al endpoint `global`. Cloud Run env vars tienen precedencia sobre el ENV del
# Dockerfile.
set -euo pipefail

PROJECT="${GOOGLE_CLOUD_PROJECT:-garita-hackathon}"
REGION_RUN="northamerica-south1"
REGION_GEMINI="${GEMINI_LOCATION:-global}"
SERVICE="garita-hello"

gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com --project="$PROJECT"

.venv/bin/adk deploy cloud_run \
  --project="$PROJECT" \
  --region="$REGION_RUN" \
  --service_name="$SERVICE" \
  --app_name=hello \
  src/agentes/hello \
  -- --allow-unauthenticated \
     --set-env-vars="GOOGLE_CLOUD_LOCATION=${REGION_GEMINI},GOOGLE_GENAI_USE_ENTERPRISE=1,GARITA_MODELO=gemini-3.5-flash"

URL=$(gcloud run services describe "$SERVICE" --project="$PROJECT" --region="$REGION_RUN" --format='value(status.url)')
echo "URL: $URL"
curl -s -o /dev/null -w "GET /list-apps -> HTTP %{http_code}\n" "$URL/list-apps"
echo "Captura de consola: https://console.cloud.google.com/run/detail/$REGION_RUN/$SERVICE/metrics?project=$PROJECT"
