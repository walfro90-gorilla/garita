# Arquitectura v0 — herramienta de diseño (22 ago)

No es entregable. Existe para comprobar que se puede dibujar dónde vive el
estado, cómo se conecta Gemini y qué cruza la frontera. Si no se dibuja claro,
el diseño necesita otra pasada.

```mermaid
flowchart LR
    subgraph MX["northamerica-south1 · Querétaro · zona de PII"]
        direction TB
        API["Cloud Run · api<br/>(FastAPI + ADK)"]
        COORD["coordinador"]
        ING["ingesta"]
        VAL["validador<br/>XSD + catálogos"]
        CUM["cumplimiento<br/>vigencias"]
        SEG["seguimiento<br/>propone acciones"]
        GEMMA["Cloud Run · Gemma (CPU)<br/>redacción PII"]
        FS[("Firestore<br/>expediente + mapa tokens")]
        GCS[("Cloud Storage<br/>originales, retention")]
        KMS["Cloud KMS<br/>firma hash-chain"]
        PS["Pub/Sub<br/>storage policy MX<br/>+ dead-letter"]
        LEDGER["LedgerService"]
        API --> COORD
        COORD --> ING & VAL & CUM & SEG
        ING --> GCS
        ING --> GEMMA
        ING --> FS
        VAL --> FS
        CUM --> FS
        SEG --> FS
        COORD --> LEDGER --> KMS
        LEDGER --> FS
        API <--> PS
    end

    subgraph GLOBAL["Vertex AI · endpoint global"]
        GEMINI["gemini-3.5-flash"]
    end

    HUMANO["Humano<br/>cola de aprobación (Next.js)"]

    ING -. "payload REDACTADO<br/>[CURP_1], [NOMBRE_1]" .-> GEMINI
    GEMINI -. "JSON validado Pydantic" .-> ING
    SEG -. "AccionPropuesta<br/>pending_approval" .-> HUMANO
    HUMANO -. "aprueba" .-> API

    style MX fill:#eef6ee,stroke:#2e7d32,stroke-width:2px
    style GLOBAL fill:#fff4e5,stroke:#ef6c00,stroke-width:2px,stroke-dasharray: 5 5
```

**Lo que cruza la línea punteada:** texto redactado hacia Gemini; JSON
estructurado de regreso. Nada más.

**Tres relojes** (SPEC §1): minutos (Carta Porte por viaje), semanas–meses
(vigencias), años (ledger inmutable). Los tres viven en Firestore + Storage en
México; el único reloj que toca Gemini es el de minutos, ya redactado.

Pendiente para v1 (D4): diagrama en PNG, `docs/architecture.png`.
