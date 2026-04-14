"""
[DEPRECADO — v1 multiagente]

El Agente Investigador original era el único sin LLM. En v2 fue migrado
directamente a services/skills/research_skill.py con la misma lógica de fetch.

Ver: services/skills/research_skill.py para la nueva implementación.
"""

"""
Agente Investigador — datos en tiempo real desde APIs públicas argentinas.

Fuentes:
  - DolarAPI.com      : tipos de cambio (oficial, blue, MEP, CCL, cripto, tarjeta, mayorista)
  - BCRA Monetarias   : tasas BADLAR, inflación, reservas, UVA, CER
  - BCRA Transparencia: catálogo de préstamos bancarios (personales, prendarios)

No llama a LLM — empaqueta datos estructurados directamente.
El sintetizador del orquestador se encarga de darle sentido en contexto.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from schemas import AgentAnswer, AgentQueryRequest, AgentQueryResponse, DataPoint

logger = logging.getLogger(__name__)

# Asegurar que backend/ esté en sys.path para importar data.*
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    from data.external_fetcher import (
        fetch_dollar_snapshot,
        fetch_key_macro_variables,
        fetch_pyme_eligible_loans,
    )
    _FETCHER_AVAILABLE = True
except ImportError as e:
    _FETCHER_AVAILABLE = False
    logger.warning("external_fetcher no disponible: %s", e)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _safe_val(v) -> str:
    """Convierte cualquier valor a string limpio para DataPoint."""
    if v is None:
        return "N/A"
    if isinstance(v, float):
        return f"{v:,.2f}" if v > 1 else f"{v:.4f}"
    return str(v)


def _fetch_dollar_answer() -> AgentAnswer | None:
    try:
        rates = fetch_dollar_snapshot()
        if not rates:
            return None

        lines = []
        data_points = []
        for tipo, data in rates.items():
            venta = data.get("venta")
            compra = data.get("compra")
            if venta is None:
                continue
            label = tipo.replace("_", " ").title()
            lines.append(f"  {label}: compra ${compra:,.0f} / venta ${venta:,.0f}")
            data_points.append(DataPoint(
                label=f"USD {label} (venta)",
                value=f"ARS {venta:,.0f}",
                source="dolarapi.com",
            ))

        if not lines:
            return None

        return AgentAnswer(
            question="Tipos de cambio en tiempo real",
            answer="Cotizaciones actuales (ARS/USD):\n" + "\n".join(lines),
            confidence=0.97,
            data_points=data_points,
        )
    except Exception as e:
        logger.warning("investigador: error fetching dollar rates: %s", e)
        return None


def _fetch_macro_answer() -> AgentAnswer | None:
    try:
        variables = fetch_key_macro_variables()
        if not variables:
            return None

        DISPLAY_NAMES = {
            "inflacion_mensual": "Inflación mensual",
            "inflacion_interanual": "Inflación interanual",
            "tasa_badlar": "Tasa BADLAR",
            "tasa_tm20": "Tasa TM20",
            "tasa_adelantos_cta_cte": "Tasa adelantos cta. cte.",
            "tasa_prestamos_personales": "Tasa préstamos personales",
            "usd_minorista": "USD minorista (BCRA)",
            "usd_mayorista": "USD mayorista (BCRA)",
            "reservas_internacionales": "Reservas internacionales",
            "base_monetaria": "Base monetaria",
            "uva": "UVA",
            "cer": "CER",
        }

        lines = []
        data_points = []
        for name, info in variables.items():
            val = info.get("value")
            fecha = info.get("date", "")
            if val is None:
                continue
            label = DISPLAY_NAMES.get(name, name.replace("_", " ").title())
            # Tasas: si el valor viene en porcentaje (> 1) o decimal
            if "tasa" in name or "inflacion" in name:
                display = f"{val:.2f}%" if val <= 1 else f"{val:.2f}% (TEA)"
            else:
                display = _safe_val(val)
            lines.append(f"  {label}: {display} ({fecha})")
            data_points.append(DataPoint(label=label, value=display, source="bcra_api"))

        if not lines:
            return None

        return AgentAnswer(
            question="Variables macro BCRA en tiempo real",
            answer="Indicadores BCRA actualizados:\n" + "\n".join(lines),
            confidence=0.92,
            data_points=data_points,
        )
    except Exception as e:
        logger.warning("investigador: error fetching BCRA variables: %s", e)
        return None


def _fetch_pyme_loans_answer() -> AgentAnswer | None:
    try:
        loans = fetch_pyme_eligible_loans()
        if not loans:
            return None

        lines = []
        data_points = []
        for loan in loans[:5]:  # top 5 para no saturar el contexto
            bank = loan.get("bank_name", "?")
            name = loan.get("credit_name", "?")
            rate = loan.get("annual_rate", 0) * 100
            monto = loan.get("max_amount")
            plazo = loan.get("max_term_months", "?")
            monto_str = f"${monto:,.0f}" if monto else "N/A"
            lines.append(f"  [{bank}] {name} — {rate:.0f}% TEA | {monto_str} | {plazo} meses")
            data_points.append(DataPoint(
                label=f"{bank}: {name}",
                value=f"{rate:.0f}% TEA",
                source="bcra_transparencia",
            ))

        if not lines:
            return None

        return AgentAnswer(
            question="Préstamos PyME vigentes en el sistema bancario",
            answer=f"Top {len(lines)} líneas PyME del catálogo BCRA Transparencia:\n" + "\n".join(lines),
            confidence=0.88,
            data_points=data_points,
        )
    except Exception as e:
        logger.warning("investigador: error fetching BCRA loans: %s", e)
        return None


# ── Agente principal ───────────────────────────────────────────────────────────

async def query_investigador(request: AgentQueryRequest) -> AgentQueryResponse:
    """
    Agente Investigador — consulta APIs públicas argentinas en tiempo real.

    Responde preguntas sobre datos frescos de mercado: tipos de cambio,
    tasas BCRA, inflación, préstamos vigentes. Sin LLM — datos directos.
    """
    if not _FETCHER_AVAILABLE:
        return AgentQueryResponse(
            thread_id=request.thread_id,
            topic="investigacion",
            answers=[AgentAnswer(
                question="Datos en tiempo real",
                answer="El módulo de datos externos no está disponible en este momento.",
                confidence=0.0,
            )],
            summary="Investigador no disponible — módulo external_fetcher no cargado.",
        )

    answers: list[AgentAnswer] = []

    # Siempre busca: tipos de cambio + macro
    dollar = _fetch_dollar_answer()
    if dollar:
        answers.append(dollar)

    macro = _fetch_macro_answer()
    if macro:
        answers.append(macro)

    # Solo busca préstamos si la consulta menciona crédito/financiamiento
    query_lower = (request.original_query + " ".join(request.questions)).lower()
    if any(kw in query_lower for kw in ("crédito", "credito", "préstamo", "prestamo",
                                         "financiamiento", "banco", "tasa", "línea")):
        loans = _fetch_pyme_loans_answer()
        if loans:
            answers.append(loans)

    if not answers:
        answers.append(AgentAnswer(
            question=request.questions[0] if request.questions else "Datos de mercado",
            answer="No se pudieron obtener datos en tiempo real (APIs no respondieron).",
            confidence=0.1,
        ))

    sources_fetched = len([a for a in answers if a.confidence > 0.5])
    return AgentQueryResponse(
        thread_id=request.thread_id,
        topic="investigacion",
        answers=answers,
        summary=(
            f"Datos en tiempo real obtenidos: {sources_fetched} fuentes. "
            f"Dólar oficial/blue/MEP, indicadores BCRA, "
            + ("préstamos PyME." if len(answers) > 2 else "indicadores macro.")
        ),
    )
