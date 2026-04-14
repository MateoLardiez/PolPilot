"""
PolPilot — Script de carga inicial (seed).

Lee los 7+ archivos JSON de seed/ y llena:
  - internal.sqlite  (company_profile, financials, indicators, clients, suppliers, products, employees)
  - external.sqlite  (available_credits, macro_indicators, regulations, credit_profile)
  - memory.sqlite    (schemas vacíos, listos para uso)
  - vectors/         (ChromaDB collections con embeddings de los datos cargados)

Uso:
    python -m polpilot.backend.seed.seed_database [--empresa-id empresa_demo]
"""

import json
import sys
from pathlib import Path

# Agregar el root del proyecto al path para imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from polpilot.backend.data.db import (
    init_databases,
    get_internal_db,
    get_external_db,
    insert_row,
    insert_many,
)
from polpilot.backend.data.vector_store import VectorStore

SEED_DIR = Path(__file__).resolve().parent
DEFAULT_EMPRESA_ID = "empresa_demo"


def load_json(filename: str) -> dict | list:
    with open(SEED_DIR / filename, "r", encoding="utf-8") as f:
        return json.load(f)


def seed_internal(empresa_id: str) -> None:
    """Llena internal.sqlite con datos del negocio."""
    conn = get_internal_db(empresa_id)

    # Company profile
    profile = load_json("seed_company_profile.json")
    insert_row(conn, "company_profile", profile)
    print(f"  ✓ company_profile: 1 fila")

    # Financials monthly
    financials = load_json("seed_financials.json")
    count = insert_many(conn, "financials_monthly", financials)
    print(f"  ✓ financials_monthly: {count} filas")

    # Financial indicators
    indicators = load_json("seed_indicators.json")
    count = insert_many(conn, "financial_indicators", indicators)
    print(f"  ✓ financial_indicators: {count} filas")

    # Clients
    clients = load_json("seed_clients.json")
    count = insert_many(conn, "clients", clients)
    print(f"  ✓ clients: {count} filas")

    # Suppliers
    suppliers = load_json("seed_suppliers.json")
    count = insert_many(conn, "suppliers", suppliers)
    print(f"  ✓ suppliers: {count} filas")

    # Products
    products = load_json("seed_products.json")
    count = insert_many(conn, "products", products)
    print(f"  ✓ products: {count} filas")

    # Employees
    employees = load_json("seed_employees.json")
    count = insert_many(conn, "employees", employees)
    print(f"  ✓ employees: {count} filas")

    conn.close()


def seed_external(empresa_id: str) -> None:
    """Llena external.sqlite con créditos, macro y regulaciones."""
    conn = get_external_db(empresa_id)

    # Available credits
    credits = load_json("seed_credits.json")
    count = insert_many(conn, "available_credits", credits)
    print(f"  ✓ available_credits: {count} filas")

    # Macro indicators (datos de abril 2026)
    macro_data = [
        {"indicator_name": "inflacion_mensual", "value": 0.028, "date": "2026-03", "source": "bcra_api"},
        {"indicator_name": "inflacion_interanual", "value": 0.42, "date": "2026-03", "source": "bcra_api"},
        {"indicator_name": "usd_oficial", "value": 1200.0, "date": "2026-04-14", "source": "bcra_api"},
        {"indicator_name": "usd_blue", "value": 1350.0, "date": "2026-04-14", "source": "curated"},
        {"indicator_name": "tasa_badlar", "value": 0.32, "date": "2026-04-14", "source": "bcra_api"},
        {"indicator_name": "tasa_plazo_fijo_30d", "value": 0.30, "date": "2026-04-14", "source": "bcra_api"},
        {"indicator_name": "riesgo_pais", "value": 780.0, "date": "2026-04-14", "source": "bcra_api"},
        {"indicator_name": "pbi_variacion_anual", "value": 0.045, "date": "2026-Q1", "source": "bcra_api"},
        {"indicator_name": "desempleo", "value": 0.068, "date": "2026-Q1", "source": "bcra_api"},
    ]
    count = insert_many(conn, "macro_indicators", macro_data)
    print(f"  ✓ macro_indicators: {count} filas")

    # Regulations
    regulations = [
        {
            "title": "Resolución AFIP 5432/2025: Régimen simplificado de importación PyME",
            "summary": "Nuevo régimen simplificado de importación para PyMEs categoría Tramo 1 y 2. Elimina SIRA, simplifica trámites.",
            "full_text": None,
            "source": "boletin_oficial",
            "source_url": "https://www.boletinoficial.gob.ar",
            "relevance_score": 0.95,
            "status": "confirmed",
            "probability": 1.0,
            "published_date": "2025-11-15",
        },
        {
            "title": "Decreto 124/2026: Bonificación tasa créditos PyME importación",
            "summary": "Bonificación de 5 puntos en tasa de interés para créditos productivos PyME con destino importación de insumos.",
            "full_text": None,
            "source": "boletin_oficial",
            "source_url": "https://www.boletinoficial.gob.ar",
            "relevance_score": 0.98,
            "status": "confirmed",
            "probability": 1.0,
            "published_date": "2026-02-01",
        },
        {
            "title": "Comunicación BCRA A-7890: Líneas preferenciales sin reciprocidad",
            "summary": "Las PyMEs con certificado vigente pueden acceder a líneas de crédito preferenciales sin requisito de reciprocidad bancaria.",
            "full_text": None,
            "source": "bcra",
            "source_url": "https://www.bcra.gob.ar",
            "relevance_score": 0.85,
            "status": "confirmed",
            "probability": 1.0,
            "published_date": "2026-03-10",
        },
    ]
    count = insert_many(conn, "regulations", regulations)
    print(f"  ✓ regulations: {count} filas")

    # Credit profile (BCRA Central de Deudores para Calatayud)
    credit_profile = {
        "cuit": "30-71584923-4",
        "situation": 1,
        "total_debt": 0,
        "days_overdue": 0,
        "last_24_months": json.dumps([1]*24),
        "rejected_checks": json.dumps([]),
    }
    insert_row(conn, "credit_profile", credit_profile)
    print(f"  ✓ credit_profile: 1 fila")

    # Sector signals
    signals = [
        {
            "signal_type": "demand_shift",
            "description": "Aumento de demanda de repuestos importados por desregulación de importaciones desde enero 2025.",
            "sector": "Repuestos automotores",
            "impact_level": "high",
            "data_points": 5,
            "source": "curated",
        },
        {
            "signal_type": "price_change",
            "description": "Baja de precios en discos y pastillas de freno importados (-15% promedio) por mayor competencia.",
            "sector": "Repuestos automotores",
            "impact_level": "medium",
            "data_points": 3,
            "source": "curated",
        },
    ]
    count = insert_many(conn, "sector_signals", signals)
    print(f"  ✓ sector_signals: {count} filas")

    # Collective intelligence
    ci = [
        {"metric_name": "avg_margin_sector", "sector": "Repuestos automotores", "region": "Santa Fe", "value": 0.30, "sample_size": 12, "period": "2026-Q1"},
        {"metric_name": "avg_payment_days", "sector": "Repuestos automotores", "region": "Santa Fe", "value": 35.0, "sample_size": 12, "period": "2026-Q1"},
    ]
    count = insert_many(conn, "collective_intelligence", ci)
    print(f"  ✓ collective_intelligence: {count} filas")

    conn.close()


def seed_vectors(empresa_id: str) -> None:
    """Genera embeddings iniciales en ChromaDB."""
    vs = VectorStore(empresa_id)
    vs.init_collections()

    # Internal docs — embeddings del perfil y financials
    profile = load_json("seed_company_profile.json")
    profile_text = (
        f"Empresa: {profile['name']}. CUIT: {profile['cuit']}. "
        f"Sector: {profile['sector']} - {profile['sub_sector']}. "
        f"Ubicación: {profile['location']}, {profile['province']}. "
        f"Empleados: {profile['employees_count']}. Antigüedad: {profile['years_in_business']} años. "
        f"Facturación anual: ${profile['annual_revenue']:,.0f}. "
        f"{profile['description']}"
    )

    financials = load_json("seed_financials.json")
    fin_docs = []
    fin_ids = []
    fin_metas = []
    for f in financials:
        text = (
            f"Financiero {f['year']}-{f['month']:02d}: "
            f"Ingresos ${f['revenue']:,.0f}, Egresos ${f['expenses']:,.0f}, "
            f"Flujo neto ${f['net_cash_flow']:,.0f}, Saldo caja ${f['cash_balance']:,.0f}. "
            f"{f.get('notes', '')}"
        )
        fin_docs.append(text)
        fin_ids.append(f"fin_{f['year']}_{f['month']:02d}")
        fin_metas.append({"type": "financial", "year": f["year"], "month": f["month"]})

    vs.add_documents(
        "internal_docs",
        documents=[profile_text] + fin_docs,
        metadatas=[{"type": "profile"}] + fin_metas,
        ids=["profile_001"] + fin_ids,
    )
    print(f"  ✓ internal_docs: {1 + len(fin_docs)} embeddings")

    # External research — embeddings de créditos y regulaciones
    credits = load_json("seed_credits.json")
    credit_docs = []
    credit_ids = []
    credit_metas = []
    for i, c in enumerate(credits):
        text = (
            f"Crédito: {c['credit_name']} de {c['bank_name']}. "
            f"Tipo: {c['credit_type']}. Tasa anual: {c['annual_rate']*100:.0f}%. "
            f"Monto máximo: ${c['max_amount']:,.0f}. Plazo: {c['max_term_months']} meses. "
            f"Requisitos: {c['requirements']}"
        )
        credit_docs.append(text)
        credit_ids.append(f"credit_{i+1:03d}")
        credit_metas.append({"type": "credit", "bank": c["bank_name"]})

    vs.add_documents(
        "external_research",
        documents=credit_docs,
        metadatas=credit_metas,
        ids=credit_ids,
    )
    print(f"  ✓ external_research: {len(credit_docs)} embeddings")

    # Conversation context — vacío al inicio
    print(f"  ✓ conversation_context: 0 embeddings (vacío al inicio)")

    print(f"  Totales ChromaDB:")
    for name in ["internal_docs", "external_research", "conversation_context"]:
        print(f"    {name}: {vs.count(name)}")


def main(empresa_id: str = DEFAULT_EMPRESA_ID) -> None:
    print(f"=== PolPilot Seed Database ===")
    print(f"Empresa ID: {empresa_id}\n")

    print("1. Inicializando schemas SQLite...")
    init_databases(empresa_id)
    print("   ✓ Schemas creados\n")

    print("2. Cargando internal.sqlite...")
    seed_internal(empresa_id)
    print()

    print("3. Cargando external.sqlite...")
    seed_external(empresa_id)
    print()

    print("4. Generando embeddings en ChromaDB...")
    seed_vectors(empresa_id)
    print()

    print("=== Seed completado ===")


if __name__ == "__main__":
    eid = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_EMPRESA_ID
    main(eid)
