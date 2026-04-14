"""
Finance Skill — Prepara datos financieros internos para la síntesis.

Responsabilidades:
  - Recibir el contexto de DB ya leído por client_db_skill
  - Formatear y estructurar los datos para incluirlos en el prompt de síntesis
  - Extraer métricas clave (caja, flujo, health score)

No hace llamadas LLM. Función sincrónica.
Las queries específicas se responden en la síntesis de super_agent.py.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FinanceData:
    """Datos financieros preparados para la síntesis."""
    raw_context: str  # contexto completo de data_bridge
    sub_questions: list[str] = field(default_factory=list)
    key_metrics: dict[str, str] = field(default_factory=dict)  # metric_name → value_string

    @property
    def is_available(self) -> bool:
        return bool(self.raw_context.strip())

    def as_prompt_block(self) -> str:
        """Formatea los datos como bloque para inyectar en el prompt de síntesis."""
        if not self.is_available:
            return "[FINANZAS] Sin datos disponibles."
        parts = ["[DATOS FINANCIEROS INTERNOS]", self.raw_context]
        if self.sub_questions:
            parts.append("\n[SUB-PREGUNTAS A RESPONDER CON ESTOS DATOS]")
            parts.extend(f"  - {q}" for q in self.sub_questions)
        return "\n".join(parts)


def _extract_key_metrics(context: str) -> dict[str, str]:
    """
    Extrae métricas clave del contexto de texto para exponer en metadata.
    Parsing heurístico, no crítico para el flujo.
    """
    metrics = {}
    patterns = {
        "saldo_caja": r"Saldo (?:actual|caja):\s*\$([\d,\.]+)",
        "flujo_neto": r"Flujo neto(?: mes)?:\s*\$([\d,\.]+)",
        "health_score": r"Health Score:\s*(\d+(?:\.\d+)?)",
        "liquidez_corriente": r"Liquidez corriente:\s*([\d,\.]+)",
        "ingresos_ultimo_mes": r"Ingresos:\s*\$([\d,\.]+)",
    }
    for key, pattern in patterns.items():
        m = re.search(pattern, context, re.IGNORECASE)
        if m:
            metrics[key] = m.group(1).replace(",", "")
    return metrics


def execute(
    company_id: str,
    finanzas_context: str,
    sub_questions: Optional[list[str]] = None,
) -> FinanceData:
    """
    Prepara los datos financieros internos para la síntesis.

    Args:
        company_id: ID de la empresa (para trazabilidad).
        finanzas_context: Contexto ya leído por client_db_skill.
        sub_questions: Sub-preguntas clasificadas por topic_skill.

    Returns:
        FinanceData listo para incluir en el prompt de síntesis.
    """
    key_metrics = _extract_key_metrics(finanzas_context)

    return FinanceData(
        raw_context=finanzas_context,
        sub_questions=sub_questions or [],
        key_metrics=key_metrics,
    )
