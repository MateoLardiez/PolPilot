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

## Búsqueda híbrida

Cuando un agente necesita información, se combinan dos métodos:

- **30% peso** → SQLite FTS5 (búsqueda por keywords, algoritmo BM25)
- **70% peso** → ChromaDB (búsqueda semántica por embeddings)

Los resultados se rankean juntos para entregar el contexto más relevante.
