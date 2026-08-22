"""Tool `cross_check`: cruza el Viaje contra su tractor, cajas y operador. Scope: validador.

Determinista. Produce Bloqueos duros con ids deterministas (reejecutar no duplica).
No toca red ni Storage.
"""

from datetime import date, datetime, time, timezone

from dominio.enums import MotivoBloqueo
from dominio.modelos import Activo, Bloqueo, Operador, Viaje
from tools.catalogo_lookup import catalogo_lookup

AGENTE = "validador"


def _bloqueo(viaje: Viaje, motivo: MotivoBloqueo, clave: str, explicacion: str, hoy: date, documento_id: str | None = None) -> Bloqueo:
    return Bloqueo(
        bloqueo_id=f"blq-{viaje.viaje_id}-{motivo}-{clave}",
        motivo=motivo,
        severidad="duro",
        explicacion=explicacion,
        documento_id=documento_id,
        evidencia_uri=f"expediente://viajes/{viaje.viaje_id}",
        accion_propuesta_id=None,
        detectado_por=AGENTE,
        detectado_en=datetime.combine(hoy, time.min, tzinfo=timezone.utc),
    )


def cross_check(viaje: Viaje, tractor: Activo | None, cajas: list[Activo], operador: Operador | None, hoy: date) -> list[Bloqueo]:
    b: list[Bloqueo] = []
    inc = MotivoBloqueo.dato_inconsistente
    cat = MotivoBloqueo.catalogo_invalido

    if tractor is None or tractor.activo_id != viaje.tractor_id:
        b.append(_bloqueo(viaje, inc, "tractor", f"El tractor {viaje.tractor_id} no existe en el expediente.", hoy))
    else:
        if tractor.tipo != "tractor":
            b.append(_bloqueo(viaje, inc, "tipo-tractor", f"{tractor.activo_id} es {tractor.tipo}, no tractor.", hoy))
        if not tractor.config_autotransporte:
            b.append(_bloqueo(viaje, inc, "config", f"El tractor {tractor.placa} no tiene ConfigAutotransporte; la Carta Porte lo exige.", hoy))
    ids_cajas = {c.activo_id for c in cajas}
    for caja_id in viaje.caja_ids:
        if caja_id not in ids_cajas:
            b.append(_bloqueo(viaje, inc, f"caja-{caja_id}", f"La caja {caja_id} no existe en el expediente.", hoy))
    if operador is None or operador.operador_id != viaje.operador_id:
        b.append(_bloqueo(viaje, inc, "operador", f"El operador {viaje.operador_id} no existe en el expediente.", hoy))

    if not viaje.mercancias:
        b.append(_bloqueo(viaje, inc, "mercancias", "El viaje no declara mercancías.", hoy))
    for i, m in enumerate(viaje.mercancias):
        if not catalogo_lookup("c_ClaveProdServCP", m.clave_prod_serv_cp):
            b.append(_bloqueo(viaje, cat, f"prodserv-{i}", f"Mercancía {i + 1}: clave_prod_serv_cp {m.clave_prod_serv_cp} no está en c_ClaveProdServCP.", hoy))
        if viaje.transp_internac:
            if not m.fraccion_arancelaria:
                b.append(_bloqueo(viaje, inc, f"fraccion-{i}", f"Mercancía {i + 1}: transporte internacional sin fracción arancelaria.", hoy))
            elif not catalogo_lookup("c_FraccionArancelaria", m.fraccion_arancelaria):
                b.append(_bloqueo(viaje, cat, f"fraccion-{i}", f"Mercancía {i + 1}: fracción {m.fraccion_arancelaria} no está en c_FraccionArancelaria.", hoy))
    return b
