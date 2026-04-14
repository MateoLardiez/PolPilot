"""
Novelty Skill — Detecta si la consulta es nueva o ya fue respondida recientemente.

Responsabilidades:
  - Comparar la query actual con mensajes recientes de la conversación
  - Estimar similitud por overlap de tokens (sin LLM, rápido)
  - Retornar si hay contexto previo relevante y cuál es

No hace llamadas LLM. Función sincrónica y determinística.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from services.shared_memory import shared_memory

# Umbral de overlap de palabras para considerar "similar"
_SIMILARITY_THRESHOLD = 0.55

# Stop-words en español (simplificado)
_STOP_WORDS = {
    "el", "la", "los", "las", "un", "una", "unos", "unas",
    "de", "del", "al", "a", "en", "con", "por", "para",
    "que", "qué", "cómo", "como", "cuál", "cual",
    "es", "son", "hay", "tiene", "tengo",
    "me", "mi", "tu", "su", "se",
    "y", "o", "pero", "si", "no",
    "puedo", "puede", "quiero", "quiere",
}


@dataclass
class NoveltyResult:
    """Resultado de la detección de novedad."""
    is_new_query: bool
    similarity_score: float  # 0.0 = completamente nuevo, 1.0 = idéntico
    similar_message: Optional[str]  # mensaje previo similar (si existe)
    context_note: str  # nota para incluir en el prompt del super-agente


def _tokenize(text: str) -> set[str]:
    """Tokeniza texto a un set de palabras relevantes (sin stop-words)."""
    words = re.findall(r"[a-záéíóúñü]+", text.lower())
    return {w for w in words if w not in _STOP_WORDS and len(w) > 2}


def execute(
    company_id: str,
    conversation_id: str,
    normalized_message: str,
    lookback: int = 10,
) -> NoveltyResult:
    """
    Detecta si la consulta ya fue respondida en la conversación reciente.

    Args:
        company_id: ID de la empresa.
        conversation_id: ID de la conversación activa.
        normalized_message: Mensaje normalizado por ingest_skill.
        lookback: Cuántos mensajes previos revisar.

    Returns:
        NoveltyResult indicando si es nueva y qué contexto previo hay.
    """
    recent = shared_memory.get_recent_messages(company_id, conversation_id, limit=lookback)
    if not recent:
        return NoveltyResult(
            is_new_query=True,
            similarity_score=0.0,
            similar_message=None,
            context_note="Primera consulta de esta sesión.",
        )

    query_tokens = _tokenize(normalized_message)
    best_score = 0.0
    best_match: Optional[str] = None

    for msg in recent:
        if msg.role.value != "user":
            continue
        msg_tokens = _tokenize(msg.content)
        if not msg_tokens:
            continue
        intersection = query_tokens & msg_tokens
        union = query_tokens | msg_tokens
        score = len(intersection) / len(union) if union else 0.0
        if score > best_score:
            best_score = score
            best_match = msg.content

    is_new = best_score < _SIMILARITY_THRESHOLD

    if is_new:
        note = "Consulta nueva — sin contexto previo muy similar."
    else:
        note = f"Consulta similar a una previa (similitud: {best_score:.0%}). Considera reutilizar contexto."

    return NoveltyResult(
        is_new_query=is_new,
        similarity_score=round(best_score, 3),
        similar_message=best_match if not is_new else None,
        context_note=note,
    )
