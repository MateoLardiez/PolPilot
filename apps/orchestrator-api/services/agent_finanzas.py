"""Agente de Finanzas — analiza datos internos de la empresa."""

from __future__ import annotations

import json

import anthropic

from config import settings
from schemas import AgentAnswer, AgentQueryRequest, AgentQueryResponse, DataPoint

client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

FINANZAS_SYSTEM = """Sos el Agente de Finanzas de PolPilot. Tu rol es analizar la situación financiera INTERNA de la empresa.

Tus fuentes de datos:
- Flujo de caja (ingresos, egresos, neto)
- Márgenes (bruto, neto)
- Liquidez disponible
- Cuentas por cobrar / pagar
- Deudas vigentes
- Proyecciones financieras
- Health Score financiero
- Datos de clientes morosos
- Inventario y stock

Reglas:
- Solo respondés con datos concretos. Si no tenés un dato, decí "dato no disponible".
- NUNCA inventés números.
- Siempre incluí la fuente del dato (ej: "financials_monthly.cash_balance").
- Respondé en JSON.
"""


async def query_finanzas(request: AgentQueryRequest) -> AgentQueryResponse:
    """Procesa las preguntas del orquestador sobre finanzas."""

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
      "data_points": [{{"label": "nombre", "value": "valor", "source": "tabla.columna"}}]
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
        system=FINANZAS_SYSTEM,
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
            topic="finanzas",
            answers=[AgentAnswer(**a) for a in data.get("answers", [])],
            summary=data.get("summary", ""),
            needs_external_support=data.get("needs_external_support", False),
            external_support_question=data.get("external_support_question"),
        )
    except (json.JSONDecodeError, Exception):
        return AgentQueryResponse(
            thread_id=request.thread_id,
            topic="finanzas",
            answers=[],
            summary=raw,
        )
