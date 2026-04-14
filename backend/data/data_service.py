"""
PolPilot — Data Service.

Funciones de acceso a datos que los agentes de IA invocan.
Cada función abre y cierra su propia conexión (stateless).

Organización:
  1. Perfil y datos internos     — get_company_*, get_financials_*, get_clients_*, ...
  2. Créditos y macro             — get_credits_*, get_macro_*, get_regulations_*, ...
  3. Memoria y conversaciones     — get_conversation_*, save_message, save_summary, ...
  4. Búsqueda híbrida             — hybrid_search
  5. Escritura externa            — write_* (solo Research y Economy agents)
"""

import json
from datetime import datetime

from .db import (
    get_internal_db,
    get_external_db,
    get_memory_db,
    query,
    insert_row,
    insert_many,
    fts_search,
)
from .vector_store import VectorStore


# ═══════════════════════════════════════════════════════════════════════════
# 1. PERFIL Y DATOS INTERNOS (internal.sqlite — SOLO LECTURA para agentes)
# ═══════════════════════════════════════════════════════════════════════════

def get_company_profile(empresa_id: str) -> dict | None:
    """Retorna el perfil completo de la empresa."""
    conn = get_internal_db(empresa_id)
    rows = query(conn, "SELECT * FROM company_profile LIMIT 1")
    conn.close()
    return rows[0] if rows else None


def get_financials(
    empresa_id: str,
    last_n_months: int = 6,
) -> list[dict]:
    """Retorna los últimos N meses de datos financieros, ordenados cronológicamente."""
    conn = get_internal_db(empresa_id)
    rows = query(
        conn,
        """
        SELECT * FROM financials_monthly
        ORDER BY year DESC, month DESC
        LIMIT ?
        """,
        (last_n_months,),
    )
    conn.close()
    return list(reversed(rows))


def get_latest_indicators(empresa_id: str) -> dict | None:
    """Retorna los indicadores financieros más recientes."""
    conn = get_internal_db(empresa_id)
    rows = query(
        conn,
        "SELECT * FROM financial_indicators ORDER BY calculated_at DESC LIMIT 1",
    )
    conn.close()
    return rows[0] if rows else None


def get_all_indicators(empresa_id: str) -> list[dict]:
    """Retorna todos los períodos de indicadores financieros."""
    conn = get_internal_db(empresa_id)
    rows = query(conn, "SELECT * FROM financial_indicators ORDER BY period DESC")
    conn.close()
    return rows


def get_clients(
    empresa_id: str,
    risk_level: str | None = None,
) -> list[dict]:
    """Retorna clientes, opcionalmente filtrados por nivel de riesgo."""
    conn = get_internal_db(empresa_id)
    if risk_level:
        rows = query(
            conn,
            "SELECT * FROM clients WHERE risk_level = ? ORDER BY annual_revenue DESC",
            (risk_level,),
        )
    else:
        rows = query(conn, "SELECT * FROM clients ORDER BY annual_revenue DESC")
    conn.close()
    return rows


def get_delinquent_clients(empresa_id: str, min_days: int = 90) -> list[dict]:
    """Retorna clientes morosos con más de N días de atraso."""
    conn = get_internal_db(empresa_id)
    rows = query(
        conn,
        "SELECT * FROM clients WHERE avg_payment_days >= ? ORDER BY outstanding_balance DESC",
        (min_days,),
    )
    conn.close()
    return rows


def get_suppliers(empresa_id: str, primary_only: bool = False) -> list[dict]:
    """Retorna proveedores, opcionalmente solo los principales."""
    conn = get_internal_db(empresa_id)
    if primary_only:
        rows = query(conn, "SELECT * FROM suppliers WHERE is_primary = 1")
    else:
        rows = query(conn, "SELECT * FROM suppliers ORDER BY reliability_pct DESC")
    conn.close()
    return rows


def get_products(
    empresa_id: str,
    category: str | None = None,
    low_stock_only: bool = False,
) -> list[dict]:
    """Retorna productos. Puede filtrar por categoría o stock bajo."""
    conn = get_internal_db(empresa_id)
    if low_stock_only:
        rows = query(
            conn,
            "SELECT * FROM products WHERE current_stock <= min_stock ORDER BY current_stock ASC",
        )
    elif category:
        rows = query(
            conn,
            "SELECT * FROM products WHERE category = ? ORDER BY monthly_revenue DESC",
            (category,),
        )
    else:
        rows = query(conn, "SELECT * FROM products ORDER BY monthly_revenue DESC")
    conn.close()
    return rows


def get_employees(empresa_id: str) -> list[dict]:
    """Retorna todos los empleados."""
    conn = get_internal_db(empresa_id)
    rows = query(conn, "SELECT * FROM employees ORDER BY salary DESC")
    conn.close()
    return rows


def get_documents(
    empresa_id: str,
    topic: str | None = None,
) -> list[dict]:
    """Retorna metadata de documentos cargados."""
    conn = get_internal_db(empresa_id)
    if topic:
        rows = query(
            conn,
            "SELECT * FROM documents WHERE topic = ? ORDER BY created_at DESC",
            (topic,),
        )
    else:
        rows = query(conn, "SELECT * FROM documents ORDER BY created_at DESC")
    conn.close()
    return rows


def get_cash_position(empresa_id: str) -> dict:
    """Resumen rápido de la posición de caja actual.
    Combina el último mes financiero + indicadores + morosos.
    Útil para el agente de Finanzas."""
    latest_fin = get_financials(empresa_id, last_n_months=1)
    indicators = get_latest_indicators(empresa_id)
    morosos = get_delinquent_clients(empresa_id)

    fin = latest_fin[0] if latest_fin else {}
    return {
        "cash_balance": fin.get("cash_balance", 0),
        "net_cash_flow": fin.get("net_cash_flow", 0),
        "accounts_receivable": fin.get("accounts_receivable", 0),
        "accounts_payable": fin.get("accounts_payable", 0),
        "current_ratio": indicators.get("current_ratio") if indicators else None,
        "health_score": indicators.get("health_score") if indicators else None,
        "total_overdue": sum(c.get("outstanding_balance", 0) for c in morosos),
        "delinquent_count": len(morosos),
    }


# ═══════════════════════════════════════════════════════════════════════════
# 2. CRÉDITOS, MACRO Y CONTEXTO EXTERNO (external.sqlite)
# ═══════════════════════════════════════════════════════════════════════════

def get_available_credits(
    empresa_id: str,
    credit_type: str | None = None,
    max_rate: float | None = None,
) -> list[dict]:
    """Retorna créditos disponibles con filtros opcionales."""
    conn = get_external_db(empresa_id)
    conditions = []
    params: list = []

    if credit_type:
        conditions.append("credit_type = ?")
        params.append(credit_type)
    if max_rate is not None:
        conditions.append("annual_rate <= ?")
        params.append(max_rate)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = query(
        conn,
        f"SELECT * FROM available_credits {where} ORDER BY annual_rate ASC",
        tuple(params),
    )
    conn.close()
    return rows


def get_credits_for_company(empresa_id: str) -> list[dict]:
    """Cruza el perfil de la empresa con los créditos disponibles.
    Retorna créditos con un campo extra 'matches_profile' indicando
    si la empresa podría calificar basándose en datos básicos."""
    profile = get_company_profile(empresa_id)
    credits = get_available_credits(empresa_id)
    indicators = get_latest_indicators(empresa_id)

    if not profile:
        return credits

    has_mipyme = profile.get("annual_revenue", 0) > 0  # simplificado para hackathon
    annual_rev = profile.get("annual_revenue", 0)

    for credit in credits:
        reasons_ok = []
        reasons_fail = []

        # Check MiPyME cert requirement
        if credit.get("requires_mipyme_cert"):
            if has_mipyme:
                reasons_ok.append("Tiene certificado PyME")
            else:
                reasons_fail.append("Requiere certificado PyME")

        # Check amount vs revenue (heuristic: max credit < 80% annual revenue)
        max_amount = credit.get("max_amount", 0)
        if max_amount and annual_rev:
            if max_amount <= annual_rev * 0.8:
                reasons_ok.append(f"Monto ({max_amount:,.0f}) dentro del rango de facturación")
            else:
                reasons_fail.append(f"Monto máximo ({max_amount:,.0f}) alto vs facturación")

        # Check current_ratio if available
        if indicators and indicators.get("current_ratio"):
            cr = indicators["current_ratio"]
            if cr >= 1.0:
                reasons_ok.append(f"Liquidez corriente {cr:.2f} >= 1.0")
            else:
                reasons_fail.append(f"Liquidez corriente {cr:.2f} < 1.0 (ajustado)")

        credit["matches_profile"] = len(reasons_fail) == 0
        credit["qualification_reasons_ok"] = reasons_ok
        credit["qualification_reasons_fail"] = reasons_fail

    return credits


def get_macro_indicators(
    empresa_id: str,
    indicator_name: str | None = None,
    latest_only: bool = True,
) -> list[dict]:
    """Retorna indicadores macroeconómicos."""
    conn = get_external_db(empresa_id)
    if indicator_name and latest_only:
        rows = query(
            conn,
            "SELECT * FROM macro_indicators WHERE indicator_name = ? ORDER BY date DESC LIMIT 1",
            (indicator_name,),
        )
    elif indicator_name:
        rows = query(
            conn,
            "SELECT * FROM macro_indicators WHERE indicator_name = ? ORDER BY date DESC",
            (indicator_name,),
        )
    else:
        rows = query(
            conn,
            """
            SELECT * FROM macro_indicators
            WHERE id IN (
                SELECT MAX(id) FROM macro_indicators GROUP BY indicator_name
            )
            ORDER BY indicator_name
            """,
        )
    conn.close()
    return rows


def get_macro_snapshot(empresa_id: str) -> dict:
    """Retorna un snapshot de todos los indicadores macro actuales como dict plano."""
    indicators = get_macro_indicators(empresa_id, latest_only=True)
    return {row["indicator_name"]: row["value"] for row in indicators}


def get_regulations(
    empresa_id: str,
    status: str | None = "confirmed",
    min_relevance: float = 0.0,
) -> list[dict]:
    """Retorna regulaciones filtradas por status y relevancia mínima."""
    conn = get_external_db(empresa_id)
    rows = query(
        conn,
        """
        SELECT * FROM regulations
        WHERE (? IS NULL OR status = ?) AND relevance_score >= ?
        ORDER BY relevance_score DESC
        """,
        (status, status, min_relevance),
    )
    conn.close()
    return rows


def get_sector_signals(
    empresa_id: str,
    impact_level: str | None = None,
) -> list[dict]:
    """Retorna señales del sector."""
    conn = get_external_db(empresa_id)
    if impact_level:
        rows = query(
            conn,
            "SELECT * FROM sector_signals WHERE impact_level = ? ORDER BY detected_at DESC",
            (impact_level,),
        )
    else:
        rows = query(conn, "SELECT * FROM sector_signals ORDER BY detected_at DESC")
    conn.close()
    return rows


def get_credit_profile(empresa_id: str) -> dict | None:
    """Retorna el perfil crediticio BCRA de la empresa (por CUIT)."""
    profile = get_company_profile(empresa_id)
    if not profile or not profile.get("cuit"):
        return None

    conn = get_external_db(empresa_id)
    rows = query(
        conn,
        "SELECT * FROM credit_profile WHERE cuit = ? ORDER BY queried_at DESC LIMIT 1",
        (profile["cuit"],),
    )
    conn.close()
    if not rows:
        return None

    result = rows[0]
    # Parsear JSON fields
    if result.get("last_24_months") and isinstance(result["last_24_months"], str):
        result["last_24_months"] = json.loads(result["last_24_months"])
    if result.get("rejected_checks") and isinstance(result["rejected_checks"], str):
        result["rejected_checks"] = json.loads(result["rejected_checks"])
    return result


def get_collective_intelligence(
    empresa_id: str,
    metric_name: str | None = None,
) -> list[dict]:
    """Retorna benchmarks anonimizados del sector."""
    conn = get_external_db(empresa_id)
    if metric_name:
        rows = query(
            conn,
            "SELECT * FROM collective_intelligence WHERE metric_name = ? ORDER BY updated_at DESC",
            (metric_name,),
        )
    else:
        rows = query(conn, "SELECT * FROM collective_intelligence ORDER BY metric_name")
    conn.close()
    return rows


def get_sector_benchmark(empresa_id: str) -> dict:
    """Compara los indicadores de la empresa contra el promedio del sector."""
    indicators = get_latest_indicators(empresa_id)
    benchmarks = get_collective_intelligence(empresa_id)

    comparison = {}
    bench_map = {b["metric_name"]: b["value"] for b in benchmarks}

    if indicators and "avg_margin_sector" in bench_map:
        company_margin = indicators.get("gross_margin", 0)
        sector_margin = bench_map["avg_margin_sector"]
        comparison["gross_margin"] = {
            "company": company_margin,
            "sector_avg": sector_margin,
            "diff": company_margin - sector_margin,
            "status": "above" if company_margin > sector_margin else "below",
        }

    if indicators and "avg_payment_days" in bench_map:
        company_days = indicators.get("days_receivable", 0)
        sector_days = bench_map["avg_payment_days"]
        comparison["payment_days"] = {
            "company": company_days,
            "sector_avg": sector_days,
            "diff": company_days - sector_days,
            "status": "better" if company_days < sector_days else "worse",
        }

    return comparison


# ═══════════════════════════════════════════════════════════════════════════
# 3. MEMORIA Y CONVERSACIONES (memory.sqlite)
# ═══════════════════════════════════════════════════════════════════════════

def start_conversation(empresa_id: str) -> int:
    """Crea una nueva conversación. Retorna el conversation_id."""
    conn = get_memory_db(empresa_id)
    cid = insert_row(conn, "conversations", {})
    conn.close()
    return cid


def save_message(
    empresa_id: str,
    conversation_id: int,
    role: str,
    content: str,
    message_type: str = "query",
    topics: list[str] | None = None,
) -> int:
    """Guarda un mensaje. Retorna el message_id."""
    conn = get_memory_db(empresa_id)
    mid = insert_row(conn, "messages", {
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
        "message_type": message_type,
        "topics_detected": json.dumps(topics) if topics else None,
    })
    # Actualizar contador
    conn.execute(
        "UPDATE conversations SET total_messages = total_messages + 1 WHERE id = ?",
        (conversation_id,),
    )
    conn.commit()
    conn.close()
    return mid


def get_conversation_messages(
    empresa_id: str,
    conversation_id: int,
    limit: int = 50,
) -> list[dict]:
    """Retorna mensajes de una conversación."""
    conn = get_memory_db(empresa_id)
    rows = query(
        conn,
        "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC LIMIT ?",
        (conversation_id, limit),
    )
    conn.close()
    return rows


def get_recent_conversations(empresa_id: str, limit: int = 5) -> list[dict]:
    """Retorna las últimas conversaciones con su resumen."""
    conn = get_memory_db(empresa_id)
    rows = query(
        conn,
        "SELECT * FROM conversations ORDER BY started_at DESC LIMIT ?",
        (limit,),
    )
    conn.close()
    return rows


def save_summary(
    empresa_id: str,
    conversation_id: int,
    summary_text: str,
    context_window: int,
    key_facts: list[str] | None = None,
) -> int:
    """Guarda un merge summary (append-only). Retorna el summary_id."""
    conn = get_memory_db(empresa_id)
    sid = insert_row(conn, "summaries", {
        "conversation_id": conversation_id,
        "summary_text": summary_text,
        "context_window": context_window,
        "key_facts": json.dumps(key_facts) if key_facts else None,
    })
    conn.close()
    return sid


def get_summaries(empresa_id: str, conversation_id: int | None = None) -> list[dict]:
    """Retorna resúmenes, opcionalmente filtrados por conversación."""
    conn = get_memory_db(empresa_id)
    if conversation_id:
        rows = query(
            conn,
            "SELECT * FROM summaries WHERE conversation_id = ? ORDER BY created_at ASC",
            (conversation_id,),
        )
    else:
        rows = query(conn, "SELECT * FROM summaries ORDER BY created_at DESC LIMIT 20")
    conn.close()
    return rows


def log_query(
    empresa_id: str,
    original_query: str,
    expanded_questions: list[str],
    agents_called: list[str],
    agent_responses: dict,
    final_response: str,
    validation_passed: bool,
    processing_time_ms: int,
) -> int:
    """Registra una traza de ejecución del orquestador."""
    conn = get_memory_db(empresa_id)
    qid = insert_row(conn, "query_log", {
        "original_query": original_query,
        "expanded_questions": json.dumps(expanded_questions),
        "agents_called": json.dumps(agents_called),
        "agent_responses": json.dumps(agent_responses),
        "final_response": final_response,
        "validation_passed": validation_passed,
        "processing_time_ms": processing_time_ms,
    })
    conn.close()
    return qid


def get_query_log(empresa_id: str, limit: int = 10) -> list[dict]:
    """Retorna las últimas trazas del orquestador."""
    conn = get_memory_db(empresa_id)
    rows = query(
        conn,
        "SELECT * FROM query_log ORDER BY created_at DESC LIMIT ?",
        (limit,),
    )
    conn.close()
    return rows


# ═══════════════════════════════════════════════════════════════════════════
# 4. BÚSQUEDA HÍBRIDA (30% FTS5 + 70% ChromaDB)
# ═══════════════════════════════════════════════════════════════════════════

def _normalize_fts_scores(results: list[dict]) -> list[tuple[str, float]]:
    """Normaliza scores BM25 de FTS5 a rango [0, 1]."""
    if not results:
        return []
    # BM25 retorna scores negativos (más negativo = más relevante)
    scores = [abs(r.get("rank", 0)) for r in results]
    max_score = max(scores) if scores else 1
    return [
        (str(r.get("rowid", i)), abs(r.get("rank", 0)) / max_score if max_score else 0)
        for i, r in enumerate(results)
    ]


def _normalize_vector_scores(results: dict) -> list[tuple[str, float]]:
    """Normaliza distancias ChromaDB a scores [0, 1] (1 = más relevante)."""
    if not results or not results.get("ids") or not results["ids"][0]:
        return []
    ids = results["ids"][0]
    distances = results["distances"][0]
    # Cosine distance: 0 = idéntico, 2 = opuesto. Convertir a score.
    return [(id_, 1 - dist / 2) for id_, dist in zip(ids, distances)]


def hybrid_search(
    empresa_id: str,
    query_text: str,
    domain: str = "internal",
    n_results: int = 5,
    fts_weight: float = 0.3,
    vector_weight: float = 0.7,
) -> list[dict]:
    """Búsqueda híbrida: combina FTS5 (BM25) + ChromaDB (semántica).

    Args:
        domain: "internal" busca en docs/internal_docs,
                "external" busca en regulations/external_research,
                "memory" busca en messages/conversation_context.
    """
    vs = VectorStore(empresa_id)

    # Mapeo de dominio a tabla FTS y collection ChromaDB
    domain_map = {
        "internal": ("fts_documents", "internal_docs", get_internal_db),
        "external": ("fts_regulations", "external_research", get_external_db),
        "memory":   ("fts_messages", "conversation_context", get_memory_db),
    }

    if domain not in domain_map:
        raise ValueError(f"Domain must be one of: {list(domain_map.keys())}")

    fts_table, collection, db_getter = domain_map[domain]

    # FTS5 search
    conn = db_getter(empresa_id)
    fts_results = fts_search(conn, fts_table, query_text, limit=n_results * 2)
    conn.close()
    fts_scored = _normalize_fts_scores(fts_results)

    # Vector search
    vector_results = vs.search(collection, query_text, n_results=n_results * 2)
    vector_scored = _normalize_vector_scores(vector_results)

    # Combinar scores
    combined: dict[str, float] = {}
    for id_, score in fts_scored:
        combined[f"fts_{id_}"] = score * fts_weight
    for id_, score in vector_scored:
        if id_ in combined:
            combined[id_] += score * vector_weight
        else:
            combined[id_] = score * vector_weight

    # Ordenar por score combinado
    ranked = sorted(combined.items(), key=lambda x: x[1], reverse=True)[:n_results]

    # Armar resultados con documentos de ChromaDB (tienen el texto)
    docs = vector_results.get("documents", [[]])[0] if vector_results else []
    metas = vector_results.get("metadatas", [[]])[0] if vector_results else []
    ids = vector_results.get("ids", [[]])[0] if vector_results else []

    doc_map = {id_: {"text": doc, "metadata": meta} for id_, doc, meta in zip(ids, docs, metas)}

    results = []
    for id_, score in ranked:
        entry = {"id": id_, "score": round(score, 4)}
        if id_ in doc_map:
            entry["text"] = doc_map[id_]["text"]
            entry["metadata"] = doc_map[id_]["metadata"]
        results.append(entry)

    return results


def semantic_search(
    empresa_id: str,
    query_text: str,
    collection: str,
    n_results: int = 5,
    where: dict | None = None,
) -> list[dict]:
    """Búsqueda puramente semántica (solo ChromaDB). Útil cuando no hay FTS."""
    vs = VectorStore(empresa_id)
    results = vs.search(collection, query_text, n_results=n_results, where=where)

    if not results or not results.get("ids") or not results["ids"][0]:
        return []

    output = []
    for id_, doc, meta, dist in zip(
        results["ids"][0],
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        output.append({
            "id": id_,
            "text": doc,
            "metadata": meta,
            "score": round(1 - dist / 2, 4),
        })
    return output


# ═══════════════════════════════════════════════════════════════════════════
# 5. ESCRITURA EXTERNA (solo Research y Economy agents)
# ═══════════════════════════════════════════════════════════════════════════

def write_credits(empresa_id: str, credits: list[dict]) -> int:
    """Agrega créditos a external.sqlite. Solo para agentes Research/Economy."""
    conn = get_external_db(empresa_id)
    count = insert_many(conn, "available_credits", credits)
    conn.close()

    # Actualizar embeddings en ChromaDB
    vs = VectorStore(empresa_id)
    docs, metas, ids = [], [], []
    for i, c in enumerate(credits):
        text = (
            f"Crédito: {c['credit_name']} de {c['bank_name']}. "
            f"Tipo: {c.get('credit_type', 'N/A')}. Tasa anual: {c.get('annual_rate', 0)*100:.0f}%. "
            f"Monto máximo: ${c.get('max_amount', 0):,.0f}. Plazo: {c.get('max_term_months', 0)} meses."
        )
        docs.append(text)
        metas.append({"type": "credit", "bank": c["bank_name"]})
        ids.append(f"credit_new_{datetime.now().strftime('%Y%m%d%H%M%S')}_{i}")
    vs.add_documents("external_research", docs, metas, ids)

    return count


def write_macro_indicators(empresa_id: str, indicators: list[dict]) -> int:
    """Agrega indicadores macro a external.sqlite. Solo para agentes Research/Economy."""
    conn = get_external_db(empresa_id)
    count = insert_many(conn, "macro_indicators", indicators)
    conn.close()
    return count


def write_regulations(empresa_id: str, regulations: list[dict]) -> int:
    """Agrega regulaciones a external.sqlite. Solo para agentes Research/Economy."""
    conn = get_external_db(empresa_id)
    count = insert_many(conn, "regulations", regulations)
    conn.close()

    # Actualizar embeddings
    vs = VectorStore(empresa_id)
    docs, metas, ids = [], [], []
    for i, r in enumerate(regulations):
        text = f"{r['title']}. {r.get('summary', '')}"
        docs.append(text)
        metas.append({"type": "regulation", "source": r.get("source", "unknown")})
        ids.append(f"reg_new_{datetime.now().strftime('%Y%m%d%H%M%S')}_{i}")
    vs.add_documents("external_research", docs, metas, ids)

    return count


def write_sector_signals(empresa_id: str, signals: list[dict]) -> int:
    """Agrega señales del sector a external.sqlite. Solo para agente Research."""
    conn = get_external_db(empresa_id)
    count = insert_many(conn, "sector_signals", signals)
    conn.close()
    return count


def write_credit_profile(empresa_id: str, profile: dict) -> int:
    """Actualiza el perfil crediticio BCRA. Solo para agente Economy."""
    conn = get_external_db(empresa_id)
    if "last_24_months" in profile and isinstance(profile["last_24_months"], list):
        profile["last_24_months"] = json.dumps(profile["last_24_months"])
    if "rejected_checks" in profile and isinstance(profile["rejected_checks"], list):
        profile["rejected_checks"] = json.dumps(profile["rejected_checks"])
    row_id = insert_row(conn, "credit_profile", profile)
    conn.close()
    return row_id


# ═══════════════════════════════════════════════════════════════════════════
# 6. EMBEDDINGS — Actualización de vectores desde Data Service
# ═══════════════════════════════════════════════════════════════════════════

def update_conversation_embeddings(
    empresa_id: str,
    summary_id: int,
    summary_text: str,
) -> None:
    """Agrega un nuevo summary al collection conversation_context."""
    vs = VectorStore(empresa_id)
    vs.add_documents(
        "conversation_context",
        documents=[summary_text],
        metadatas=[{"type": "summary", "summary_id": summary_id}],
        ids=[f"summary_{summary_id}"],
    )
