"""
PolPilot — Módulo de base de datos SQLite.

Gestiona las 3 bases de datos por empresa:
  - internal.sqlite: datos internos del negocio (SOLO LECTURA para agentes)
  - external.sqlite: datos externos traídos por agentes investigadores
  - memory.sqlite:   conversaciones + merge summaries + query log

Cada empresa tiene su propio directorio aislado bajo DATA_ROOT/{empresa_id}/.
"""

import sqlite3
from pathlib import Path
from typing import Optional

DATA_ROOT = Path(__file__).resolve().parent.parent.parent / "data"


# ---------------------------------------------------------------------------
# Conexiones
# ---------------------------------------------------------------------------

def _connect(db_path: Path) -> sqlite3.Connection:
    """Abre una conexión SQLite con WAL mode y foreign keys activados."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def get_internal_db(empresa_id: str) -> sqlite3.Connection:
    return _connect(DATA_ROOT / empresa_id / "internal.sqlite")


def get_external_db(empresa_id: str) -> sqlite3.Connection:
    return _connect(DATA_ROOT / empresa_id / "external.sqlite")


def get_memory_db(empresa_id: str) -> sqlite3.Connection:
    return _connect(DATA_ROOT / empresa_id / "memory.sqlite")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

INTERNAL_SCHEMA = """
-- Perfil de la empresa
CREATE TABLE IF NOT EXISTS company_profile (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    cuit        TEXT,
    sector      TEXT,
    sub_sector  TEXT,
    location    TEXT,
    province    TEXT,
    employees_count  INTEGER,
    years_in_business INTEGER,
    annual_revenue   REAL,
    revenue_target   REAL,
    description TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Datos financieros mensuales
CREATE TABLE IF NOT EXISTS financials_monthly (
    id          INTEGER PRIMARY KEY,
    year        INTEGER NOT NULL,
    month       INTEGER NOT NULL,
    revenue     REAL,
    expenses    REAL,
    net_cash_flow REAL,
    cash_balance  REAL,
    accounts_receivable REAL,
    accounts_payable    REAL,
    inventory_value     REAL,
    notes       TEXT,
    source      TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_financials_period ON financials_monthly(year, month);

-- Indicadores financieros calculados
CREATE TABLE IF NOT EXISTS financial_indicators (
    id          INTEGER PRIMARY KEY,
    period      TEXT NOT NULL,
    gross_margin     REAL,
    net_margin       REAL,
    roa              REAL,
    roe              REAL,
    current_ratio    REAL,
    quick_ratio      REAL,
    working_capital  REAL,
    debt_to_equity   REAL,
    days_receivable  REAL,
    days_payable     REAL,
    inventory_turnover REAL,
    cash_cycle       REAL,
    health_score     INTEGER,
    calculated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_indicators_period ON financial_indicators(period);

-- Clientes de la empresa
CREATE TABLE IF NOT EXISTS clients (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    client_type TEXT,
    annual_revenue   REAL,
    avg_payment_days INTEGER,
    outstanding_balance REAL,
    risk_level  TEXT,
    notes       TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Proveedores
CREATE TABLE IF NOT EXISTS suppliers (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    avg_price_level    TEXT,
    payment_terms_days INTEGER,
    delivery_time_hours INTEGER,
    reliability_pct    REAL,
    is_primary  BOOLEAN DEFAULT FALSE,
    notes       TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Productos / Servicios
CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    category    TEXT,
    monthly_revenue REAL,
    margin_pct  REAL,
    current_stock   REAL,
    min_stock   REAL,
    supplier_id INTEGER REFERENCES suppliers(id),
    notes       TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_products_supplier ON products(supplier_id);

-- Empleados
CREATE TABLE IF NOT EXISTS employees (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    role        TEXT,
    area        TEXT,
    salary      REAL,
    workload_pct REAL,
    notes       TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Documentos cargados (metadata)
CREATE TABLE IF NOT EXISTS documents (
    id          INTEGER PRIMARY KEY,
    filename    TEXT NOT NULL,
    doc_type    TEXT,
    topic       TEXT,
    content_markdown TEXT,
    raw_path    TEXT,
    processed   BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

EXTERNAL_SCHEMA = """
-- Créditos disponibles
CREATE TABLE IF NOT EXISTS available_credits (
    id          INTEGER PRIMARY KEY,
    bank_name   TEXT NOT NULL,
    credit_name TEXT NOT NULL,
    credit_type TEXT,
    annual_rate REAL,
    max_amount  REAL,
    min_amount  REAL,
    max_term_months INTEGER,
    requirements    TEXT,
    requires_mipyme_cert BOOLEAN,
    url         TEXT,
    source      TEXT,
    last_verified   TIMESTAMP,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_credits_bank ON available_credits(bank_name);

-- Indicadores macroeconómicos
CREATE TABLE IF NOT EXISTS macro_indicators (
    id          INTEGER PRIMARY KEY,
    indicator_name TEXT NOT NULL,
    value       REAL NOT NULL,
    date        TEXT NOT NULL,
    source      TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_macro_date ON macro_indicators(date);
CREATE INDEX IF NOT EXISTS idx_macro_name ON macro_indicators(indicator_name);

-- Regulaciones y novedades
CREATE TABLE IF NOT EXISTS regulations (
    id          INTEGER PRIMARY KEY,
    title       TEXT NOT NULL,
    summary     TEXT,
    full_text   TEXT,
    source      TEXT,
    source_url  TEXT,
    relevance_score REAL,
    status      TEXT,
    probability REAL,
    published_date  TEXT,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Señales del sector
CREATE TABLE IF NOT EXISTS sector_signals (
    id          INTEGER PRIMARY KEY,
    signal_type TEXT,
    description TEXT,
    sector      TEXT,
    impact_level TEXT,
    data_points INTEGER,
    source      TEXT,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_signals_sector ON sector_signals(sector);

-- Perfil crediticio (BCRA Central de Deudores)
CREATE TABLE IF NOT EXISTS credit_profile (
    id          INTEGER PRIMARY KEY,
    cuit        TEXT NOT NULL,
    situation   INTEGER,
    total_debt  REAL,
    days_overdue INTEGER,
    last_24_months TEXT,
    rejected_checks TEXT,
    queried_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_credit_cuit ON credit_profile(cuit);

-- Inteligencia colectiva (datos anonimizados de la red PolPilot)
CREATE TABLE IF NOT EXISTS collective_intelligence (
    id          INTEGER PRIMARY KEY,
    metric_name TEXT,
    sector      TEXT,
    region      TEXT,
    value       REAL,
    sample_size INTEGER,
    period      TEXT,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

MEMORY_SCHEMA = """
-- Conversaciones
CREATE TABLE IF NOT EXISTS conversations (
    id          INTEGER PRIMARY KEY,
    started_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at    TIMESTAMP,
    total_messages INTEGER DEFAULT 0,
    summary     TEXT
);

-- Mensajes individuales
CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations(id),
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    message_type TEXT,
    topics_detected TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);

-- Merge Summaries (resúmenes incrementales, append-only)
CREATE TABLE IF NOT EXISTS summaries (
    id          INTEGER PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations(id),
    summary_text    TEXT NOT NULL,
    context_window  INTEGER,
    key_facts       TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Query Log (trazas del orquestador)
CREATE TABLE IF NOT EXISTS query_log (
    id          INTEGER PRIMARY KEY,
    original_query      TEXT,
    expanded_questions  TEXT,
    agents_called       TEXT,
    agent_responses     TEXT,
    final_response      TEXT,
    validation_passed   BOOLEAN,
    processing_time_ms  INTEGER,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# ---------------------------------------------------------------------------
# FTS5 — Full-Text Search (BM25) para búsqueda híbrida
# ---------------------------------------------------------------------------

INTERNAL_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS fts_documents USING fts5(
    filename, topic, content_markdown,
    content='documents',
    content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
    INSERT INTO fts_documents(rowid, filename, topic, content_markdown)
    VALUES (new.id, new.filename, new.topic, new.content_markdown);
END;

CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
    INSERT INTO fts_documents(fts_documents, rowid, filename, topic, content_markdown)
    VALUES ('delete', old.id, old.filename, old.topic, old.content_markdown);
END;
"""

EXTERNAL_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS fts_regulations USING fts5(
    title, summary, full_text,
    content='regulations',
    content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS regulations_ai AFTER INSERT ON regulations BEGIN
    INSERT INTO fts_regulations(rowid, title, summary, full_text)
    VALUES (new.id, new.title, new.summary, new.full_text);
END;

CREATE TRIGGER IF NOT EXISTS regulations_ad AFTER DELETE ON regulations BEGIN
    INSERT INTO fts_regulations(fts_regulations, rowid, title, summary, full_text)
    VALUES ('delete', old.id, old.title, old.summary, old.full_text);
END;
"""

MEMORY_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS fts_messages USING fts5(
    content, topics_detected,
    content='messages',
    content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
    INSERT INTO fts_messages(rowid, content, topics_detected)
    VALUES (new.id, new.content, new.topics_detected);
END;

CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
    INSERT INTO fts_messages(fts_messages, rowid, content, topics_detected)
    VALUES ('delete', old.id, old.content, old.topics_detected);
END;
"""


# ---------------------------------------------------------------------------
# Inicialización
# ---------------------------------------------------------------------------

def init_databases(empresa_id: str) -> None:
    """Crea las 3 bases de datos con sus schemas, índices y FTS5."""

    internal = get_internal_db(empresa_id)
    internal.executescript(INTERNAL_SCHEMA)
    internal.executescript(INTERNAL_FTS)
    internal.close()

    external = get_external_db(empresa_id)
    external.executescript(EXTERNAL_SCHEMA)
    external.executescript(EXTERNAL_FTS)
    external.close()

    memory = get_memory_db(empresa_id)
    memory.executescript(MEMORY_SCHEMA)
    memory.executescript(MEMORY_FTS)
    memory.close()


# ---------------------------------------------------------------------------
# Helpers de lectura / escritura
# ---------------------------------------------------------------------------

def insert_row(conn: sqlite3.Connection, table: str, data: dict) -> int:
    """Inserta un dict como fila en la tabla dada. Retorna el rowid."""
    columns = ", ".join(data.keys())
    placeholders = ", ".join(["?"] * len(data))
    sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
    cursor = conn.execute(sql, list(data.values()))
    conn.commit()
    return cursor.lastrowid


def insert_many(conn: sqlite3.Connection, table: str, rows: list[dict]) -> int:
    """Inserta múltiples filas. Retorna cantidad insertada."""
    if not rows:
        return 0
    columns = ", ".join(rows[0].keys())
    placeholders = ", ".join(["?"] * len(rows[0]))
    sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
    conn.executemany(sql, [list(r.values()) for r in rows])
    conn.commit()
    return len(rows)


def query(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    """Ejecuta un SELECT y retorna lista de dicts."""
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def fts_search(conn: sqlite3.Connection, fts_table: str, term: str, limit: int = 10) -> list[dict]:
    """Búsqueda full-text con BM25 ranking."""
    sql = f"""
        SELECT *, rank
        FROM {fts_table}
        WHERE {fts_table} MATCH ?
        ORDER BY rank
        LIMIT ?
    """
    rows = conn.execute(sql, (term, limit)).fetchall()
    return [dict(r) for r in rows]
