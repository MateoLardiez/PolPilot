"""
Client DB Skill — Lee datos del cliente y contexto de memoria conversacional.

Responsabilidades:
  - Obtener contexto financiero interno (internal.sqlite o mock)
  - Obtener contexto económico externo (external.sqlite o mock)
  - Leer memoria conversacional acumulada (shared_memory)
  - Detectar si la DB tiene datos reales o es mock

No hace llamadas LLM. Función sincrónica (shared_memory.build es sincrónico).
"""

from __future__ import annotations

from dataclasses import dataclass

from services.data_bridge import get_finanzas_context, get_economia_context
from services.shared_memory import shared_memory


@dataclass
class ClientDBResult:
    """Contexto completo del cliente leído desde la DB y la memoria."""
    company_id: str
    conversation_id: str
    finanzas_context: str
    economia_context: str
    memory_context: str
    has_real_data: bool  # False si cayó en mock_data

    @property
    def has_memory(self) -> bool:
        return bool(self.memory_context.strip())

    def summary_for_prompt(self) -> str:
        """Combina memoria + perfil de empresa en un bloque compacto para el LLM."""
        parts = []
        if self.memory_context:
            parts.append(f"[HISTORIAL CONVERSACIÓN]\n{self.memory_context}")
        # Extrae solo las primeras líneas del contexto financiero (perfil)
        fin_lines = self.finanzas_context.splitlines()
        profile_lines = fin_lines[:20]  # header + perfil básico
        parts.append("[PERFIL EMPRESA (resumen)]\n" + "\n".join(profile_lines))
        return "\n\n".join(parts)


def execute(company_id: str, conversation_id: str) -> ClientDBResult:
    """
    Lee el contexto completo del cliente desde la DB y la memoria conversacional.

    Args:
        company_id: ID de la empresa.
        conversation_id: ID de la conversación activa.

    Returns:
        ClientDBResult con todo el contexto disponible.
    """
    finanzas_ctx = get_finanzas_context(company_id)
    economia_ctx = get_economia_context(company_id)
    memory_ctx = shared_memory.build_conversation_context(company_id, conversation_id)

    # Heurística: si el contexto contiene "Mock" en el encabezado → mock data
    has_real = (
        bool(finanzas_ctx)
        and "mock" not in finanzas_ctx[:60].lower()
        and "mock" not in finanzas_ctx[:60].lower()
    )

    return ClientDBResult(
        company_id=company_id,
        conversation_id=conversation_id,
        finanzas_context=finanzas_ctx,
        economia_context=economia_ctx,
        memory_context=memory_ctx,
        has_real_data=has_real,
    )
