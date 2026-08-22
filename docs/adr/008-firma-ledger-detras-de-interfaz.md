# ADR 008: La firma del ledger vive detrás de una interfaz

- **Estado:** aceptado
- **Fecha:** 2026-08-22

## Contexto

ADR-006 fija el ledger: cadena de hashes SHA-256, cada entrada firmada con Cloud
KMS, archivo WORM en Cloud Storage. En F1 no hay facturación en GCP, y la suite
de F1 debe correr local y verde sin red (`docs/PROGRESS.md`).

## Decisión

`LedgerService` no conoce KMS. Recibe un `Firmador`:

```python
class Firmador(Protocol):
    key_id: str
    def firmar(self, digesto: bytes) -> bytes: ...
    def verificar(self, digesto: bytes, firma: bytes) -> bool: ...
```

- `FirmadorLocalHmac` — HMAC-SHA256 con clave en memoria. Desarrollo y tests.
- `FirmadorKms` — Cloud KMS con llave **MAC HMAC_SHA256** (`mac_sign` /
  `mac_verify`). Misma semántica que el local: un MAC sobre el hash de la
  entrada. Se conecta cuando haya facturación; hasta entonces es un adaptador
  sin prueba automática y así se declara.

Lo que se firma es el **hash** de la entrada (canonicalizada como JSON con
claves ordenadas), no la entrada. `verify()` recalcula hash, enlace y firma de
toda la cadena y lanza `LedgerAlterado` en la primera discrepancia.

## Por qué MAC y no firma asimétrica

Un MAC en KMS basta para el objetivo del hackathon (detectar alteración por
quien no tiene la llave) y mantiene el adaptador en dos llamadas. Si en
producción se necesita verificación por terceros sin acceso a KMS, se cambia
`FirmadorKms` por uno con `asymmetric_sign` + llave pública; `LedgerService`
no cambia. La constancia NOM-151 vía PSC queda como escalamiento (SPEC §7).

## Consecuencias

- `ledger.verify()` es el mismo código en tests y en producción; solo cambia
  el firmador.
- `EntradaLedger` es inmutable (`frozen=True`) y solo la construye
  `LedgerService.append()` (CLAUDE.md <forbidden_actions>).
- La llave local **nunca** se commitea ni se usa fuera de tests: se genera por
  test con `secrets.token_bytes`.
- Pendiente al tener facturación: crear keyring en `northamerica-south1`
  (ADR-003), llave `MAC` `HMAC_SHA256`, y un test de humo marcado como
  `integracion` que firme y verifique una entrada real.
