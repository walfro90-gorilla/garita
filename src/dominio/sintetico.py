"""Expediente sintético de Café 57 para tests y demo. Prefijos obligatorios: XAXX (RFC), TEST- (placas, folios).

Placas: el patrón PlacaVM del SAT prohíbe guiones, así que las placas sintéticas son TEST001/TEST002
(prefijo TEST sin guion). Folios sí llevan TEST-.

Un tractor con la verificación físico-mecánica VENCIDA (el caso del video), una caja,
un operador y el permisionario. `verificacion_vencida=False` simula la renovación ingresada.
"""

from datetime import date, datetime

from dominio.enums import EstadoVigencia, TipoDocumento
from dominio.modelos import Activo, DocumentoVigencia, Domicilio, Mercancia, Operador, Transportista, Ubicacion, Viaje

TENANT = "tenant-cafe57-sintetico"
RFC = "XAXX010101000"


def documento(**cambios) -> DocumentoVigencia:
    base = dict(
        documento_id="doc-1", tenant_id=TENANT, tipo=TipoDocumento.licencia_federal, folio="TEST-LIC-0001",
        fecha_emision=date(2025, 1, 10), fecha_vencimiento=date(2027, 1, 10), estado=EstadoVigencia.vigente,
        fuente_uri="gs://garita-sintetico/doc-1.jpg", confianza_extraccion=0.97, requiere_revision_humana=False,
        hash_documento="a" * 64,
    )
    return DocumentoVigencia(**(base | cambios))


def viaje(**cambios) -> Viaje:
    base = dict(
        viaje_id="viaje-1", tenant_id=TENANT, tractor_id="tractor-1", caja_ids=["caja-1"], operador_id="operador-1",
        transp_internac=True, entrada_salida_merc="Salida", pais_origen_destino="USA", via_entrada_salida="01",
        regimenes_aduaneros=["EXD"],
        mercancias=[Mercancia(clave_prod_serv_cp="10101500", descripcion="Arneses sintéticos", cantidad=10,
                              clave_unidad="H87", peso_en_kg=1200, fraccion_arancelaria="01011001", tipo_materia="03",
                              valor_mercancia=1000.0, moneda="USD")],
        ubicaciones=[
            Ubicacion(tipo_ubicacion="Origen", id_ubicacion="OR000001", rfc_remitente_destinatario=RFC,
                      fecha_hora_salida_llegada=datetime(2026, 8, 23, 5, 0),
                      domicilio=Domicilio(calle="Calle Sintetica 123", estado="CHH", pais="MEX", codigo_postal="32000")),
            Ubicacion(tipo_ubicacion="Destino", id_ubicacion="DE000001", rfc_remitente_destinatario="XEXX010101000",
                      fecha_hora_salida_llegada=datetime(2026, 8, 23, 9, 0), distancia_recorrida=350.0,
                      num_reg_id_trib="TEST-EIN-000000", residencia_fiscal="USA",
                      domicilio=Domicilio(calle="Synthetic Rd 1", estado="TX", pais="USA", codigo_postal="79901")),
        ],
    )
    return Viaje(**(base | cambios))


def sembrar_expediente(repo, *, verificacion_vencida: bool = True) -> None:
    verif = documento(documento_id="doc-verif-0001", tipo=TipoDocumento.verificacion_fisico_mecanica, folio="TEST-VFM-0001",
                      fecha_vencimiento=date(2026, 7, 1) if verificacion_vencida else date(2027, 7, 1),
                      estado=EstadoVigencia.vencido if verificacion_vencida else EstadoVigencia.vigente,
                      fuente_uri="gs://garita-sintetico/verificacion_fisico_mecanica_vencida.jpg", emisor="UV-TEST-09")
    poliza = documento(documento_id="doc-pol-0001", tipo=TipoDocumento.poliza_responsabilidad_civil, folio="TEST-POL-0001",
                       fecha_vencimiento=date(2026, 9, 10), emisor="Aseguradora Sintetica SA")
    repo.guardar("activos", "tractor-1", Activo(
        activo_id="tractor-1", tenant_id=TENANT, tipo="tractor", placa="TEST001", numero_economico="T-01",
        config_autotransporte="T3S2", tarjeta_circulacion=documento(documento_id="doc-tc-0001", tipo=TipoDocumento.tarjeta_circulacion, folio="TEST-TC-0001"),
        verificacion_fisico_mecanica=verif, poliza_responsabilidad_civil=poliza, peso_bruto_vehicular=30.0, anio_modelo=2020))
    repo.guardar("activos", "caja-1", Activo(
        activo_id="caja-1", tenant_id=TENANT, tipo="caja", placa="TEST002", numero_economico="C-01", config_autotransporte=None,
        tarjeta_circulacion=documento(documento_id="doc-tc-0002", tipo=TipoDocumento.tarjeta_circulacion),
        verificacion_fisico_mecanica=documento(documento_id="doc-verif-0002", tipo=TipoDocumento.verificacion_fisico_mecanica),
        poliza_responsabilidad_civil=documento(documento_id="doc-pol-0002", tipo=TipoDocumento.poliza_responsabilidad_civil),
        sub_tipo_rem="CTR004"))
    repo.guardar("operadores", "operador-1", Operador(
        operador_id="operador-1", tenant_id=TENANT, nombre="OPERADOR SINTETICO UNO", curp="TEST900101HCHRST01",
        rfc="XAXX900101AB1", licencia_federal=documento(documento_id="doc-lic-0001"), visa_fast=None))
    repo.guardar("transportistas", TENANT, Transportista(
        tenant_id=TENANT, rfc=RFC, razon_social="Transportes Sinteticos SA de CV", tipo_permiso_sict="TPAF01",
        permiso_sict=documento(documento_id="doc-perm-0001", tipo=TipoDocumento.permiso_sict, folio="TEST-PERM-0001",
                               fecha_vencimiento=date(2027, 3, 15))))
    repo.guardar("viajes", "viaje-1", viaje())
