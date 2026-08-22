"""Test de aislamiento de tools (entregable de F1, CLAUDE.md <agent_contracts>)."""

import pytest

from tools.registry import SCOPES, TOOLS_CONOCIDAS, ToolFueraDeScope, ToolRegistry, registro_por_defecto

PROHIBIDAS = {
    "coordinador": ["storage_read", "gemini_extract", "xsd_validate", "proponer_accion"],
    "validador": ["storage_read", "gemini_extract", "firestore_write", "memory_bank"],
    "cumplimiento": ["storage_read", "proponer_accion", "firestore_write"],
    "seguimiento": ["storage_read", "gemini_extract", "firestore_write", "xsd_validate"],
    "ingesta": ["proponer_accion", "xsd_validate", "delegar"],
}


@pytest.mark.parametrize("agente,tool", [(a, t) for a, ts in PROHIBIDAS.items() for t in ts])
def test_agente_no_resuelve_tool_fuera_de_scope(agente, tool):
    registro = registro_por_defecto()
    with pytest.raises(ToolFueraDeScope):
        registro.resolver(agente, tool)


def test_validador_resuelve_sus_tools_deterministas():
    registro = registro_por_defecto()
    assert callable(registro.resolver("validador", "xsd_validate"))
    assert callable(registro.resolver("validador", "catalogo_lookup"))


def test_tool_en_scope_pero_no_registrada_es_keyerror_no_permiso():
    registro = ToolRegistry()
    with pytest.raises(KeyError):
        registro.resolver("ingesta", "gemma_redact")


def test_no_se_registra_tool_sin_dueño():
    with pytest.raises(KeyError):
        ToolRegistry().registrar("enviar_correo", lambda: None)


def test_solo_el_coordinador_delega_y_nadie_mas_ve_pii_cruda():
    assert "delegar" in SCOPES["coordinador"]
    assert all("delegar" not in SCOPES[a] for a in SCOPES if a != "coordinador")
    assert all("storage_read" not in SCOPES[a] for a in SCOPES if a != "ingesta")
    assert TOOLS_CONOCIDAS == frozenset().union(*SCOPES.values())
