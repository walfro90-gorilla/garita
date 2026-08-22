#!/usr/bin/env bash
# F0: un presupuesto con tres umbrales: $25 / $60 / $120.
# Requiere: cuenta de facturación ABIERTA y vinculada al proyecto.
# Uso: scripts/budget_alerts.sh <BILLING_ACCOUNT_ID>
set -euo pipefail

BILLING="${1:?Uso: $0 <BILLING_ACCOUNT_ID>}"
PROJECT="${GOOGLE_CLOUD_PROJECT:-garita-hackathon}"
NUMERO=$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')

gcloud billing budgets create \
  --billing-account="$BILLING" \
  --display-name="garita-25-60-120" \
  --budget-amount=120USD \
  --filter-projects="projects/$NUMERO" \
  --threshold-rule=percent=0.2084 \
  --threshold-rule=percent=0.50 \
  --threshold-rule=percent=1.00

gcloud billing budgets list --billing-account="$BILLING" --format='table(displayName,amount.specifiedAmount.units,thresholdRules[].thresholdPercent)'
