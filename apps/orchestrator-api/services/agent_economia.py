"""Agente de Economía — contexto macro y créditos."""

from __future__ import annotations

import json

import anthropic

from config import settings
from schemas import AgentAnswer, AgentQueryRequest, AgentQueryResponse, DataPoint

client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

ECONOMIA_SYSTEM = """Sos el Agente de Economía de PolPilot. Tu rol es analizar el contexto EXTERNO relevante para la empresa.

Tus fuentes de datos:
- Líneas de crédito PyME disponibles (bancos, fintechs, programas subsidiados)
- Tasas de referencia BCRA
- Inflación proyectada
- Tipo de cambio
- Regulaciones vigentes y nuevas
- Programas de subsidio o bonificación
- Tendencias sectoriales
- Estacionalidad del mercado
- Datos de proveedores (precios, tendencias)

Reglas:
- Solo respondés con datos verificables. Si no tenés un dato actualizado, decí "dato pendiente de actualización".
- NUNCA inventés tasas, montos o condiciones de créditos.
- Citá la fuente cuando sea posible (ej: "BCRA Transparencia", "Boletín Oficial").
- Respondé en JSON.
"""


async def query_economia(request: AgentQueryRequest) -> AgentQueryResponse:
    """Procesa las preguntas del orquestador sobre economía."""

    questions_text = "\n".join(f"- {q}" for q in request.questions)

    user_prompt = f"""Empresa: {request.company_id}
Pregunta original del usuario: "{request.original_query}"

Preguntas que debés responder:
{questions_text}

Contexto previo: {request.conversation_context or "Ninguno"}

Respondé con JSON:
{{
  "answers": [
    {{
      "question": "la pregunta",
      "answer": "tu respuesta con datos concretos",
      "confidence": 0.0-1.0,
      "data_points": [{{"label": "nombre", "value": "valor", "source": "fuente"}}]
    }}
  ],
  "summary": "resumen ejecutivo de todas las respuestas",
  "needs_external_support": false,
  "external_support_question": null
}}
"""

    response = await client.messages.create(
        model=settings.AGENT_MODEL,
        max_tokens=2048,
        system=ECONOMIA_SYSTEM,
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
        return AgentQueryResponse(
            thread_id=request.thread_id,
            topic="economia",
            answers=[AgentAnswer(**a) for a in data.get("answers", [])],
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
