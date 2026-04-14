"""
Super-Agente PolPilot — Único punto de orquestación.

Reemplaza el sistema multiagente (orchestrator + agent_finanzas + agent_economia
+ agent_investigador + message_broker) por un pipeline secuencial con skills.

Pipeline obligatorio:
  1. ingest_skill       — normaliza y enriquece el input
  2. client_db_skill    — lee DB de empresa + memoria conversacional
  3. novelty_skill      — detecta si la query es nueva o repetida
  4. CLASSIFY (LLM)     — clasifica tópico + intención (un solo call LLM)
  5. execute skills     — reúne datos según tópicos activos (sin LLM)
  6. SYNTHESIZE (LLM)   — genera la respuesta final (un solo call LLM)
  7. memory_write_skill — persiste interacción en memoria y context_store

Decisiones técnicas:
  - Solo 2 llamadas LLM por query: classify + synthesize
  - El LLM NO se llama dentro de las skills (son funciones puras de datos)
  - No hay despacho paralelo a sub-agentes ni inter-agent calls
  - La respuesta final mantiene el schema QueryResponse para compatibilidad de API
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
    MemoryMessageRole,
    OrchestratorMetadata,
    QueryRequest,
    QueryResponse,
    ResponsePayload,
)
from services.context_store import context_store
from services.shared_memory import shared_memory
from services.skills import (
    client_db_skill,
    economy_skill,
    finance_skill,
    ingest_skill,
    intent_skill,
    memory_write_skill,
    novelty_skill,
    research_skill,
    topic_skill,
)

logger = logging.getLogger(__name__)

# ── Configuración ──────────────────────────────────────

_SYSTEM_PROMPT_PATH = Path(settings.PROMPTS_DIR) / "super_agent_system.md"
SYSTEM_PROMPT: str = _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")

client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

RELEVANCE_THRESHOLD = 0.20


# ── Etapa 4: Clasificación (LLM) ──────────────────────

async def _classify_query(
    user_message: str,
    detected_keywords: list[str],
    memory_context: str,
    company_profile_summary: str,
) -> topic_skill.TopicClassification:
    """
    Única llamada LLM para clasificar tópico + intención simultáneamente.
    Evita el call duplicado que existía en el orchestrator original.
    """
    prompt = topic_skill.build_classification_prompt(
        user_message=user_message,
        memory_context=memory_context,
        company_profile_summary=company_profile_summary,
        detected_keywords=detected_keywords,
        max_questions_per_topic=settings.MAX_QUESTIONS_PER_TOPIC,
    )

    response = await client.messages.create(
        model=settings.ORCHESTRATOR_MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    try:
        return topic_skill.parse_llm_response(raw)
    except (json.JSONDecodeError, Exception) as e:
        logger.warning("super_agent: classification parse error: %s — using fallback", e)
        # Fallback: activar todos los tópicos con baja relevance
        return topic_skill.TopicClassification(
            primary_topic="mixed",
            intent="consulta general",
            intent_description=user_message,
            complexity="simple",
            requires_live_data=bool(detected_keywords),
            finanzas=topic_skill.TopicDetail(relevance=0.5, sub_questions=[user_message]),
            economia=topic_skill.TopicDetail(relevance=0.3, sub_questions=[user_message]),
            investigacion=topic_skill.TopicDetail(relevance=0.2 if detected_keywords else 0.0),
        )


# ── Etapa 5: Ejecución de skills de datos ─────────────

async def _execute_data_skills(
    company_id: str,
    classification: topic_skill.TopicClassification,
    client_data: client_db_skill.ClientDBResult,
    original_message: str,
) -> dict[str, object]:
    """
    Reúne los datos necesarios ejecutando las skills correspondientes
    a los tópicos activos en la clasificación.

    Nota: research_skill es async (HTTP calls), el resto son sync.
    """
    data: dict[str, object] = {}

    if classification.finanzas.is_relevant:
        data["finanzas"] = finance_skill.execute(
            company_id=company_id,
            finanzas_context=client_data.finanzas_context,
            sub_questions=classification.finanzas.sub_questions,
        )
        logger.debug("super_agent: finance_skill executed")

    if classification.economia.is_relevant:
        data["economia"] = economy_skill.execute(
            company_id=company_id,
            economia_context=client_data.economia_context,
            sub_questions=classification.economia.sub_questions,
        )
        logger.debug("super_agent: economy_skill executed")

    if classification.investigacion.is_relevant or classification.requires_live_data:
        data["investigacion"] = await research_skill.execute(
            original_query=original_message,
            sub_questions=classification.investigacion.sub_questions,
        )
        logger.debug("super_agent: research_skill executed")

    return data


# ── Etapa 6: Síntesis (LLM) ───────────────────────────

async def _synthesize(
    user_message: str,
    classification: topic_skill.TopicClassification,
    intent_result: intent_skill.IntentResult,
    execution_data: dict[str, object],
    memory_context: str,
    novelty: novelty_skill.NoveltyResult,
) -> ResponsePayload:
    """
    Segunda (y última) llamada LLM: sintetiza todos los datos en la respuesta final.
    """
    # Construir bloque de datos para el prompt
    data_blocks: list[str] = []
    for topic_name, data_obj in execution_data.items():
        if hasattr(data_obj, "as_prompt_block"):
            block = data_obj.as_prompt_block()
            if block:
                data_blocks.append(block)

    data_section = "\n\n".join(data_blocks) if data_blocks else "Sin datos disponibles."

    novelty_note = ""
    if not novelty.is_new_query and novelty.similar_message:
        novelty_note = (
            f"\nNOTA: El usuario preguntó algo similar antes: \"{novelty.similar_message[:100]}...\" "
            "— Complementá sin repetir lo ya dicho."
        )

    synthesis_prompt = f"""Sos Angela, la asistente de PolPilot. Respondé esta consulta usando ÚNICAMENTE los datos provistos.

CONSULTA DEL USUARIO:
"{user_message}"

INTENCIÓN DETECTADA: {classification.intent} ({intent_result.urgency} urgencia)
INSTRUCCIÓN DE TONO: {intent_result.tone_hint}
{novelty_note}

CONTEXTO DE CONVERSACIÓN PREVIA:
{memory_context or "Sin conversación previa."}

DATOS DISPONIBLES:
{data_section}

TÓPICOS ACTIVOS: {", ".join(classification.active_topics) or "ninguno"}

Respondé ÚNICAMENTE con el JSON especificado en el system prompt. Sin texto adicional.
"""

    response = await client.messages.create(
        model=settings.ORCHESTRATOR_MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": synthesis_prompt}],
    )

    raw = response.content[0].text.strip()
    # Strip markdown code blocks
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        data = json.loads(raw)
        return ResponsePayload(**data)
    except (json.JSONDecodeError, Exception) as e:
        logger.warning("super_agent: synthesis parse error: %s — using raw text", e)
        return ResponsePayload(
            message=raw or "No pude generar una respuesta en este momento.",
            confidence=0.3,
            sources_used=classification.active_topics,
        )


# ── Pipeline principal ─────────────────────────────────

async def process_query(request: QueryRequest) -> QueryResponse:
    """
    Pipeline completo del super-agente.

    Reemplaza process_query() del orchestrator.py original con un flujo
    secuencial y un único punto de orquestación LLM.
    """
    start = time.time()
    conv_id = request.conversation_id or str(uuid.uuid4())

    logger.info(
        "super_agent: START company=%s conv=%s msg='%s...'",
        request.company_id, conv_id[:8], request.user_message[:60],
    )

    # ── Stage 1: INGEST ───────────────────────────────
    ingest = ingest_skill.execute(request.user_message, request.company_id)
    logger.debug("super_agent: ingest done keywords=%s", ingest.all_detected_keywords[:5])

    # ── Stage 2: CLIENT DB ────────────────────────────
    client_data = client_db_skill.execute(request.company_id, conv_id)
    logger.debug(
        "super_agent: client_db done has_real_data=%s has_memory=%s",
        client_data.has_real_data, client_data.has_memory,
    )

    # ── Stage 3: NOVELTY ──────────────────────────────
    novelty = novelty_skill.execute(
        company_id=request.company_id,
        conversation_id=conv_id,
        normalized_message=ingest.normalized_message,
    )
    logger.debug(
        "super_agent: novelty done is_new=%s similarity=%.2f",
        novelty.is_new_query, novelty.similarity_score,
    )

    # ── Stage 4+5: CLASSIFY (LLM) ─────────────────────
    classification = await _classify_query(
        user_message=ingest.normalized_message,
        detected_keywords=ingest.all_detected_keywords,
        memory_context=client_data.memory_context,
        company_profile_summary=client_data.summary_for_prompt(),
    )
    # Sobrescribir requires_live_data si ingest lo detectó
    if ingest.requires_live_data:
        classification.requires_live_data = True

    intent_result = intent_skill.from_classification(
        intent=classification.intent,
        intent_description=classification.intent_description,
    )
    logger.info(
        "super_agent: classify done topic=%s intent=%s active=%s",
        classification.primary_topic, intent_result.intent, classification.active_topics,
    )

    # ── Stage 6: EXECUTE SKILLS ───────────────────────
    execution_data = await _execute_data_skills(
        company_id=request.company_id,
        classification=classification,
        client_data=client_data,
        original_message=ingest.normalized_message,
    )
    skills_executed = ["ingest", "client_db", "novelty", "classify"] + [
        f"{k}_data" for k in execution_data
    ]
    logger.debug("super_agent: data skills done: %s", list(execution_data.keys()))

    # ── Stage 7: SYNTHESIZE (LLM) ─────────────────────
    response_payload = await _synthesize(
        user_message=ingest.normalized_message,
        classification=classification,
        intent_result=intent_result,
        execution_data=execution_data,
        memory_context=client_data.memory_context,
        novelty=novelty,
    )
    skills_executed.append("synthesize")
    logger.info(
        "super_agent: synthesize done confidence=%.2f sources=%s",
        response_payload.confidence, response_payload.sources_used,
    )

    # ── Stage 8: MEMORY WRITE ─────────────────────────
    skills_executed.append("memory_write")
    mem_result = memory_write_skill.write_interaction(
        company_id=request.company_id,
        conversation_id=conv_id,
        user_message=ingest.normalized_message,
        assistant_response=response_payload.message,
        skills_invoked=skills_executed,
        topic=classification.primary_topic,
        confidence=response_payload.confidence,
        sub_questions=classification.all_sub_questions,
    )
    logger.debug(
        "super_agent: memory_write done saved=%s/%s needs_merge=%s",
        mem_result.user_message_saved, mem_result.assistant_response_saved, mem_result.needs_merge,
    )

    # Disparar merge summary en background si es necesario
    if mem_result.needs_merge:
        asyncio.create_task(
            shared_memory.generate_merge_summary(request.company_id, conv_id)
        )

    # ── Build response ────────────────────────────────
    elapsed_ms = int((time.time() - start) * 1000)
    logger.info(
        "super_agent: DONE conv=%s elapsed=%dms",
        conv_id[:8], elapsed_ms,
    )

    return QueryResponse(
        response=response_payload,
        metadata=OrchestratorMetadata(
            conversation_id=conv_id,
            iterations=1,                           # single-pass en super-agente
            agents_activated=skills_executed,       # skills usadas (no agentes)
            total_sub_questions=len(classification.all_sub_questions),
            inter_agent_calls=0,                    # eliminado en super-agente
            stop_loss_score=None,                   # no aplica en single-pass
            stop_loss_decision="SUPER_AGENT_SINGLE_PASS",
        ),
    )
