# PolPilot - Modelo de Datos Base (3 DB NoSQL por Cliente)

## 1. Objetivo

Definir una estructura inicial de datos para implementar PolPilot con **3 bases no relacionales por cliente**:

1. `internal_db`: informacion interna del negocio cliente.
2. `external_db`: informacion externa recolectada por el agente investigador.
3. `summary_db`: resumenes operativos + embeddings para recuperacion semantica.

Este documento esta pensado para **MVP implementable**, con trazabilidad para el orquestador y el agente resumidor.

---

## 2. Estrategia de Tenancy (por cliente)

### 2.1 Convencion de nombres

Para un cliente `client_id=acme_001`:

- `polpilot_acme_001_internal`
- `polpilot_acme_001_external`
- `polpilot_acme_001_summary`

### 2.2 Motor recomendado

- `internal_db`: MongoDB (documental).
- `external_db`: MongoDB (documental).
- `summary_db`: Vector DB (Qdrant/Weaviate/Pinecone) + metadatos en MongoDB.

Nota: si quieren arrancar mas simple, pueden usar solo MongoDB en las 3 y agregar vector DB en fase 2.

---

## 3. DB 1 - Internal (informacion interna cliente)

## 3.1 Proposito

Guardar hechos internos del negocio: perfil, operaciones, documentos subidos, y estado de integraciones.

## 3.2 Colecciones MVP

1. `company_profile`
2. `users_roles`
3. `business_facts`
4. `documents_raw`
5. `documents_normalized`
6. `integration_state`

## 3.3 Campos base comunes

Todos los documentos deben incluir:

- `_id`
- `client_id`
- `created_at`
- `updated_at`
- `version`
- `source` (whatsapp, upload, integration, manual)
- `confidence` (0.0 - 1.0 cuando aplique)

## 3.4 Ejemplo `business_facts`

```json
{
  "_id": "fact_9f2",
  "client_id": "acme_001",
  "fact_type": "cashflow_monthly",
  "period": "2026-04",
  "payload": {
    "income_total": 12500000,
    "expense_total": 9800000,
    "currency": "ARS"
  },
  "source": "excel_upload",
  "confidence": 0.93,
  "created_at": "2026-04-14T14:20:00Z",
  "updated_at": "2026-04-14T14:20:00Z",
  "version": 1
}
```

## 3.5 Indices minimos

- `business_facts`: `(client_id, fact_type, period desc)`
- `documents_raw`: `(client_id, uploaded_at desc)`
- `documents_normalized`: `(client_id, doc_id)`

---

## 4. DB 2 - External (investigacion externa)

## 4.1 Proposito

Guardar informacion externa estructurada por el agente investigador: fuentes, hallazgos, validez temporal y evidencia.

## 4.2 Colecciones MVP

1. `source_registry`
2. `research_runs`
3. `external_findings_raw`
4. `external_findings_normalized`
5. `external_signals`

## 4.3 Ejemplo `external_findings_normalized`

```json
{
  "_id": "ext_find_301",
  "client_id": "acme_001",
  "topic": "creditos_pyme",
  "entity": "BCRA",
  "finding_type": "rate_reference",
  "payload": {
    "metric": "tasa_adelantos_cuenta_corriente",
    "value": 37.2,
    "unit": "TNA"
  },
  "evidence": [
    {
      "url": "https://www.bcra.gob.ar/",
      "captured_at": "2026-04-14T13:10:00Z"
    }
  ],
  "valid_from": "2026-04-14",
  "valid_to": null,
  "confidence": 0.88,
  "created_at": "2026-04-14T13:11:00Z",
  "updated_at": "2026-04-14T13:11:00Z",
  "version": 1
}
```

## 4.4 Indices minimos

- `external_findings_normalized`: `(client_id, topic, updated_at desc)`
- `external_signals`: `(client_id, signal_type, observed_at desc)`
- `research_runs`: `(client_id, started_at desc, status)`

---

## 5. DB 3 - Summary (resumenes + embeddings)

## 5.1 Proposito

Persistir memoria resumida por contexto y sus embeddings para que el orquestador recupere rapido lo relevante.

## 5.2 Componentes

1. `context_summaries` (MongoDB)
2. `context_embeddings` (Vector DB)
3. `summary_lineage` (MongoDB, trazabilidad)

## 5.3 Regla funcional clave

El agente resumidor debe crear **una nueva linea por contexto/turno** (append-only), en lugar de sobreescribir siempre el mismo resumen.

## 5.4 Ejemplo `context_summaries`

```json
{
  "_id": "sum_20260414_00019",
  "client_id": "acme_001",
  "session_id": "sess_77",
  "execution_id": "exec_3921",
  "context_key": "credito_pyme_capital_trabajo",
  "summary_text": "Se detecta necesidad de capital de trabajo con riesgo de liquidez en 45 dias.",
  "highlights": [
    "flujo de fondos negativo proyectado",
    "lineas de credito BCRA relevantes"
  ],
  "source_refs": ["fact_9f2", "ext_find_301"],
  "relevance_score": 0.91,
  "created_at": "2026-04-14T14:30:00Z",
  "version": 1
}
```

## 5.5 Ejemplo vector point `context_embeddings`

```json
{
  "id": "emb_sum_20260414_00019",
  "vector": [0.012, -0.337, 0.228],
  "payload": {
    "client_id": "acme_001",
    "summary_id": "sum_20260414_00019",
    "context_key": "credito_pyme_capital_trabajo",
    "created_at": "2026-04-14T14:30:01Z"
  }
}
```

## 5.6 Indices minimos

- `context_summaries`: `(client_id, context_key, created_at desc)`
- `summary_lineage`: `(client_id, execution_id)`
- Vector index por `client_id` + `context_key` como filtros de payload.

---

## 6. Flujo operacional entre agentes

1. Usuario envia input (texto/audio/doc).
2. Orquestador normaliza y guarda crudo en `internal_db.documents_raw`.
3. Investigador consulta fuentes y escribe hallazgos en `external_db`.
4. Orquestador arma contexto activo con datos internos + externos.
5. Resumidor genera nueva linea en `summary_db.context_summaries`.
6. Se genera embedding y se guarda en `summary_db.context_embeddings`.
7. En la siguiente consulta, el orquestador hace retrieval semantico + filtros por cliente/contexto.

---

## 7. Reglas de consistencia para MVP

1. `append-only` para resumenes (no editar historico salvo correccion versionada).
2. Idempotencia por `execution_id + step_id` para evitar duplicados.
3. Soft delete (`deleted_at`) en vez de hard delete.
4. Todo documento con `source_refs` para trazabilidad.
5. Guardar `model_name` y `prompt_version` en outputs de agentes.

---

## 8. Modelo de colecciones (resumen corto)

- `internal_db`: negocio cliente (hechos, docs, integraciones).
- `external_db`: inteligencia externa (fuentes y hallazgos).
- `summary_db`: memoria comprimida y recuperacion vectorial.

Con esta base ya pueden implementar:

- ingestion pipeline
- research agent writer
- summarizer writer
- retrieval del orquestador para respuesta contextual

---

## 9. Siguiente paso tecnico inmediato

Definir contratos JSON (schemas) para:

1. `DecisionArtifact`
2. `ResearchFinding`
3. `ContextSummary`
4. `EmbeddingPayload`

y validar en runtime con `zod` o `json schema`.
