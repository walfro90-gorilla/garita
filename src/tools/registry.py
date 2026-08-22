"""ToolRegistry: scopes por agente (CLAUDE.md <agent_contracts>).

Un agente solo resuelve tools de su scope. Resolver fuera de scope lanza
ToolFueraDeScope aunque la tool exista. El test de aislamiento vive en
tests/test_registry.py y es entregable de F1.
"""

from collections.abc import Callable
from typing import Any

SCOPES: dict[str, frozenset[str]] = {
    "coordinador": frozenset({"delegar", "leer_expediente"}),
    "ingesta": frozenset({"storage_read", "gemma_redact", "gemini_extract", "firestore_write"}),
    "validador": frozenset({"xsd_validate", "catalogo_lookup", "cross_check"}),
    "cumplimiento": frozenset({"vigencias_query", "ctpat_msc_lookup", "memory_bank"}),
    "seguimiento": frozenset({"memory_bank", "proponer_accion"}),
}

TOOLS_CONOCIDAS: frozenset[str] = frozenset().union(*SCOPES.values())


class ToolFueraDeScope(PermissionError):
    pass


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}

    def registrar(self, nombre: str, fn: Callable[..., Any]) -> None:
        if nombre not in TOOLS_CONOCIDAS:
            raise KeyError(f"tool sin dueño en SCOPES: {nombre}")
        self._tools[nombre] = fn

    def tools_de(self, agente: str) -> frozenset[str]:
        return SCOPES[agente]

    def resolver(self, agente: str, nombre: str) -> Callable[..., Any]:
        if nombre not in SCOPES[agente]:
            raise ToolFueraDeScope(f"{agente} no puede resolver {nombre}")
        if nombre not in self._tools:
            raise KeyError(f"tool no registrada todavía: {nombre}")
        return self._tools[nombre]


def registro_por_defecto() -> ToolRegistry:
    """Solo las tools deterministas de F1. Las demás se registran en F2/F3."""
    from tools.catalogo_lookup import catalogo_lookup
    from tools.xsd_validate import xsd_validate

    registro = ToolRegistry()
    registro.registrar("xsd_validate", xsd_validate)
    registro.registrar("catalogo_lookup", catalogo_lookup)
    return registro
