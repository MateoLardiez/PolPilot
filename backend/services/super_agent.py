"""
Super-Agente PolPilot v3 — Agent SDK con Tool Use.

Arquitectura:
  - Un único agente (Angela) con TODAS las skills registradas como tools
  - El agente decide cuándo y cómo llamar cada skill (no hay pipeline fijo)
  - Loop: mensaje → tool_use → tool_results → … → end_turn → respuesta final
  - Skills son funciones puras; el LLM solo orquesta qué llamar y cuándo

Flujo de ejecución:
  1. Recibe QueryRequest con mensaje del usuario + company_id
  2. Construye mensajes iniciales con contexto de empresa y conversación
  3. Corre el agent loop: el LLM llama tools hasta tener suficiente info
  4. En end_turn: parsea la respuesta final como ResponsePayload JSON
  5. Escribe en memoria y devuelve QueryResponse

Skills disponibles como tools:
  ingest_skill, client_db_skill, novelty_skill,
  finance_skill, economy_skill, research_skill,
  memory_management_skill, skill_creator_skill,
  eval_skill, system_prompt_skill
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Optional

import anthropic

from config import settings
from schemas import (
    OrchestratorMetadata,
    QueryRequest,
    QueryResponse,
    ResponsePayload,
)
from services.shared_memory import shared_memory
from services.skills import (
    client_db_skill,
    economy_skill,
    eval_skill,
    finance_skill,
    ingest_skill,
    memory_management_skill,
    memory_write_skill,
    novelty_skill,
    research_skill,
    skill_creator_skill,
    system_prompt_skill,
)

logger = logging.getLogger(__name__)

# ── Límite de iteraciones del loop ─────────────────────
MAX_TOOL_ITERATIONS = 8


# ── System Prompt ──────────────────────────────────────

def _load_system_prompt() -> str:
    path = Path(settings.PROMPTS_DIR) / "super_agent_system.md"
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.error("super_agent: system prompt no encontrado en %s", path)
        return "Sos Angela, asistente de PolPilot. Respondé en JSON."


# ── Cliente Anthropic ──────────────────────────────────

def _get_client() -> anthropic.AsyncAnthropic:
    if not settings.ANTHROPIC_API_KEY:
        raise ValueError(
            "ANTHROPIC_API_KEY no configurada. "
            "Revisar el archivo .env del backend."
        )
    return anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)


# ── Definición de Tools (Skills como Tools del Agent SDK) ──

SKILL_TOOLS: list[dict] = [
    {
        "name": "ingest_skill",
        "description": (
            "Normaliza el mensaje del usuario, detecta keywords financieras "
            "y económicas, e identifica si requiere datos en tiempo real. "
            "Llamar SIEMPRE como primer paso."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "user_message": {"type": "string"},
                "company_id": {"type": "string"},
            },
            "required": ["user_message", "company_id"],
        },
    },
    {
        "name": "client_db_skill",
        "description": (
            "Obtiene datos internos de la empresa: finanzas, economía local "
            "y contexto de conversación previa desde la base de datos."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "company_id": {"type": "string"},
                "conversation_id": {"type": "string"},
            },
            "required": ["company_id", "conversation_id"],
        },
    },
    {
        "name": "novelty_skill",
        "description": (
            "Detecta si la consulta es nueva o similar a preguntas anteriores "
            "en la conversación, para evitar repetir información."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "company_id": {"type": "string"},
                "conversation_id": {"type": "string"},
                "normalized_message": {"type": "string"},
            },
            "required": ["company_id", "conversation_id", "normalized_message"],
        },
    },
    {
        "name": "finance_skill",
        "description": (
            "Obtiene y formatea datos financieros internos: flujo de caja, "
            "liquidez, cuentas por cobrar/pagar, stock y health score. "
            "Usar cuando la consulta es sobre finanzas de la empresa."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "company_id": {"type": "string"},
                "sub_questions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Preguntas específicas a responder con datos financieros",
                },
            },
            "required": ["company_id"],
        },
    },
    {
        "name": "economy_skill",
        "description": (
            "Obtiene datos macroeconómicos argentinos: créditos PyME disponibles, "
            "tasas BCRA, inflación, regulaciones AFIP. "
            "Usar cuando la consulta es sobre el contexto económico."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "company_id": {"type": "string"},
                "sub_questions": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["company_id"],
        },
    },
    {
        "name": "research_skill",
        "description": (
            "Obtiene datos en TIEMPO REAL desde APIs públicas: tipos de cambio "
            "(dólar oficial, blue, MEP, CCL), tasas BCRA, reservas internacionales, "
            "préstamos PyME vigentes. Usar para cualquier consulta sobre cotizaciones actuales."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "original_query": {"type": "string"},
                "sub_questions": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["original_query"],
        },
    },
    {
        "name": "memory_management_skill",
        "description": (
            "Gestión avanzada de memoria persistente: leer hechos históricos "
            "de la empresa, escribir datos importantes para recordar, "
            "obtener perfil acumulado."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["read", "write", "get_facts", "clear"],
                },
                "company_id": {"type": "string"},
                "conversation_id": {"type": "string"},
                "content": {
                    "type": "string",
                    "description": "Hecho a guardar (solo action=write)",
                },
            },
            "required": ["action", "company_id"],
        },
    },
    {
        "name": "skill_creator_skill",
        "description": (
            "Crea una nueva skill personalizada cuando ninguna existente "
            "resuelve el caso de uso. Genera el archivo .py desde un template. "
            "Usar solo cuando realmente falte una capacidad nueva."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "skill_name": {
                    "type": "string",
                    "description": "Nombre en snake_case sin sufijo _skill",
                },
                "description": {"type": "string"},
                "use_case": {"type": "string"},
            },
            "required": ["skill_name", "description", "use_case"],
        },
    },
    {
        "name": "eval_skill",
        "description": (
            "Ejecuta o prepara evaluaciones de calidad de respuestas. "
            "Devuelve casos de prueba predefinidos o evalúa una respuesta inline."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "company_id": {"type": "string"},
                "evaluate_response": {
                    "type": "object",
                    "description": "ResponsePayload a evaluar (opcional)",
                },
                "evaluate_against_case_id": {
                    "type": "string",
                    "description": "ID del test case (tc_001…tc_005)",
                },
            },
            "required": ["company_id"],
        },
    },
    {
        "name": "system_prompt_skill",
        "description": (
            "Lee o actualiza el system prompt del agente. "
            "Usar para inspeccionar el comportamiento actual o ajustarlo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["read", "update", "reset", "list"],
                },
                "prompt_name": {
                    "type": "string",
                    "description": "super_agent_system | orchestrator_system",
                },
                "content": {
                    "type": "string",
                    "description": "Nuevo contenido (solo action=update)",
                },
            },
            "required": ["action", "prompt_name"],
        },
    },
]


# ── Tool Dispatcher ────────────────────────────────────

async def _dispatch(tool_name: str, tool_input: dict, ctx: dict) -> str:
    """
    Ejecuta la skill correspondiente y devuelve el resultado como JSON string.
    ctx contiene company_id, conversation_id y user_message del request.
    """
    cid = tool_input.get("company_id", ctx["company_id"])
    conv = tool_input.get("conversation_id", ctx["conversation_id"])

    try:
        if tool_name == "ingest_skill":
            r = ingest_skill.execute(
                tool_input.get("user_message", ctx["user_message"]),
                cid,
            )
            return json.dumps({
                "normalized_message": r.normalized_message,
                "requires_live_data": r.requires_live_data,
                "keywords": r.all_detected_keywords[:10],
            })

        elif tool_name == "client_db_skill":
            r = client_db_skill.execute(cid, conv)
            return json.dumps({
                "has_real_data": r.has_real_data,
                "has_memory": r.has_memory,
                "finanzas_summary": r.finanzas_context[:400] if r.finanzas_context else None,
                "economia_summary": r.economia_context[:400] if r.economia_context else None,
                "memory_context": r.memory_context[:300] if r.memory_context else None,
            })

        elif tool_name == "novelty_skill":
            r = novelty_skill.execute(
                company_id=cid,
                conversation_id=conv,
                normalized_message=tool_input.get(
                    "normalized_message", ctx["user_message"]
                ),
            )
            return json.dumps({
                "is_new_query": r.is_new_query,
                "similarity_score": r.similarity_score,
                "similar_message": r.similar_message,
            })

        elif tool_name == "finance_skill":
            db = client_db_skill.execute(cid, conv)
            r = finance_skill.execute(
                company_id=cid,
                finanzas_context=db.finanzas_context,
                sub_questions=tool_input.get("sub_questions", []),
            )
            return json.dumps({
                "is_available": r.is_available(),
                "data_block": r.as_prompt_block()[:1200],
            })

        elif tool_name == "economy_skill":
            db = client_db_skill.execute(cid, conv)
            r = economy_skill.execute(
                company_id=cid,
                economia_context=db.economia_context,
                sub_questions=tool_input.get("sub_questions", []),
            )
            return json.dumps({
                "is_available": r.is_available(),
                "data_block": r.as_prompt_block()[:1200],
            })

        elif tool_name == "research_skill":
            r = await research_skill.execute(
                original_query=tool_input.get("original_query", ctx["user_message"]),
                sub_questions=tool_input.get("sub_questions", []),
            )
            return json.dumps({
                "sources_fetched": r.sources_fetched,
                "is_available": r.is_available,
                "data_block": r.as_prompt_block()[:1400],
            })

        elif tool_name == "memory_management_skill":
            r = memory_management_skill.execute(
                action=tool_input.get("action", "read"),
                company_id=cid,
                conversation_id=tool_input.get("conversation_id", conv),
                content=tool_input.get("content"),
            )
            return json.dumps(r)

        elif tool_name == "skill_creator_skill":
            r = skill_creator_skill.execute(
                skill_name=tool_input.get("skill_name", ""),
                description=tool_input.get("description", ""),
                use_case=tool_input.get("use_case", ""),
            )
            return json.dumps(r)

        elif tool_name == "eval_skill":
            r = eval_skill.execute(
                company_id=cid,
                evaluate_response=tool_input.get("evaluate_response"),
                evaluate_against_case_id=tool_input.get("evaluate_against_case_id"),
            )
            return json.dumps(r)

        elif tool_name == "system_prompt_skill":
            r = system_prompt_skill.execute(
                action=tool_input.get("action", "read"),
                prompt_name=tool_input.get("prompt_name", "super_agent_system"),
                content=tool_input.get("content"),
            )
            return json.dumps(r)

        else:
            return json.dumps({"error": f"Skill '{tool_name}' no registrada"})

    except Exception as e:
        logger.error("dispatch error: tool=%s error=%s", tool_name, e)
        return json.dumps({"error": str(e), "tool": tool_name})


# ── Agent Loop ─────────────────────────────────────────

async def _run_agent_loop(
    user_message: str,
    company_id: str,
    conversation_id: str,
    conversation_context: Optional[str],
) -> tuple[str, list[str]]:
    """
    Loop principal del agente con tool_use.

    El LLM llama tools hasta tener suficiente información,
    luego genera la respuesta final en end_turn.

    Returns:
        (raw_response_text, tools_called_list)
    """
    client = _get_client()
    system_prompt = _load_system_prompt()

    ctx = {
        "company_id": company_id,
        "conversation_id": conversation_id,
        "user_message": user_message,
    }

    # Mensaje inicial con contexto de empresa y conversación
    initial_content = (
        f"[EMPRESA: {company_id} | CONV: {conversation_id[:8]}]\n"
    )
    if conversation_context:
        initial_content += f"[CONTEXTO PREVIO]\n{conversation_context}\n\n"
    initial_content += f"[CONSULTA]\n{user_message}"

    messages: list[dict] = [
        {"role": "user", "content": initial_content}
    ]

    tools_called: list[str] = []

    for iteration in range(MAX_TOOL_ITERATIONS):
        response = await client.messages.create(
            model=settings.ORCHESTRATOR_MODEL,
            max_tokens=4096,
            system=system_prompt,
            tools=SKILL_TOOLS,
            messages=messages,
        )

        logger.debug(
            "agent_loop: iter=%d stop_reason=%s",
            iteration, response.stop_reason,
        )

        # ── Respuesta final ────────────────────────────
        if response.stop_reason == "end_turn":
            final_text = "".join(
                block.text for block in response.content if hasattr(block, "text")
            )
            return final_text.strip(), tools_called

        # ── Tool use ───────────────────────────────────
        if response.stop_reason == "tool_use":
            tool_results: list[dict] = []

            for block in response.content:
                if block.type == "tool_use":
                    tools_called.append(block.name)
                    logger.info(
                        "agent: tool=%s input_keys=%s",
                        block.name, list(block.input.keys()),
                    )
                    result_str = await _dispatch(block.name, block.input, ctx)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_str,
                    })

            # Agregar al historial de mensajes
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        else:
            logger.warning("agent_loop: stop_reason inesperado=%s", response.stop_reason)
            break

    # Iteraciones agotadas
    logger.warning("agent_loop: MAX_TOOL_ITERATIONS alcanzado para conv=%s", conversation_id[:8])
    return (
        json.dumps({
            "message": (
                "Alcancé el límite de procesamiento para esta consulta. "
                "Por favor, reformulá la pregunta o dividila en partes más simples."
            ),
            "confidence": 0.3,
            "sources_used": tools_called,
        }),
        tools_called,
    )


# ── Parser de respuesta final ──────────────────────────

def _parse_response(raw: str) -> ResponsePayload:
    """
    Intenta parsear la respuesta del agente como JSON ResponsePayload.
    Si falla (el agente respondió en texto libre), lo envuelve como mensaje.
    """
    text = raw.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    try:
        data = json.loads(text)
        return ResponsePayload(**data)
    except Exception:
        # El agente respondió en texto libre — lo aceptamos como mensaje
        return ResponsePayload(
            message=raw or "No pude generar una respuesta en este momento.",
            confidence=0.4,
            sources_used=["agent"],
        )


# ── Entry point ────────────────────────────────────────

async def process_query(request: QueryRequest) -> QueryResponse:
    """
    Punto de entrada del super-agente v3.

    El agente decide qué skills llamar basándose en la consulta.
    No hay pipeline fijo: el LLM orquesta las tools.
    """
    start = time.time()

    if not settings.ANTHROPIC_API_KEY:
        raise ValueError(
            "ANTHROPIC_API_KEY no configurada. Revisar .env del backend."
        )

    conv_id = request.conversation_id or str(uuid.uuid4())

    logger.info(
        "super_agent_v3: START company=%s conv=%s msg='%.60s'",
        request.company_id, conv_id[:8], request.user_message,
    )

    # Correr el loop del agente
    raw_response, tools_called = await _run_agent_loop(
        user_message=request.user_message,
        company_id=request.company_id,
        conversation_id=conv_id,
        conversation_context=request.conversation_context,
    )

    # Parsear respuesta final
    payload = _parse_response(raw_response)

    # Persistir en memoria conversacional
    mem_result = memory_write_skill.write_interaction(
        company_id=request.company_id,
        conversation_id=conv_id,
        user_message=request.user_message,
        assistant_response=payload.message,
        skills_invoked=tools_called,
        topic="agent_sdk",
        confidence=payload.confidence,
        sub_questions=[],
    )

    # Merge summary en background si la conversación creció mucho
    if mem_result.needs_merge:
        asyncio.create_task(
            shared_memory.generate_merge_summary(request.company_id, conv_id)
        )

    elapsed_ms = int((time.time() - start) * 1000)
    logger.info(
        "super_agent_v3: DONE conv=%s elapsed=%dms tools=%s confidence=%.2f",
        conv_id[:8], elapsed_ms, tools_called, payload.confidence,
    )

    return QueryResponse(
        response=payload,
        metadata=OrchestratorMetadata(
            conversation_id=conv_id,
            iterations=len(tools_called),
            agents_activated=tools_called,
            total_sub_questions=0,
            inter_agent_calls=0,
            stop_loss_score=None,
            stop_loss_decision="AGENT_SDK_TOOL_USE",
        ),
    )
