"""Constructor del Complemento Carta Porte 3.1 a partir del expediente. Scope: validador.

Determinista. Nombres del SAT. Si falta un dato obligatorio, lanza
CartaPorteIncompleta con la lista completa de faltantes en vez de emitir un XML
inválido. El XML resultante se valida contra el XSD oficial con `xsd_validate`
antes de `listo → en_ruta` (dominio.estados) y antes del timbrado (pac_mock).
"""

import uuid

from lxml import etree

from dominio.modelos import Activo, Operador, Transportista, Viaje

NS = "http://www.sat.gob.mx/CartaPorte31"
NSMAP = {"cartaporte31": NS}
_NAMESPACE_IDCCP = uuid.UUID("6f1c5c2e-0000-4000-8000-000000000057")


class CartaPorteIncompleta(ValueError):
    def __init__(self, faltantes: list[str]) -> None:
        self.faltantes = faltantes
        super().__init__("Carta Porte incompleta: " + "; ".join(faltantes))


def id_ccp(viaje_id: str) -> str:
    """IdCCP: UUID v5 del viaje con prefijo CCC (formato que exige el SAT). Determinista."""
    return "CCC" + str(uuid.uuid5(_NAMESPACE_IDCCP, viaje_id)).upper()[3:]


def _num(v: float, decimales: int) -> str:
    return f"{v:.{decimales}f}"


def construir_carta_porte(viaje: Viaje, tractor: Activo, cajas: list[Activo], operador: Operador, transportista: Transportista) -> bytes:
    faltantes: list[str] = []
    if tractor.tipo != "tractor":
        faltantes.append(f"{tractor.activo_id} no es tractor")
    for campo in ("config_autotransporte", "peso_bruto_vehicular", "anio_modelo"):
        if getattr(tractor, campo) is None:
            faltantes.append(f"tractor {tractor.placa}: falta {campo}")
    if not tractor.poliza_responsabilidad_civil.folio or not tractor.poliza_responsabilidad_civil.emisor:
        faltantes.append(f"tractor {tractor.placa}: póliza sin folio o sin aseguradora")
    for caja in cajas:
        if caja.sub_tipo_rem is None:
            faltantes.append(f"caja {caja.placa}: falta sub_tipo_rem")
    if len(cajas) > 2:
        faltantes.append("la Carta Porte admite máximo 2 remolques")
    if not transportista.permiso_sict.folio:
        faltantes.append("permiso SICT sin folio (NumPermisoSCT)")
    if not operador.licencia_federal.folio:
        faltantes.append(f"operador {operador.operador_id}: licencia sin folio")
    tipos = {u.tipo_ubicacion for u in viaje.ubicaciones}
    if tipos != {"Origen", "Destino"}:
        faltantes.append("se requiere una ubicación Origen y una Destino")
    if not viaje.mercancias:
        faltantes.append("sin mercancías")
    if viaje.transp_internac:
        for i, m in enumerate(viaje.mercancias):
            if not m.fraccion_arancelaria:
                faltantes.append(f"mercancía {i + 1}: internacional sin fracción arancelaria")
        if not viaje.regimenes_aduaneros:
            faltantes.append("internacional sin regímenes aduaneros")
    if faltantes:
        raise CartaPorteIncompleta(faltantes)

    E = etree.Element
    raiz = E(f"{{{NS}}}CartaPorte", nsmap=NSMAP, Version="3.1", IdCCP=id_ccp(viaje.viaje_id),
             TranspInternac="Sí" if viaje.transp_internac else "No")
    if viaje.transp_internac:
        raiz.set("EntradaSalidaMerc", viaje.entrada_salida_merc)
        raiz.set("PaisOrigenDestino", viaje.pais_origen_destino)
        raiz.set("ViaEntradaSalida", viaje.via_entrada_salida)
    raiz.set("TotalDistRec", _num(sum(u.distancia_recorrida or 0 for u in viaje.ubicaciones), 2))

    if viaje.regimenes_aduaneros:
        regs = etree.SubElement(raiz, f"{{{NS}}}RegimenesAduaneros")
        for r in viaje.regimenes_aduaneros:
            etree.SubElement(regs, f"{{{NS}}}RegimenAduaneroCCP", RegimenAduanero=r)

    ubis = etree.SubElement(raiz, f"{{{NS}}}Ubicaciones")
    for u in sorted(viaje.ubicaciones, key=lambda x: x.tipo_ubicacion != "Origen"):
        el = etree.SubElement(ubis, f"{{{NS}}}Ubicacion", TipoUbicacion=u.tipo_ubicacion, IDUbicacion=u.id_ubicacion,
                              RFCRemitenteDestinatario=u.rfc_remitente_destinatario,
                              FechaHoraSalidaLlegada=u.fecha_hora_salida_llegada.strftime("%Y-%m-%dT%H:%M:%S"))
        if u.distancia_recorrida is not None:
            el.set("DistanciaRecorrida", _num(u.distancia_recorrida, 2))

    mercs = etree.SubElement(raiz, f"{{{NS}}}Mercancias", PesoBrutoTotal=_num(sum(m.peso_en_kg for m in viaje.mercancias), 3),
                             UnidadPeso="KGM", NumTotalMercancias=str(len(viaje.mercancias)))
    for m in viaje.mercancias:
        el = etree.SubElement(mercs, f"{{{NS}}}Mercancia", BienesTransp=m.clave_prod_serv_cp, Descripcion=m.descripcion,
                              Cantidad=_num(m.cantidad, 6).rstrip("0").rstrip("."), ClaveUnidad=m.clave_unidad,
                              PesoEnKg=_num(m.peso_en_kg, 3))
        if m.fraccion_arancelaria:
            el.set("FraccionArancelaria", m.fraccion_arancelaria)
        if m.valor_mercancia is not None and m.moneda:
            el.set("ValorMercancia", _num(m.valor_mercancia, 2))
            el.set("Moneda", m.moneda)

    auto = etree.SubElement(mercs, f"{{{NS}}}Autotransporte", PermSCT=transportista.tipo_permiso_sict,
                            NumPermisoSCT=transportista.permiso_sict.folio)
    etree.SubElement(auto, f"{{{NS}}}IdentificacionVehicular", ConfigVehicular=tractor.config_autotransporte,
                     PesoBrutoVehicular=_num(tractor.peso_bruto_vehicular, 2), PlacaVM=tractor.placa,
                     AnioModeloVM=str(tractor.anio_modelo))
    etree.SubElement(auto, f"{{{NS}}}Seguros", AseguraRespCivil=tractor.poliza_responsabilidad_civil.emisor,
                     PolizaRespCivil=tractor.poliza_responsabilidad_civil.folio)
    if cajas:
        rems = etree.SubElement(auto, f"{{{NS}}}Remolques")
        for caja in cajas:
            etree.SubElement(rems, f"{{{NS}}}Remolque", SubTipoRem=caja.sub_tipo_rem, Placa=caja.placa)

    fig = etree.SubElement(raiz, f"{{{NS}}}FiguraTransporte")
    etree.SubElement(fig, f"{{{NS}}}TiposFigura", TipoFigura="01", NumLicencia=operador.licencia_federal.folio,
                     NombreFigura=operador.nombre)
    return etree.tostring(raiz, xml_declaration=True, encoding="UTF-8", pretty_print=True)
