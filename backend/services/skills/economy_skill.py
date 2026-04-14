"""
Economy Skill — Prepara datos macroeconómicos y crediticios para la síntesis.

Responsabilidades:
  - Recibir el contexto externo ya leído por client_db_skill
  - Formatear datos de créditos, macro e indicadores BCRA
  - Extraer la lista de créditos disponibles

No hace llamadas LLM. Función sincrónica.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EconomyData:
    """Datos económicos externos preparados para la síntesis."""
    raw_context: str  # contexto completo de data_bridge
    sub_questions: list[str] = field(default_factory=list)
    credit_count: int = 0  # cantidad de créditos disponibles detectados
    has_live_macro: bool = False  # si el contexto tiene datos de API live

    @property
    def is_available(self) -> bool:
        return bool(self.raw_context.strip())

    def as_prompt_block(self) -> str:
        """Formatea los datos como bloque para inyectar en el prompt de síntesis."""
        if not self.is_available:
            return "[ECONOMÍA] Sin datos disponibles."
        parts = ["[CONTEXTO ECONÓMICO EXTERNO]", self.raw_context]
        if self.sub_questions:
            parts.append("\n[SUB-PREGUNTAS A RESPONDER CON ESTOS DATOS]")
            parts.extend(f"  - {q}" for q in self.sub_questions)
        return "\n".join(parts)


def _count_credits(context: str) -> int:
    """Cuenta la cantidad de créditos listados en el contexto."""
    matches = re.findall(r"\[\d+\]", context)
    return len(matches)


def execute(
    company_id: str,
    economia_context: str,
    sub_questions: Optional[list[str]] = None,
) -> EconomyData:
    """
    Prepara los datos económicos externos para la síntesis.

    Args:
        company_id: ID de la empresa (para trazabilidad).
        economia_context: Contexto ya leído por client_db_skill.
        sub_questions: Sub-preguntas clasificadas por topic_skill.

    Returns:
        EconomyData listo para incluir en el prompt de síntesis.
    """
    credit_count = _count_credits(economia_context)
    has_live = "api" in economia_context.lower() or "live" in economia_context.lower()

    return EconomyData(
        raw_context=economia_context,
        sub_questions=sub_questions or [],
        credit_count=credit_count,
        has_live_macro=has_live,
    )
