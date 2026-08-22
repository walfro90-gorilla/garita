# GARITA

A fleet of agents that keeps a cross-border trucking carrier in a state where it
can cross. GARITA validates every *Complemento Carta Porte 3.1* before it is
stamped, and keeps current everything the Carta Porte depends on: federal
driver licenses, circulation cards, mechanical inspections, insurance policies,
SICT permits.

Built for the **All Things Agentic** hackathon (Google / Devpost), category
*Fortified Enterprise Fleet*.

## No preexisting code

All code in this repository was written between **August 3 and August 31,
2026**, specifically for this hackathon. Nothing here derives from or reuses
any prior project, client work, or employer code. The first commit is dated
August 22, 2026 and matches the project start date declared on Devpost.

## Stack

- **Gemini 3.5 Flash** via **Vertex AI** (global endpoint)
- **Google Agent Development Kit (ADK)** for Python — agent orchestration
- **Cloud Run** in `northamerica-south1` (Querétaro, Mexico) — all compute that touches PII
- **Firestore**, **Cloud Storage**, **Cloud KMS**, **Pub/Sub** — all in Mexico
- Python 3.12 · Pydantic v2 · lxml (SAT XSD validation) · pytest
- Next.js 15 for two views: approval queue and case file

## Data residency

Vertex AI does not serve Gemini from Mexico. GARITA treats that as
architecture, not as a limitation: PII never leaves `northamerica-south1`; a
Gemma redaction service replaces names, CURP, RFC and plates with tokens, and
only redacted payloads reach Gemini. See
[docs/adr/003-data-residency.md](docs/adr/003-data-residency.md) for the
evidence and the decision.

## Synthetic data only

No real RFC, CURP, plate, license or company name appears anywhere. Synthetic
RFCs use the `XAXX` prefix; plates and folios use `TEST-`.

## Multi-tenancy

Every persisted model carries `tenant_id`. Isolation logic is out of scope for
the hackathon and is not implemented.

## Run locally

```bash
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env           # then set GOOGLE_CLOUD_PROJECT
.venv/bin/pytest
.venv/bin/adk api_server src/agentes --port 8000
curl localhost:8000/list-apps  # → ["hello"]
```

## Deploy the F0 hello-world to Cloud Run (Querétaro)

```bash
gcloud auth login
scripts/deploy_hello.sh
```

## Layout

```
docs/SPEC.md         domain + plan        docs/PROGRESS.md   session log
docs/adr/            decisions            src/agentes/       ADK agents
src/dominio/         Pydantic models      src/tools/         one tool per file
src/infra/           Firestore, Pub/Sub, KMS, Storage, ledger
src/api/             FastAPI entrypoint   tests/  fixtures/  web/
```
