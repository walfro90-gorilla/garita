"""Agente hello-world de F0.

Único propósito: probar que un agente ADK responde 200 desde Cloud Run en
`northamerica-south1` mientras el modelo se sirve vía Vertex AI desde el
endpoint `global` (ver docs/adr/003-data-residency.md). Se borra en F1.
"""

import os

from google.adk.agents import Agent

# Modelo por defecto decidido en ADR-003. Sobreescribible por entorno.
MODELO = os.environ.get("GARITA_MODELO", "gemini-3.5-flash")

root_agent = Agent(
    name="hello",
    model=MODELO,
    description="Agente de humo de GARITA. No toca datos.",
    instruction=(
        "Eres GARITA. Responde en una sola línea en español: "
        "'GARITA en línea desde northamerica-south1'."
    ),
)
