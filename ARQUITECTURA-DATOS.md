# PolPilot — Arquitectura de Datos

> Documento de referencia para el equipo de desarrollo.
> Hackathon Anthropic — 14 de abril de 2026

---

## 1. Analisis de lo que propusieron Mateo y Diego

### Lo que dijeron

Mateo propone bases de datos para los agentes de Finanzas y Economia, sugiere NoSQL (MongoDB).

Diego propone 3 bases de datos por cliente:
1. Informacion interna del cliente
2. Informacion externa (agente investigador la llena)
3. Resumenes / vectores / embeddings

### Lo que esta bien

- La separacion conceptual en 3 bases es correcta.
- La restriccion de que agentes de IA NO pueden modificar informacion interna es CRITICA y esta bien planteada.
- Pensar en "por cliente" es correcto — cada empresa tiene su propio cerebro aislado.

### Lo que hay que corregir

**MongoDB es overkill para una hackathon.** Necesitas levantar un servidor, manejar conexiones, etc. SQLite es un archivo, sin infraestructura, y tiene FTS5 (full-text search con BM25) integrado. Para una hackathon, SQLite gana por lejos.

**No son exactamente 3 bases de datos, sino 4 conceptos de almacenamiento** (que pueden vivir en 2-3 archivos fisicos):

1. **Base Interna** (datos del cliente) — SQLite
2. **Base Externa** (datos traidos por agentes investigadores) — SQLite
3. **Base de Memoria** (conversaciones + resumenes) — SQLite
4. **Base Vectorial** (embeddings de todo lo anterior) — ChromaDB

La 4ta es necesaria porque los embeddings no van en SQLite comun — necesitan un motor de busqueda vectorial. ChromaDB es Python-native, se instala con pip, y no necesita infraestructura.

**La data de Finanzas y Economia no son "bases de datos separadas".** Son TOPICOS dentro de la base interna y la base externa respectivamente. El agente de Finanzas lee de la base interna (flujo de caja, margenes, etc.) y el agente de Economia lee de la base externa (creditos, tasas BCRA, macro). Ambos tambien leen de la base vectorial para busqueda semantica.

---

## 2. Arquitectura de Datos Definitiva

### Por cada empresa/cliente:

```
polpilot_data/
  {empresa_id}/
    internal.sqlite       ← Datos internos del negocio (SOLO LECTURA para agentes)
    external.sqlite       ← Datos externos traidos por agentes investigadores
    memory.sqlite         ← Conversaciones + merge summaries + query log
    vectors/              ← ChromaDB (embeddings de todo lo anterior)
      chroma.sqlite3
      ...
```

### Reglas de acceso (CRITICAS)

```
┌──────────────────────────────────────────────────────────┐
│                    REGLAS DE ACCESO                       │
│                                                          │
│  internal.sqlite                                         │
│    ESCRITURA: Solo el Data Service (cuando el usuario     │
│               carga datos via chat/upload)               │
│    LECTURA:   Todos los agentes                          │
│    ⛔ AGENTES DE IA NO PUEDEN ESCRIBIR AQUI              │
│                                                          │
│  external.sqlite                                         │
│    ESCRITURA: Agente Investigador + Agente Economia      │
│    LECTURA:   Todos los agentes                          │
│    ✅ Los agentes SI pueden escribir aqui                 │
│                                                          │
│  memory.sqlite                                           │
│    ESCRITURA: Data Service (merge summaries) +           │
│               Orquestador (query log)                    │
│    LECTURA:   Todos los agentes                          │
│                                                          │
│  vectors/ (ChromaDB)                                     │
│    ESCRITURA: Data Service (al ingestar/actualizar)      │
│    LECTURA:   Todos los agentes (busqueda semantica)     │
└──────────────────────────────────────────────────────────┘
```

---

## 3. Detalle de cada Base de Datos

### 3.1 internal.sqlite — El Cerebro Interno

Contiene TODO lo que el usuario carga sobre su empresa. Es la "verdad" del negocio.

```sql
-- Perfil de la empresa
CREATE TABLE company_profile (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    cuit TEXT,
    sector TEXT,
    sub_sector TEXT,
    location TEXT,
    province TEXT,
    employees_count INTEGER,
    years_in_business INTEGER,
    annual_revenue REAL,
    revenue_target REAL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Datos financieros mensuales
CREATE TABLE financials_monthly (
    id INTEGER PRIMARY KEY,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    revenue REAL,            -- ingresos
    expenses REAL,           -- egresos
    net_cash_flow REAL,      -- flujo neto
    cash_balance REAL,       -- saldo de caja
    accounts_receivable REAL,-- cuentas por cobrar
    accounts_payable REAL,   -- cuentas por pagar
    inventory_value REAL,    -- valor de inventario
    notes TEXT,
    source TEXT,             -- 'excel_upload', 'manual', 'audio', etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indicadores financieros calculados
CREATE TABLE financial_indicators (
    id INTEGER PRIMARY KEY,
    period TEXT NOT NULL,     -- '2026-03', '2026-Q1', etc.
    gross_margin REAL,
    net_margin REAL,
    roa REAL,
    roe REAL,
    current_ratio REAL,      -- razon corriente
    quick_ratio REAL,        -- prueba acida
    working_capital REAL,
    debt_to_equity REAL,
    days_receivable REAL,    -- dias de cobro
    days_payable REAL,       -- dias de pago
    inventory_turnover REAL, -- rotacion de stock
    cash_cycle REAL,         -- ciclo de caja
    health_score INTEGER,    -- 0-100
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Clientes de la empresa
CREATE TABLE clients (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    client_type TEXT,        -- 'fleet', 'workshop', 'government', 'individual'
    annual_revenue REAL,     -- facturacion anual de este cliente
    avg_payment_days INTEGER,
    outstanding_balance REAL,
    risk_level TEXT,         -- 'low', 'medium', 'high'
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Proveedores
CREATE TABLE suppliers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    avg_price_level TEXT,    -- '$', '$$', '$$$', '$$$$'
    payment_terms_days INTEGER,
    delivery_time_hours INTEGER,
    reliability_pct REAL,    -- 0-100
    is_primary BOOLEAN DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Productos / Servicios
CREATE TABLE products (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT,
    monthly_revenue REAL,
    margin_pct REAL,
    current_stock REAL,
    min_stock REAL,          -- punto de reorden
    supplier_id INTEGER REFERENCES suppliers(id),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Empleados (basico)
CREATE TABLE employees (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT,
    area TEXT,
    salary REAL,
    workload_pct REAL,       -- 0-150 (puede estar sobrecargado)
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Documentos cargados (metadata)
CREATE TABLE documents (
    id INTEGER PRIMARY KEY,
    filename TEXT NOT NULL,
    doc_type TEXT,            -- 'excel', 'pdf', 'image', 'audio'
    topic TEXT,               -- 'finanzas', 'economia', 'general'
    content_markdown TEXT,    -- contenido normalizado a markdown
    raw_path TEXT,            -- path al archivo original
    processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 3.2 external.sqlite — El Contexto Externo

Contiene informacion que los agentes investigadores traen del exterior. El usuario NO escribe aqui directamente (aunque puede complementar si quiere).

```sql
-- Creditos disponibles
CREATE TABLE available_credits (
    id INTEGER PRIMARY KEY,
    bank_name TEXT NOT NULL,
    credit_name TEXT NOT NULL,
    credit_type TEXT,          -- 'inversion', 'capital_trabajo', 'maquinaria'
    annual_rate REAL,          -- tasa TNA
    max_amount REAL,
    min_amount REAL,
    max_term_months INTEGER,
    requirements TEXT,         -- requisitos en texto
    requires_mipyme_cert BOOLEAN,
    url TEXT,
    source TEXT,               -- 'bcra_api', 'curated', 'web_scraping'
    last_verified TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indicadores macroeconomicos
CREATE TABLE macro_indicators (
    id INTEGER PRIMARY KEY,
    indicator_name TEXT NOT NULL,  -- 'tasa_referencia', 'inflacion_mensual', 'usd_oficial', etc.
    value REAL NOT NULL,
    date TEXT NOT NULL,
    source TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Regulaciones y novedades
CREATE TABLE regulations (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT,
    full_text TEXT,
    source TEXT,               -- 'boletin_oficial', 'bcra', 'arca', 'news'
    source_url TEXT,
    relevance_score REAL,      -- 0-1, que tan relevante es para ESTA empresa
    status TEXT,               -- 'pre_official', 'confirmed', 'expired'
    probability REAL,          -- para pre-oficiales: probabilidad de confirmacion
    published_date TEXT,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Senales del sector
CREATE TABLE sector_signals (
    id INTEGER PRIMARY KEY,
    signal_type TEXT,          -- 'price_change', 'demand_shift', 'competitor_move', 'supply_delay'
    description TEXT,
    sector TEXT,
    impact_level TEXT,         -- 'low', 'medium', 'high'
    data_points INTEGER,       -- cuantas fuentes lo respaldan
    source TEXT,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Perfil crediticio (BCRA Central de Deudores)
CREATE TABLE credit_profile (
    id INTEGER PRIMARY KEY,
    cuit TEXT NOT NULL,
    situation INTEGER,         -- 1-5 segun BCRA
    total_debt REAL,
    days_overdue INTEGER,
    last_24_months TEXT,       -- JSON con historial
    rejected_checks TEXT,      -- JSON con cheques rechazados
    queried_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Datos de la red PolPilot (inteligencia colectiva, anonimizado)
CREATE TABLE collective_intelligence (
    id INTEGER PRIMARY KEY,
    metric_name TEXT,          -- 'avg_margin_sector', 'avg_payment_days', 'price_trend_product'
    sector TEXT,
    region TEXT,
    value REAL,
    sample_size INTEGER,       -- cuantas empresas participan en esta metrica
    period TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 3.3 memory.sqlite — La Memoria del Cerebro

Almacena todo el contexto conversacional y los resumenes acumulados.

```sql
-- Conversaciones
CREATE TABLE conversations (
    id INTEGER PRIMARY KEY,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    total_messages INTEGER DEFAULT 0,
    summary TEXT               -- resumen final de la conversacion
);

-- Mensajes individuales
CREATE TABLE messages (
    id INTEGER PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations(id),
    role TEXT NOT NULL,         -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    message_type TEXT,          -- 'query', 'response', 'follow_up', 'trivial'
    topics_detected TEXT,       -- JSON: ['finanzas', 'economia']
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Merge Summaries (resumenes incrementales)
CREATE TABLE summaries (
    id INTEGER PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations(id),
    summary_text TEXT NOT NULL,
    context_window INTEGER,    -- cuantos mensajes cubre
    key_facts TEXT,            -- JSON: hechos clave extraidos
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Query Log (para el orquestador)
CREATE TABLE query_log (
    id INTEGER PRIMARY KEY,
    original_query TEXT,
    expanded_questions TEXT,    -- JSON: las N preguntas generadas
    agents_called TEXT,         -- JSON: ['finanzas', 'economia']
    agent_responses TEXT,       -- JSON: respuesta de cada agente
    final_response TEXT,
    validation_passed BOOLEAN,
    processing_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 3.4 vectors/ — ChromaDB (Base Vectorial)

Almacena embeddings de todo lo anterior para busqueda semantica.

**Collections:**

| Collection | Que contiene | Se actualiza cuando... |
|-----------|-------------|----------------------|
| `internal_docs` | Embeddings de documentos, financials, perfil empresa | Usuario carga datos |
| `external_research` | Embeddings de creditos, regulaciones, senales sector | Agente investigador trae info |
| `conversation_context` | Embeddings de resumenes y mensajes clave | Se genera un merge summary |

**Retrieval hibrido:** Cuando un agente necesita informacion, busca en AMBOS:
- 30% peso: SQLite FTS5 (busqueda por keywords, algoritmo BM25)
- 70% peso: ChromaDB (busqueda semantica por embeddings)

Los resultados se combinan y rankean para entregar el contexto mas relevante al agente.

---

## 4. Que lee cada agente

```
┌─────────────────────────────────────────────────────────────┐
│ AGENTE FINANZAS                                             │
│                                                             │
│ Lee de internal.sqlite:                                     │
│   - financials_monthly (flujo de caja, ingresos, egresos)   │
│   - financial_indicators (margenes, ratios, health score)   │
│   - clients (morosos, facturacion por cliente)              │
│   - products (rentabilidad por producto)                    │
│   - documents (excels cargados, recibos)                    │
│                                                             │
│ Lee de external.sqlite:                                     │
│   - available_credits (para cruzar con capacidad de pago)   │
│   - macro_indicators (inflacion, tasas — para proyectar)    │
│                                                             │
│ Lee de vectors/:                                            │
│   - internal_docs (busqueda semantica sobre datos internos) │
│                                                             │
│ ⛔ NO ESCRIBE EN NINGUNA BASE                               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ AGENTE ECONOMIA                                             │
│                                                             │
│ Lee de internal.sqlite:                                     │
│   - company_profile (para saber tamaño, rubro, ubicacion)   │
│   - financial_indicators (para pre-calificar creditos)      │
│                                                             │
│ Lee de external.sqlite:                                     │
│   - available_credits (creditos activos)                    │
│   - macro_indicators (tasas, inflacion, dolar)              │
│   - regulations (regulaciones nuevas)                       │
│   - sector_signals (tendencias del sector)                  │
│   - credit_profile (perfil BCRA por CUIT)                   │
│   - collective_intelligence (datos de la red)               │
│                                                             │
│ Lee de vectors/:                                            │
│   - external_research (busqueda semantica sobre datos ext.) │
│                                                             │
│ ✅ PUEDE ESCRIBIR en external.sqlite                         │
│    (cuando consulta APIs de BCRA, trae creditos nuevos)     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ AGENTE INVESTIGADOR                                         │
│                                                             │
│ Lee de internal.sqlite:                                     │
│   - company_profile (para saber QUE buscar)                 │
│                                                             │
│ Lee de external.sqlite:                                     │
│   - Todo (para no duplicar informacion)                     │
│                                                             │
│ ✅ PUEDE ESCRIBIR en external.sqlite                         │
│    (regulations, sector_signals, macro_indicators)           │
│                                                             │
│ ⛔ NO PUEDE ESCRIBIR EN internal.sqlite                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. Carga inicial de datos (Onboarding)

### El producto se adapta a la informacion DISPONIBLE

No hay "informacion minima obligatoria" para arrancar. El sistema funciona con lo que haya, y mejora a medida que se carga mas:

| Nivel | Que tiene el usuario | Que puede hacer PolPilot |
|-------|---------------------|-------------------------|
| **Nivel 0** | Solo nombre y CUIT | Consultar perfil crediticio BCRA, mostrar creditos genericos |
| **Nivel 1** | + Rubro y ubicacion | Filtrar creditos por sector, mostrar senales del sector |
| **Nivel 2** | + Facturacion anual | Pre-calificar para creditos especificos, benchmark basico vs sector |
| **Nivel 3** | + Excel con flujo de caja | Health Score, proyecciones, alertas de liquidez, cruce creditos/caja |
| **Nivel 4** | + Clientes, proveedores, stock | Recomendaciones de compra, alertas de morosidad, comparador proveedores |
| **Nivel 5** | + Historial conversacional | Contexto completo, estacionalidad aprendida, alertas proactivas |

**Angela va guiando al usuario:** "Para poder darte mejores recomendaciones de creditos, necesito que me cargues tu flujo de caja de los ultimos 6 meses. Puede ser un Excel, una foto de la planilla, o decimelo por audio."

### Formatos aceptados para carga

| Formato | Como se procesa |
|---------|----------------|
| Excel / CSV | Se parsea, se mapea a tablas de internal.sqlite |
| PDF | Se extrae texto, se normaliza a Markdown, se guarda en documents |
| Imagen (foto de remito, recibo) | Se procesa con vision (Claude), se extrae data estructurada |
| Audio (WhatsApp, grabacion) | Se transcribe, se parsea intencion + datos, se guarda |
| Texto (chat) | Se clasifica y se rutea al topico correspondiente |

Todo se normaliza a **Markdown** antes de generar embeddings, porque es el formato que los LLMs consumen con mayor precision.

---

## 6. Fuentes externas reales para llenar external.sqlite

| Fuente | API disponible | Auth | Que trae | Prioridad |
|--------|---------------|------|----------|-----------|
| BCRA Transparencia | Si, REST JSON | Sin auth | Tasas por banco, condiciones, diaria | ALTA |
| BCRA Central Deudores | Si, REST JSON | Sin auth, por CUIT | Perfil crediticio, historial 24 meses | ALTA |
| BCRA Variables | Si, REST JSON | Token gratis (email) | Tasas referencia, inflacion, dolar, reservas | MEDIA |
| Banco Provincia | No (datos curados) | N/A | Lineas PyME: montos, tasas, requisitos | MEDIA |
| Banco Galicia | No (datos curados) | N/A | Lineas PyME: montos, tasas, requisitos | MEDIA |
| Boletin Oficial | No (scraping manual) | N/A | Regulaciones, programas nuevos | BAJA |

Para la hackathon: las APIs del BCRA son GRATIS y sin auth. Las usamos en tiempo real. Los datos de bancos los curamos a mano en JSON.

---

## 7. Implementacion para la Hackathon

### Que se instala

```
pip install anthropic chromadb sqlite-utils fastapi uvicorn
```

Eso es todo. Sin Docker, sin MongoDB, sin Redis. Archivos SQLite + ChromaDB + FastAPI.

### Seed de datos para la demo

Generar 7 archivos JSON que se cargan al iniciar:

1. `seed_company_profile.json` — Perfil de la empresa ejemplo
2. `seed_financials.json` — 12 meses de ingresos/egresos/caja
3. `seed_indicators.json` — Indicadores financieros calculados
4. `seed_clients.json` — 5 clientes con facturacion y morosidad
5. `seed_suppliers.json` — 3 proveedores con precios y confiabilidad
6. `seed_products.json` — 6 productos con margenes y stock
7. `seed_credits.json` — 5-8 lineas de credito reales (Provincia, Galicia, BCRA)

Un script `seed_database.py` lee estos JSON y llena internal.sqlite + external.sqlite.

### Estructura de archivos del proyecto

```
polpilot/
  backend/
    main.py                  ← FastAPI app (API Gateway)
    orchestrator.py          ← Orquestador (cerebro core)
    agents/
      finance_agent.py       ← Agente Finanzas
      economy_agent.py       ← Agente Economia
      research_agent.py      ← Agente Investigador
      classifier_agent.py    ← Clasificador (Haiku)
      summary_agent.py       ← Merge Summaries (Haiku)
      validator_agent.py     ← Stop-Loss / Validador
    data/
      data_service.py        ← Ingesta + embeddings + clasificacion
      db.py                  ← Conexiones SQLite + helpers
      vector_store.py        ← ChromaDB wrapper
    seed/
      seed_database.py       ← Script de carga inicial
      seed_company_profile.json
      seed_financials.json
      seed_indicators.json
      seed_clients.json
      seed_suppliers.json
      seed_products.json
      seed_credits.json
  frontend/
    index.html               ← Web app (adaptada de la POC)
    styles.css
    app.js
  data/                      ← Carpeta de datos (se genera al correr)
    empresa_demo/
      internal.sqlite
      external.sqlite
      memory.sqlite
      vectors/
```
