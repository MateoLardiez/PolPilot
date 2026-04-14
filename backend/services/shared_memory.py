"""
Shared Memory — Memoria compartida entre agentes y el orquestador.

Implementa memory.sqlite conceptual (in-memory para MVP):
- Conversaciones: historial de mensajes por empresa/conversación
- Merge Summaries: resúmenes incrementales que comprimen el contexto
- Query Log: registro de todas las queries del orquestador para trazabilidad
- Generación de contexto: arma el conversation_context para los agentes

Flujo:
  Usuario envía mensaje → se guarda en memoria → se genera/actualiza merge summary
  → el orquestador lee el summary como conversation_context
  → los agentes reciben el contexto filtrado
  → la respuesta se guarda en memoria → se actualiza el merge summary
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from typing import Optional

import anthropic

from config import settings
from schemas import (
    ConversationState,
    MemoryMessage,
    MemoryMessageRole,
    MergeSummary,
    QueryLogEntry,
)

logger = logging.getLogger(__name__)

client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

# Máximo de mensajes antes de forzar un merge summary
MERGE_THRESHOLD = 6
# Máximo de mensajes raw que se incluyen en el contexto (los más recientes)
RAW_CONTEXT_WINDOW = 4


class SharedMemory:
    """
    Memoria compartida del sistema (in-memory para hackathon).

    Estructura:
      conversations[company_id][conversation_id] → ConversationState
    """

    def __init__(self) -> None:
        self._conversations: dict[str, dict[str, ConversationState]] = defaultdict(dict)

    # ── Gestión de conversaciones ──────────────────────

    def get_or_create_conversation(
        self, company_id: str, conversation_id: str
    ) -> ConversationState:
        if conversation_id not in self._conversations[company_id]:
            self._conversations[company_id][conversation_id] = ConversationState(
                conversation_id=conversation_id,
                company_id=company_id,
            )
        return self._conversations[company_id][conversation_id]

    def get_conversation(
        self, company_id: str, conversation_id: str
    ) -> Optional[ConversationState]:
        return self._conversations.get(company_id, {}).get(conversation_id)

    def list_conversations(self, company_id: str) -> list[str]:
        return list(self._conversations.get(company_id, {}).keys())

    # ── Mensajes ───────────────────────────────────────

    def add_message(
        self,
        company_id: str,
        conversation_id: str,
        role: MemoryMessageRole,
        content: str,
        metadata: Optional[dict] = None,
    ) -> MemoryMessage:
        """Agrega un mensaje a la conversación."""
        conv = self.get_or_create_conversation(company_id, conversation_id)
        msg = MemoryMessage(
            role=role,
            content=content,
            company_id=company_id,
            conversation_id=conversation_id,
            metadata=metadata,
        )
        conv.messages.append(msg)
        conv.total_messages += 1
        return msg

    def get_recent_messages(
        self, company_id: str, conversation_id: str, limit: int = RAW_CONTEXT_WINDOW
    ) -> list[MemoryMessage]:
        """Devuelve los N mensajes más recientes."""
        conv = self.get_conversation(company_id, conversation_id)
        if not conv:
            return []
        return conv.messages[-limit:]

    # ── Merge Summaries ────────────────────────────────

    def get_latest_summary(
        self, company_id: str, conversation_id: str
    ) -> Optional[MergeSummary]:
        """Devuelve el merge summary más reciente de la conversación."""
        conv = self.get_conversation(company_id, conversation_id)
        if not conv or not conv.summaries:
            return None
        return conv.summaries[-1]

    def _store_summary(
        self, company_id: str, conversation_id: str, summary: MergeSummary
    ) -> None:
        conv = self.get_or_create_conversation(company_id, conversation_id)
        conv.summaries.append(summary)
        conv.active_context = summary.summary_text

    def needs_merge(self, company_id: str, conversation_id: str) -> bool:
        """Verifica si la conversación necesita un nuevo merge summary."""
        conv = self.get_conversation(company_id, conversation_id)
        if not conv:
            return False

        last_summary = self.get_latest_summary(company_id, conversation_id)
        if not last_summary:
            return conv.total_messages >= MERGE_THRESHOLD

        messages_since_last = conv.total_messages - last_summary.messages_covered
        return messages_since_last >= MERGE_THRESHOLD

    async def generate_merge_summary(
        self, company_id: str, conversation_id: str
    ) -> Optional[MergeSummary]:
        """
        Genera un merge summary incremental usando Haiku (modelo ligero).
        Combina el summary anterior con los mensajes nuevos.
        """
        conv = self.get_conversation(company_id, conversation_id)
        if not conv or not conv.messages:
            return None

        last_summary = self.get_latest_summary(company_id, conversation_id)
        iteration = (last_summary.iteration + 1) if last_summary else 1

        # Mensajes a resumir: los que no están cubiertos por el último summary
        covered = last_summary.messages_covered if last_summary else 0
        new_messages = conv.messages[covered:]

        if not new_messages:
            return last_summary

        messages_text = "\n".join(
            f"[{m.role.value}]: {m.content}" for m in new_messages
        )

        prev_summary_text = last_summary.summary_text if last_summary else "Sin resumen previo."
        prev_facts = last_summary.key_facts if last_summary else []

        prompt = f"""Sos el agente de resumen de PolPilot. Tu trabajo es generar un MERGE SUMMARY 
incremental de la conversación.

RESUMEN PREVIO (iteración {iteration - 1}):
{prev_summary_text}

HECHOS CLAVE PREVIOS:
{json.dumps(prev_facts, ensure_ascii=False) if prev_facts else "Ninguno"}

MENSAJES NUEVOS ({len(new_messages)} mensajes):
{messages_text}

INSTRUCCIONES:
1. Combiná el resumen previo con los mensajes nuevos.
2. Priorizá: datos financieros concretos, decisiones tomadas, preguntas pendientes.
3. Descartá: saludos, agradecimientos, repeticiones.
4. Mantené el resumen en máximo 300 palabras.
5. Extraé los hechos clave como lista.

Respondé ÚNICAMENTE con JSON:
{{
  "summary_text": "resumen actualizado de toda la conversación",
  "key_facts": ["hecho clave 1", "hecho clave 2"]
}}"""

        try:
            response = await client.messages.create(
                model="claude-haiku-4-20250414",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )

            raw = response.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()

            data = json.loads(raw)

            summary = MergeSummary(
                company_id=company_id,
                conversation_id=conversation_id,
                summary_text=data.get("summary_text", raw),
                messages_covered=conv.total_messages,
                iteration=iteration,
                key_facts=data.get("key_facts", []),
            )
            self._store_summary(company_id, conversation_id, summary)

            logger.info(
                "Merge summary #%d generated for %s/%s (%d messages covered)",
                iteration, company_id, conversation_id, conv.total_messages,
            )
            return summary

        except Exception as e:
            logger.error("Failed to generate merge summary: %s", e)
            return last_summary

    # ── Contexto para agentes ──────────────────────────

    def build_conversation_context(
        self, company_id: str, conversation_id: str
    ) -> str:
        """
        Construye el conversation_context que reciben los agentes.

        Estructura:
        1. Merge summary acumulado (si existe)
        2. Últimos N mensajes raw (ventana reciente)
        """
        parts: list[str] = []

        # 1. Summary acumulado
        summary = self.get_latest_summary(company_id, conversation_id)
        if summary:
            parts.append(f"[RESUMEN ACUMULADO (iteración #{summary.iteration}, "
                         f"{summary.messages_covered} msgs)]:\n{summary.summary_text}")
            if summary.key_facts:
                parts.append(f"[HECHOS CLAVE]: {', '.join(summary.key_facts)}")

        # 2. Mensajes recientes
        recent = self.get_recent_messages(company_id, conversation_id)
        if recent:
            recent_text = "\n".join(
                f"  [{m.role.value}]: {m.content}" for m in recent
            )
            parts.append(f"[MENSAJES RECIENTES ({len(recent)})]:\n{recent_text}")

        return "\n\n".join(parts) if parts else ""

    # ── Query Log ──────────────────────────────────────

    def log_query(
        self, company_id: str, conversation_id: str, entry: QueryLogEntry
    ) -> None:
        """Registra una query en el log del orquestador."""
        conv = self.get_or_create_conversation(company_id, conversation_id)
        conv.query_log.append(entry)

    def get_query_log(
        self, company_id: str, conversation_id: str
    ) -> list[QueryLogEntry]:
        conv = self.get_conversation(company_id, conversation_id)
        if not conv:
            return []
        return conv.query_log

    # ── Stats ──────────────────────────────────────────

    def get_conversation_stats(
        self, company_id: str, conversation_id: str
    ) -> dict:
        conv = self.get_conversation(company_id, conversation_id)
        if not conv:
            return {"exists": False}
        return {
            "exists": True,
            "conversation_id": conversation_id,
            "company_id": company_id,
            "total_messages": conv.total_messages,
            "total_summaries": len(conv.summaries),
            "total_queries": len(conv.query_log),
            "has_active_context": conv.active_context is not None,
            "created_at": conv.created_at,
        }

    # ── Reset ──────────────────────────────────────────

    def clear_conversation(self, company_id: str, conversation_id: str) -> None:
        if company_id in self._conversations:
            self._conversations[company_id].pop(conversation_id, None)

    def clear_company(self, company_id: str) -> None:
        self._conversations.pop(company_id, None)


# Singleton global
shared_memory = SharedMemory()
