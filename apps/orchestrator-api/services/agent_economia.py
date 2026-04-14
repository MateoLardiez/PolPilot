"""Agente de Economía — contexto macro, créditos y regulaciones."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import anthropic

from config import settings
from schemas import (
    AgentAnswer,
    AgentQueryRequest,
    AgentQueryResponse,
    DataPoint,
    SupportRequest,
)
from services.mock_data import build_economia_context

client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

_PROMPT_PATH = Path(__file__).parent / "agents_models" / "agent_economia.md"
_BASE_SYSTEM = _PROMPT_PATH.read_text(encoding="utf-8")


def _build_system() -> str:
    """Combina el system prompt base con el contexto macroeconómico actual."""
    macro_context = build_economia_context()
    return f"{_BASE_SYSTEM}\n\n---\n\n{macro_context}"


# Pre-construimos el system prompt al inicio (el contexto macro es global, no por empresa)
_SYSTEM_PROMPT = _build_system()


async def query_economia(request: AgentQueryRequest) -> AgentQueryResponse:
    """Procesa las preguntas del orquestador sobre economía y créditos."""

    questions_text = "\n".join(f"- {q}" for q in request.questions)

    user_prompt = f"""Empresa ID: {request.company_id}
Pregunta original del usuario: "{request.original_query}"

Preguntas específicas que debés responder usando el contexto macroeconómico y los créditos disponibles:
{questions_text}

Contexto de conversación previa: {request.conversation_context or "Ninguno"}

Respondé ÚNICAMENTE con JSON válido. Sin texto adicional antes ni después.
"""

    response = await client.messages.create(
        model=settings.AGENT_MODEL,
        max_tokens=2048,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        data = json.loads(raw)
        answers = []
        for a in data.get("answers", []):
            data_points = [DataPoint(**dp) for dp in a.get("data_points", [])]
            answers.append(AgentAnswer(
                question=a.get("question", ""),
                answer=a.get("answer", ""),
                confidence=float(a.get("confidence", 0.8)),
                data_points=data_points,
            ))
        return AgentQueryResponse(
            thread_id=request.thread_id,
            topic="economia",
            answers=answers,
            summary=data.get("summary", ""),
            needs_external_support=data.get("needs_external_support", False),
            external_support_question=data.get("external_support_question"),
        )
    except (json.JSONDecodeError, Exception):
        return AgentQueryResponse(
            thread_id=request.thread_id,
            topic="economia",
            answers=[],
            summary=raw,
        )


def build_support_request(
    question: str,
    target_agent: str,
    company_id: str,
    thread_id: Optional[str] = None,
    original_query: Optional[str] = None,
    context_payload: Optional[dict] = None,
) -> SupportRequest:
    """Construye un support_request desde el agente de Economía hacia otro agente."""
    return SupportRequest(
        source_agent="economia",
        target_agent=target_agent,
        question=question,
        company_id=company_id,
        thread_id=thread_id,
        original_query=original_query,
        context_payload=context_payload,
    )
