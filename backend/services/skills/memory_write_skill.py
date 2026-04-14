"""
Memory Write Skill — Persiste la interacción en contexto y memoria DB.

Responsabilidades:
  - Guardar el mensaje del usuario en shared_memory
  - Guardar la respuesta del asistente en shared_memory
  - Escribir entradas relevantes en context_store
  - Registrar metadata de la interacción (skills invocadas, tópico, confianza)

No hace llamadas LLM. Función sincrónica.
El merge summary (LLM) se dispara en background desde super_agent.py.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from schemas import ContextEntry, MemoryMessageRole
from services.context_store import context_store
from services.shared_memory import shared_memory

logger = logging.getLogger(__name__)


@dataclass
class MemoryWriteResult:
    """Resultado de la persistencia en memoria."""
    user_message_saved: bool
    assistant_response_saved: bool
    context_entries_written: int
    needs_merge: bool  # si la conversación ya amerita un merge summary


def write_interaction(
    company_id: str,
    conversation_id: str,
    user_message: str,
    assistant_response: str,
    skills_invoked: list[str],
    topic: str,
    confidence: float,
    sub_questions: Optional[list[str]] = None,
) -> MemoryWriteResult:
    """
    Persiste la interacción completa en memoria y contexto.

    Args:
        company_id: ID de la empresa.
        conversation_id: ID de la conversación.
        user_message: Mensaje normalizado del usuario.
        assistant_response: Respuesta final generada.
        skills_invoked: Lista de skills invocadas en este ciclo.
        topic: Tópico principal clasificado.
        confidence: Confianza de la respuesta (0.0–1.0).
        sub_questions: Sub-preguntas que se respondieron.

    Returns:
        MemoryWriteResult con el estado de la persistencia.
    """
    user_saved = False
    assistant_saved = False
    context_written = 0

    # 1. Guardar mensaje del usuario
    try:
        shared_memory.add_message(
            company_id=company_id,
            conversation_id=conversation_id,
            role=MemoryMessageRole.user,
            content=user_message,
        )
        user_saved = True
    except Exception as e:
        logger.error("memory_write: failed to save user message: %s", e)

    # 2. Guardar respuesta del asistente con metadata
    try:
        shared_memory.add_message(
            company_id=company_id,
            conversation_id=conversation_id,
            role=MemoryMessageRole.assistant,
            content=assistant_response,
            metadata={
                "skills_invoked": skills_invoked,
                "topic": topic,
                "confidence": round(confidence, 3),
                "sub_questions_count": len(sub_questions or []),
            },
        )
        assistant_saved = True
    except Exception as e:
        logger.error("memory_write: failed to save assistant response: %s", e)

    # 3. Registrar interacción en context_store
    try:
        accepted = context_store.put(
            company_id,
            ContextEntry(
                key=f"interaction_{conversation_id}_last",
                value={
                    "user_message": user_message[:200],  # truncar para no saturar
                    "topic": topic,
                    "skills": skills_invoked,
                    "confidence": confidence,
                },
                source_agent="super_agent",
                memory_priority="M_conv",
            ),
        )
        if accepted:
            context_written += 1
    except Exception as e:
        logger.error("memory_write: failed to write context entry: %s", e)

    # 4. Verificar si necesita merge summary
    needs_merge = shared_memory.needs_merge(company_id, conversation_id)

    return MemoryWriteResult(
        user_message_saved=user_saved,
        assistant_response_saved=assistant_saved,
        context_entries_written=context_written,
        needs_merge=needs_merge,
    )
