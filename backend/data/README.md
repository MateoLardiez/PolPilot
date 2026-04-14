# PolPilot — Base de Datos

## Estructura por empresa

Cada empresa tiene su propio directorio aislado:

```
polpilot/data/
  {empresa_id}/
    internal.sqlite       ← Datos internos del negocio
    external.sqlite       ← Datos externos (créditos, macro, regulaciones)
    memory.sqlite         ← Conversaciones y resúmenes
    vectors/              ← ChromaDB (embeddings para búsqueda semántica)
```

---

## Bases de datos

### internal.sqlite — El cerebro interno

Datos que el usuario carga sobre su empresa. **Los agentes de IA NO pueden escribir acá.**

| Tabla | Qué guarda |
|-------|-----------|
| `company_profile` | Nombre, CUIT, rubro, ubicación, empleados, facturación |
| `financials_monthly` | Ingresos, egresos, flujo de caja, saldo — por mes |
| `financial_indicators` | Márgenes, ratios, health score — por período |
| `clients` | Clientes con facturación, días de pago, morosidad |
| `suppliers` | Proveedores con precios, plazos, confiabilidad |
| `products` | Productos con margen, stock, punto de reorden |
| `employees` | Empleados con rol, sueldo, carga de trabajo |
| `documents` | Metadata de archivos cargados (excel, pdf, audio) |

### external.sqlite — El contexto externo

Datos que los agentes investigadores traen de fuentes externas.

| Tabla | Qué guarda |
|-------|-----------|
| `available_credits` | Líneas de crédito bancarias (tasa, monto, requisitos) |
| `macro_indicators` | Inflación, dólar, tasas BCRA, riesgo país |
| `regulations` | Resoluciones, decretos, comunicaciones relevantes |
| `sector_signals` | Tendencias del sector (demanda, precios, competencia) |
| `credit_profile` | Situación BCRA del CUIT (deuda, cheques rechazados) |
| `collective_intelligence` | Promedios anonimizados del sector (benchmarks) |

### memory.sqlite — La memoria conversacional

| Tabla | Qué guarda |
|-------|-----------|
| `conversations` | Sesiones de chat con resumen final |
| `messages` | Mensajes individuales con tópicos detectados |
| `summaries` | Resúmenes incrementales (append-only) |
| `query_log` | Trazas del orquestador (qué agentes se llamaron, tiempos) |

### vectors/ (ChromaDB) — Búsqueda semántica

| Collection | Contenido |
|-----------|-----------|
| `internal_docs` | Embeddings del perfil, financials, documentos |
| `external_research` | Embeddings de créditos, regulaciones, señales |
| `conversation_context` | Embeddings de resúmenes y mensajes clave |

---

## Reglas de acceso

```
                    LECTURA         ESCRITURA
                    ───────         ─────────
internal.sqlite     Todos           Solo Data Service (usuario carga datos)
external.sqlite     Todos           Agente Investigador + Agente Economía
memory.sqlite       Todos           Data Service + Orquestador
vectors/            Todos           Data Service (al ingestar/actualizar)
```

**Regla crítica:** los agentes de IA nunca escriben en `internal.sqlite`.

---

## Cómo usar

### Seed (carga inicial)

```bash
source polpilot/.venv/bin/activate
python -m polpilot.backend.seed.seed_database           # usa "empresa_demo"
python -m polpilot.backend.seed.seed_database mi_empresa # empresa custom
```

### Desde código Python

```python
from polpilot.backend.data.db import (
    get_internal_db, get_external_db, get_memory_db,
    query, insert_row, insert_many, fts_search
)
from polpilot.backend.data.vector_store import VectorStore

empresa = "empresa_demo"

# Leer datos financieros
conn = get_internal_db(empresa)
filas = query(conn, "SELECT * FROM financials_monthly WHERE year = 2026")
conn.close()

# Búsqueda full-text (BM25)
conn = get_external_db(empresa)
resultados = fts_search(conn, "fts_regulations", "importación PyME")
conn.close()

# Búsqueda semántica (ChromaDB)
vs = VectorStore(empresa)
resultados = vs.search("external_research", "crédito para importar insumos", n_results=3)
```

---

## Funciones disponibles (`data_service.py`)

### Datos internos (read-only para agentes)

| Función | Qué retorna |
|---------|-------------|
| `get_company_profile(empresa_id)` | Perfil completo de la empresa (nombre, CUIT, rubro, facturación) |
| `get_financials(empresa_id, last_n_months)` | Últimos N meses de ingresos, egresos, flujo de caja y saldos |
| `get_latest_indicators(empresa_id)` | Indicadores financieros más recientes (márgenes, ratios, health score) |
| `get_all_indicators(empresa_id)` | Todos los períodos de indicadores financieros |
| `get_clients(empresa_id, risk_level)` | Clientes, con filtro opcional por nivel de riesgo |
| `get_delinquent_clients(empresa_id, min_days)` | Clientes morosos con más de N días de atraso |
| `get_suppliers(empresa_id, primary_only)` | Proveedores, con filtro opcional de principales |
| `get_products(empresa_id, category, low_stock_only)` | Productos con filtro por categoría o stock bajo |
| `get_employees(empresa_id)` | Todos los empleados con rol, sueldo y carga |
| `get_documents(empresa_id, topic)` | Metadata de documentos cargados, con filtro por tópico |
| `get_cash_position(empresa_id)` | Resumen rápido: saldo, flujo, ratio, health score, morosos |

### Créditos y contexto externo

| Función | Qué retorna |
|---------|-------------|
| `get_available_credits(empresa_id, credit_type, max_rate)` | Créditos disponibles con filtros opcionales |
| `get_credits_for_company(empresa_id)` | Créditos cruzados con el perfil de la empresa (indica si califica) |
| `get_macro_indicators(empresa_id, indicator_name, latest_only)` | Indicadores macro (inflación, dólar, tasas) |
| `get_macro_snapshot(empresa_id)` | Dict plano con todos los indicadores macro actuales |
| `get_regulations(empresa_id, status, min_relevance)` | Regulaciones filtradas por estado y relevancia |
| `get_sector_signals(empresa_id, impact_level)` | Señales del sector (tendencias, precios, competencia) |
| `get_credit_profile(empresa_id)` | Perfil crediticio BCRA de la empresa (situación, deuda, cheques) |
| `get_collective_intelligence(empresa_id, metric_name)` | Benchmarks anonimizados del sector |
| `get_sector_benchmark(empresa_id)` | Comparación empresa vs promedio del sector |

### Memoria y conversaciones

| Función | Qué retorna |
|---------|-------------|
| `start_conversation(empresa_id)` | Crea nueva conversación, retorna conversation_id |
| `save_message(empresa_id, conversation_id, role, content, ...)` | Guarda un mensaje, retorna message_id |
| `get_conversation_messages(empresa_id, conversation_id, limit)` | Mensajes de una conversación |
| `get_recent_conversations(empresa_id, limit)` | Últimas conversaciones con resumen |
| `save_summary(empresa_id, conversation_id, summary_text, ...)` | Guarda un merge summary (append-only) |
| `get_summaries(empresa_id, conversation_id)` | Resúmenes, con filtro opcional por conversación |
| `log_query(empresa_id, original_query, agents_called, ...)` | Registra traza de ejecución del orquestador |
| `get_query_log(empresa_id, limit)` | Últimas trazas del orquestador |

### Búsqueda

| Función | Qué retorna |
|---------|-------------|
| `hybrid_search(empresa_id, query_text, domain, ...)` | Búsqueda combinada FTS5 (30%) + ChromaDB (70%) |
| `semantic_search(empresa_id, query_text, collection, ...)` | Búsqueda puramente semántica (solo ChromaDB) |

### Escritura externa (solo agentes Research y Economy)

| Función | Qué hace |
|---------|----------|
| `write_credits(empresa_id, credits)` | Agrega créditos + actualiza embeddings |
| `write_macro_indicators(empresa_id, indicators)` | Agrega indicadores macro |
| `write_regulations(empresa_id, regulations)` | Agrega regulaciones + actualiza embeddings |
| `write_sector_signals(empresa_id, signals)` | Agrega señales del sector |
| `write_credit_profile(empresa_id, profile)` | Actualiza perfil crediticio BCRA |
| `update_conversation_embeddings(empresa_id, summary_id, text)` | Agrega summary al vector store |

---

## Funciones de fetching externo (`external_fetcher.py`)

Funciones que consultan APIs públicas argentinas en tiempo real y escriben en `external.sqlite`.

### BCRA Estadísticas Monetarias v4.0

| Función | Qué obtiene |
|---------|-------------|
| `fetch_principales_variables()` | Lista completa de ~1220 variables monetarias con último valor |
| `fetch_variable_data(id_variable, desde, hasta)` | Serie temporal de una variable específica |
| `fetch_key_macro_variables()` | Último valor de las 13 variables clave para PyMEs |

### BCRA Estadísticas Cambiarias v1.0

| Función | Qué obtiene |
|---------|-------------|
| `fetch_exchange_rates(fecha)` | Cotizaciones de todas las monedas (EUR, BRL, etc.) |
| `fetch_usd_rate(fecha)` | Cotización del dólar USD oficial BCRA |
| `fetch_exchange_rate_history(moneda, desde, hasta)` | Evolución histórica de una moneda |

### DolarAPI.com — Todos los tipos de dólar

| Función | Qué obtiene |
|---------|-------------|
| `fetch_all_dollar_rates()` | Los 7 tipos de dólar: oficial, blue, MEP, CCL, cripto, tarjeta, mayorista |
| `fetch_dollar_rate(tipo)` | Un tipo de dólar específico (ej: `"blue"`, `"contadoconliqui"`) |
| `fetch_dollar_snapshot()` | Dict con todos los dólares normalizados (compra, venta, fecha) |

### BCRA Central de Deudores v1.0

| Función | Qué obtiene |
|---------|-------------|
| `fetch_deudas(cuit)` | Deudas actuales de un CUIT en el sistema financiero |
| `fetch_deudas_historicas(cuit)` | Historial de deudas de un CUIT (24 meses) |
| `fetch_cheques_rechazados(cuit)` | Cheques rechazados de un CUIT |
| `build_credit_profile_from_bcra(cuit)` | Perfil crediticio completo combinando las 3 consultas |

### BCRA Régimen de Transparencia v1.0 (catálogo de préstamos)

| Función | Qué obtiene |
|---------|-------------|
| `fetch_prestamos_personales(codigo_entidad)` | Préstamos personales de todos los bancos |
| `fetch_prestamos_prendarios(codigo_entidad)` | Préstamos con garantía (muchas líneas PyME) |
| `fetch_prestamos_hipotecarios(codigo_entidad)` | Préstamos hipotecarios |
| `fetch_plazos_fijos(codigo_entidad)` | Tasas de plazos fijos (para costo de oportunidad) |
| `fetch_all_loan_products()` | Todos los préstamos combinados en formato available_credits |
| `fetch_pyme_eligible_loans()` | Solo préstamos que mencionan PyME/MiPyME |

### BCRA Cheques Denunciados v1.0

| Función | Qué obtiene |
|---------|-------------|
| `fetch_entidades_bancarias()` | Lista de entidades bancarias con códigos |
| `fetch_cheque_denunciado(codigo_entidad, numero_cheque)` | Verifica si un cheque está denunciado |

### Funciones de sincronización (fetch → write to DB)

| Función | Qué hace |
|---------|----------|
| `sync_macro_indicators(empresa_id)` | Descarga variables macro BCRA + tipos de cambio → macro_indicators |
| `sync_credit_profile(empresa_id)` | Consulta Central de Deudores por CUIT de la empresa → credit_profile |
| `sync_available_credits(empresa_id, pyme_only)` | Descarga catálogo de préstamos BCRA → available_credits + embeddings |
| `sync_all_external_data(empresa_id)` | Ejecuta todas las sincronizaciones de una vez |

---

## Búsqueda híbrida

Cuando un agente necesita información, se combinan dos métodos:

- **30% peso** → SQLite FTS5 (búsqueda por keywords, algoritmo BM25)
- **70% peso** → ChromaDB (búsqueda semántica por embeddings)

Los resultados se rankean juntos para entregar el contexto más relevante.
