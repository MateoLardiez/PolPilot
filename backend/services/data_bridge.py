"""
data_bridge.py — Puente entre orchestrator-api y polpilot.backend.data.

Agrega el root del proyecto al sys.path para que los imports de
polpilot.backend.data funcionen desde apps/orchestrator-api/.

Cada función pública retorna un string de contexto listo para inyectar
en el system prompt del agente correspondiente.
Si la DB no está inicializada, cae en mock_data como fallback.
"""

from __future__ import annotations

import sys
import json
from pathlib import Path

# ── Setup path: agrega backend/ al sys.path para imports de data.* ───────────
BACKEND_DIR = Path(__file__).resolve().parent.parent  # backend/services/../ = backend/
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# ── Imports del backend de datos ─────────────────────────────────────────────
try:
    from data.data_service import (
        get_company_profile,
        get_financials,
        get_latest_indicators,
        get_all_indicators,
        get_clients,
        get_delinquent_clients,
        get_suppliers,
        get_products,
        get_employees,
        get_cash_position,
        get_available_credits,
        get_credits_for_company,
        get_macro_indicators,
        get_macro_snapshot,
        get_regulations,
        get_sector_signals,
        get_credit_profile,
        get_sector_benchmark,
        log_query,
        save_message,
        start_conversation,
    )
    from data.db import init_databases
    _POLPILOT_AVAILABLE = True
except ImportError as e:
    _POLPILOT_AVAILABLE = False
    _IMPORT_ERROR = str(e)


def _db_has_data(empresa_id: str) -> bool:
    """Verifica si la DB de la empresa tiene datos cargados."""
    if not _POLPILOT_AVAILABLE:
        return False
    try:
        profile = get_company_profile(empresa_id)
        return profile is not None
    except Exception:
        return False


# ── Finanzas context ──────────────────────────────────────────────────────────

def get_finanzas_context(empresa_id: str) -> str:
    """
    Construye el contexto financiero interno para el Agente de Finanzas.
    Fuente: internal.sqlite (SQLite real).
    Fallback: mock_data.py si la DB no está inicializada.
    """
    if not _db_has_data(empresa_id):
        from services.mock_data import build_finanzas_context
        return build_finanzas_context(empresa_id)

    try:
        profile    = get_company_profile(empresa_id) or {}
        financials = get_financials(empresa_id, last_n_months=6)
        indicators = get_latest_indicators(empresa_id) or {}
        all_inds   = get_all_indicators(empresa_id)
        cash       = get_cash_position(empresa_id)
        clients    = get_clients(empresa_id)
        delinquent = get_delinquent_clients(empresa_id, min_days=60)
        suppliers  = get_suppliers(empresa_id)
        products   = get_products(empresa_id)
        employees  = get_employees(empresa_id)
        benchmark  = get_sector_benchmark(empresa_id)

        # Historial financiero
        hist_lines = []
        for f in financials:
            hist_lines.append(
                f"  {f['year']}-{f['month']:02d}: "
                f"Ingresos ${f['revenue']:,.0f} | "
                f"Egresos ${f['expenses']:,.0f} | "
                f"Flujo neto ${f['net_cash_flow']:,.0f} | "
                f"Saldo caja ${f['cash_balance']:,.0f}"
                + (f" — {f['notes']}" if f.get("notes") else "")
            )
        hist_text = "\n".join(hist_lines) or "Sin datos"

        # Clientes morosos
        mor_lines = [
            f"  - {c['name']}: ${c['outstanding_balance']:,.0f} "
            f"({c['avg_payment_days']} días atraso, riesgo: {c.get('risk_level','?')})"
            for c in delinquent
        ]
        mor_text = "\n".join(mor_lines) or "  Sin morosos registrados"

        # Clientes principales
        cli_lines = [
            f"  - {c['name']} ({c.get('client_type','?')}): ${c.get('annual_revenue',0):,.0f}/año"
            for c in clients[:5]
        ]

        # Proveedores
        sup_lines = [
            f"  - {s['name']}: plazo {s.get('payment_terms_days','?')}d, "
            f"confiabilidad {(s.get('reliability_pct') or 0)*100:.0f}%"
            for s in suppliers[:5]
        ]

        # Productos top
        prod_lines = [
            f"  - {p['name']} ({p.get('category','?')}): "
            f"${p.get('monthly_revenue',0):,.0f}/mes, margen {(p.get('margin_pct') or 0)*100:.0f}%"
            for p in products[:5]
        ]

        # Benchmark sectorial
        bench_lines = []
        if benchmark.get("gross_margin"):
            bm = benchmark["gross_margin"]
            bench_lines.append(
                f"  Margen bruto: empresa {bm['company']*100:.1f}% vs sector {bm['sector_avg']*100:.1f}% "
                f"({'por encima' if bm['status'] == 'above' else 'por debajo'})"
            )
        if benchmark.get("payment_days"):
            bm = benchmark["payment_days"]
            bench_lines.append(
                f"  Días cobro: empresa {bm['company']:.0f} vs sector {bm['sector_avg']:.0f} "
                f"({'mejor' if bm['status'] == 'better' else 'peor'})"
            )

        # Indicadores all periods
        ind_lines = []
        for ind in all_inds[:3]:
            ind_lines.append(
                f"  [{ind['period']}] Health Score: {ind.get('health_score','?')} | "
                f"Liquidez: {ind.get('current_ratio','?')} | "
                f"Margen bruto: {(ind.get('gross_margin') or 0)*100:.1f}%"
            )

        latest_fin = financials[-1] if financials else {}

        context = f"""
=== DATOS INTERNOS DE LA EMPRESA (SQLite — internal.sqlite) ===

PERFIL:
- Nombre: {profile.get('name', 'N/A')}
- CUIT: {profile.get('cuit', 'N/A')}
- Sector: {profile.get('sector', 'N/A')} / {profile.get('sub_sector', 'N/A')}
- Localidad: {profile.get('location', 'N/A')}, {profile.get('province', 'N/A')}
- Empleados: {profile.get('employees_count', 'N/A')}
- Antigüedad: {profile.get('years_in_business', 'N/A')} años
- Facturación anual: ${profile.get('annual_revenue', 0):,.0f}
- {profile.get('description', '')}

ÚLTIMO MES ({latest_fin.get('year','?')}-{latest_fin.get('month','?'):02d} si existe):
- Ingresos: ${latest_fin.get('revenue', 0):,.0f}
- Egresos: ${latest_fin.get('expenses', 0):,.0f}
- Flujo neto: ${latest_fin.get('net_cash_flow', 0):,.0f}
- Saldo caja: ${latest_fin.get('cash_balance', 0):,.0f}
- Cuentas por cobrar: ${latest_fin.get('accounts_receivable', 0):,.0f}
- Cuentas por pagar: ${latest_fin.get('accounts_payable', 0):,.0f}
- Valor stock: ${latest_fin.get('inventory_value', 0):,.0f}
- Nota: {latest_fin.get('notes', 'Sin nota')}

POSICIÓN DE CAJA (resumen):
- Saldo actual: ${cash.get('cash_balance', 0):,.0f}
- Flujo neto mes: ${cash.get('net_cash_flow', 0):,.0f}
- Cuentas por cobrar: ${cash.get('accounts_receivable', 0):,.0f}
- Cuentas por pagar: ${cash.get('accounts_payable', 0):,.0f}
- Liquidez corriente: {cash.get('current_ratio', 'N/A')}
- Health Score: {cash.get('health_score', 'N/A')}/100
- Total morosos: ${cash.get('total_overdue', 0):,.0f} ({cash.get('delinquent_count', 0)} clientes)

INDICADORES FINANCIEROS (períodos):
{chr(10).join(ind_lines) or '  Sin indicadores'}

HISTORIAL FINANCIERO 6 MESES:
{hist_text}

CLIENTES MOROSOS (+60 días):
{mor_text}

CLIENTES PRINCIPALES:
{chr(10).join(cli_lines) or '  Sin clientes registrados'}

PROVEEDORES:
{chr(10).join(sup_lines) or '  Sin proveedores registrados'}

PRODUCTOS TOP:
{chr(10).join(prod_lines) or '  Sin productos registrados'}

BENCHMARK SECTORIAL:
{chr(10).join(bench_lines) or '  Sin benchmarks disponibles'}
""".strip()

        return context

    except Exception as exc:
        from services.mock_data import build_finanzas_context
        return build_finanzas_context(empresa_id)


# ── Economía context ──────────────────────────────────────────────────────────

def get_economia_context(empresa_id: str) -> str:
    """
    Construye el contexto macroeconómico y crediticio para el Agente de Economía.
    Fuente: external.sqlite.
    Fallback: mock_data.py si la DB no está inicializada.
    """
    if not _db_has_data(empresa_id):
        from services.mock_data import build_economia_context
        return build_economia_context()

    try:
        macro     = get_macro_snapshot(empresa_id)
        credits   = get_credits_for_company(empresa_id)
        regs      = get_regulations(empresa_id)
        signals   = get_sector_signals(empresa_id)
        cr_profile = get_credit_profile(empresa_id)

        # Macro indicators
        macro_lines = [
            f"- Inflación mensual: {macro.get('inflacion_mensual', 0)*100:.1f}%",
            f"- Inflación interanual: {macro.get('inflacion_interanual', 0)*100:.0f}%",
            f"- USD oficial: ARS {macro.get('usd_oficial', 'N/A')}",
            f"- USD blue: ARS {macro.get('usd_blue', 'N/A')}",
            f"- Tasa BADLAR: {macro.get('tasa_badlar', 0)*100:.0f}% anual",
            f"- Tasa plazo fijo 30d: {macro.get('tasa_plazo_fijo_30d', 0)*100:.0f}% anual",
            f"- Riesgo país: {macro.get('riesgo_pais', 'N/A')} bps",
            f"- PBI variación anual: +{macro.get('pbi_variacion_anual', 0)*100:.1f}%",
            f"- Desempleo: {macro.get('desempleo', 0)*100:.1f}%",
        ]

        # Créditos con elegibilidad
        credit_lines = []
        for i, c in enumerate(credits, 1):
            req_list = c.get("requirements", "[]")
            if isinstance(req_list, str):
                try:
                    req_list = json.loads(req_list)
                except Exception:
                    req_list = [req_list]
            req_str = ", ".join(req_list[:3])
            ok = c.get("qualification_reasons_ok", [])
            fail = c.get("qualification_reasons_fail", [])
            elegible = "✓ APLICA" if c.get("matches_profile") else "✗ No aplica"
            monto = f"${c.get('max_amount',0):,.0f}" if c.get("max_amount") else "N/A"
            credit_lines.append(
                f"  [{i}] {c['credit_name']} — {c['bank_name']}\n"
                f"      Tasa: {c.get('annual_rate',0)*100:.0f}% anual | Plazo: {c.get('max_term_months','?')} meses | Monto máx: {monto}\n"
                f"      Destino: {c.get('credit_type','?')} | Elegibilidad: {elegible}\n"
                f"      Requisitos: {req_str}\n"
                f"      A favor: {'; '.join(ok[:2]) or 'N/A'} | En contra: {'; '.join(fail[:2]) or 'ninguno'}"
            )

        # Regulaciones
        reg_lines = [
            f"  - [{r.get('source','?').upper()}] {r['title']}: {r.get('summary','')}"
            for r in regs[:4]
        ]

        # Señales del sector
        sig_lines = [
            f"  - [{s.get('impact_level','?').upper()}] {s.get('description','')}"
            for s in signals[:3]
        ]

        # Perfil crediticio BCRA
        cr_text = "No disponible"
        if cr_profile:
            situation = cr_profile.get("situation", "?")
            total_debt = cr_profile.get("total_debt", 0)
            days_overdue = cr_profile.get("days_overdue", 0)
            cr_text = (
                f"Situación BCRA: {situation}/5 | "
                f"Deuda total: ${total_debt:,.0f} | "
                f"Días mora: {days_overdue}"
            )

        context = f"""
=== CONTEXTO ECONÓMICO EXTERNO (SQLite — external.sqlite) ===

INDICADORES MACRO — ARGENTINA ABRIL 2026:
{chr(10).join(macro_lines)}

CRÉDITOS PyME DISPONIBLES ({len(credits)} opciones):
{chr(10).join(credit_lines) or '  Sin créditos cargados'}

PERFIL CREDITICIO BCRA:
  {cr_text}

REGULACIONES VIGENTES:
{chr(10).join(reg_lines) or '  Sin regulaciones cargadas'}

SEÑALES DEL SECTOR:
{chr(10).join(sig_lines) or '  Sin señales disponibles'}
""".strip()

        return context

    except Exception as exc:
        from services.mock_data import build_economia_context
        return build_economia_context()


# ── DB management ─────────────────────────────────────────────────────────────

def ensure_initialized(empresa_id: str) -> dict:
    """
    Verifica si la DB existe y tiene datos. Si no, retorna info para que
    el endpoint /db/init pueda ejecutar el seed.
    """
    has_data = _db_has_data(empresa_id)
    return {
        "empresa_id": empresa_id,
        "polpilot_available": _POLPILOT_AVAILABLE,
        "has_data": has_data,
        "status": "ready" if has_data else "empty",
    }


def run_seed(empresa_id: str) -> dict:
    """
    Ejecuta el seed completo para la empresa dada.
    Retorna un dict con el resultado.
    """
    if not _POLPILOT_AVAILABLE:
        return {"success": False, "error": f"polpilot module not available: {_IMPORT_ERROR}"}

    try:
        from seed.seed_database import main as run_seed_main
        run_seed_main(empresa_id)
        return {"success": True, "empresa_id": empresa_id, "message": "Seed completado"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def log_orchestrator_query(
    empresa_id: str,
    original_query: str,
    expanded_questions: list[str],
    agents_called: list[str],
    agent_responses: dict,
    final_response: str,
    validation_passed: bool,
    processing_time_ms: int,
) -> None:
    """Persiste una traza de ejecución del orquestador en memory.sqlite."""
    if not _db_has_data(empresa_id):
        return
    try:
        log_query(
            empresa_id=empresa_id,
            original_query=original_query,
            expanded_questions=expanded_questions,
            agents_called=agents_called,
            agent_responses=agent_responses,
            final_response=final_response,
            validation_passed=validation_passed,
            processing_time_ms=processing_time_ms,
        )
    except Exception:
        pass  # logging no debe romper el flujo principal
