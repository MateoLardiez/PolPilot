"""
Research Skill — Obtiene datos en tiempo real de APIs públicas argentinas.

Fuentes:
  - DolarAPI.com     : tipos de cambio (oficial, blue, MEP, CCL, cripto, tarjeta)
  - BCRA Monetarias  : tasas, inflación, reservas, UVA, CER
  - BCRA Transparencia: préstamos bancarios PyME vigentes

No hace llamadas LLM. Función asincrónica (HTTP calls a APIs externas).
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Asegurar que backend/ esté en sys.path para importar data.*
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

try:
    from data.external_fetcher import (
        fetch_dollar_snapshot,
        fetch_key_macro_variables,
        fetch_pyme_eligible_loans,
    )
    _FETCHER_AVAILABLE = True
except ImportError as _e:
    _FETCHER_AVAILABLE = False
    logger.warning("research_skill: external_fetcher no disponible: %s", _e)


# Keywords que disparan la búsqueda de préstamos PyME
_LOAN_KEYWORDS = {
    "crédito", "credito", "préstamo", "prestamo",
    "financiamiento", "banco", "tasa", "línea", "linea",
}


@dataclass
class ResearchData:
    """Datos en tiempo real obtenidos de APIs externas."""
    dollar_rates: Optional[dict] = None      # dict tipo → {compra, venta}
    macro_variables: Optional[dict] = None  # dict nombre → {value, date}
    pyme_loans: Optional[list] = None        # lista de créditos BCRA
    sub_questions: list[str] = field(default_factory=list)
    sources_fetched: int = 0
    fetcher_available: bool = True

    @property
    def is_available(self) -> bool:
        return self.fetcher_available and self.sources_fetched > 0

    def as_prompt_block(self) -> str:
        """Formatea los datos como bloque para inyectar en el prompt de síntesis."""
        if not self.fetcher_available:
            return "[INVESTIGACIÓN] APIs externas no disponibles en este momento."
        if self.sources_fetched == 0:
            return "[INVESTIGACIÓN] No se obtuvieron datos de APIs externas."

        lines = ["[DATOS EN TIEMPO REAL]"]

        if self.dollar_rates:
            lines.append("\nTIPOS DE CAMBIO (ARS/USD):")
            for tipo, data in self.dollar_rates.items():
                venta = data.get("venta")
                compra = data.get("compra")
                if venta is None:
                    continue
                label = tipo.replace("_", " ").title()
                lines.append(f"  {label}: compra ${compra:,.0f} / venta ${venta:,.0f}")

        if self.macro_variables:
            _NAMES = {
                "inflacion_mensual": "Inflación mensual",
                "inflacion_interanual": "Inflación interanual",
                "tasa_badlar": "Tasa BADLAR",
                "tasa_tm20": "Tasa TM20",
                "tasa_adelantos_cta_cte": "Tasa adelantos cta cte",
                "tasa_prestamos_personales": "Tasa préstamos personales",
                "usd_minorista": "USD minorista (BCRA)",
                "usd_mayorista": "USD mayorista (BCRA)",
                "reservas_internacionales": "Reservas internacionales",
                "base_monetaria": "Base monetaria",
                "uva": "UVA",
                "cer": "CER",
            }
            lines.append("\nINDICADORES BCRA:")
            for name, info in self.macro_variables.items():
                val = info.get("value")
                fecha = info.get("date", "")
                if val is None:
                    continue
                label = _NAMES.get(name, name.replace("_", " ").title())
                if "tasa" in name or "inflacion" in name:
                    display = f"{val:.2f}%" if val <= 1 else f"{val:.2f}% (TEA)"
                else:
                    display = str(val)
                lines.append(f"  {label}: {display} ({fecha})")

        if self.pyme_loans:
            lines.append(f"\nPRÉSTAMOS PyME VIGENTES (top {min(len(self.pyme_loans), 5)}):")
            for loan in self.pyme_loans[:5]:
                bank = loan.get("bank_name", "?")
                name = loan.get("credit_name", "?")
                rate = (loan.get("annual_rate") or 0) * 100
                monto = loan.get("max_amount")
                plazo = loan.get("max_term_months", "?")
                monto_str = f"${monto:,.0f}" if monto else "N/A"
                lines.append(f"  [{bank}] {name} — {rate:.0f}% TEA | {monto_str} | {plazo} meses")

        if self.sub_questions:
            lines.append("\n[SUB-PREGUNTAS A RESPONDER CON ESTOS DATOS]")
            lines.extend(f"  - {q}" for q in self.sub_questions)

        return "\n".join(lines)


async def execute(
    original_query: str,
    sub_questions: Optional[list[str]] = None,
) -> ResearchData:
    """
    Obtiene datos en tiempo real desde las APIs externas.

    Args:
        original_query: Query original para detectar si se necesitan préstamos.
        sub_questions: Sub-preguntas específicas del topic_skill.

    Returns:
        ResearchData con todos los datos disponibles.
    """
    if not _FETCHER_AVAILABLE:
        return ResearchData(fetcher_available=False, sub_questions=sub_questions or [])

    sources = 0
    dollar_rates = None
    macro_variables = None
    pyme_loans = None

    # Tipos de cambio — siempre
    try:
        dollar_rates = fetch_dollar_snapshot()
        if dollar_rates:
            sources += 1
    except Exception as e:
        logger.warning("research_skill: error fetching dollar rates: %s", e)

    # Macro BCRA — siempre
    try:
        macro_variables = fetch_key_macro_variables()
        if macro_variables:
            sources += 1
    except Exception as e:
        logger.warning("research_skill: error fetching BCRA variables: %s", e)

    # Préstamos PyME — solo si la query lo pide
    query_lower = (original_query + " ".join(sub_questions or [])).lower()
    if any(kw in query_lower for kw in _LOAN_KEYWORDS):
        try:
            pyme_loans = fetch_pyme_eligible_loans()
            if pyme_loans:
                sources += 1
        except Exception as e:
            logger.warning("research_skill: error fetching BCRA loans: %s", e)

    return ResearchData(
        dollar_rates=dollar_rates,
        macro_variables=macro_variables,
        pyme_loans=pyme_loans,
        sub_questions=sub_questions or [],
        sources_fetched=sources,
        fetcher_available=True,
    )
