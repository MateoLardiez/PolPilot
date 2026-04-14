"""Servicio del Orquestador — lógica core del RAC."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path

import anthropic

from config import settings
from schemas import (
    AgentQueryRequest,
    AgentQueryResponse,
    Artifact,
    ArtifactType,
    CollaborationLog,
    Complexity,
    ContextEntry,
    FollowUpEvaluation,
    OrchestratorMetadata,
    QueryRequest,
    QueryResponse,
    QuestionExpansion,
    ResponsePayload,
    StopLossCheck,
    SupportRequest,
)
from services.context_store import context_store
from services.message_broker import message_broker

logger = logging.getLogger(__name__)


def _load_system_prompt() -> str:
    path = Path(settings.PROMPTS_DIR) / "orchestrator_system.md"
    return path.read_text(encoding="utf-8")


SYSTEM_PROMPT = _load_system_prompt()

client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)


# ── Etapa 1+2: Clasificar y expandir preguntas ───────

async def expand_query(request: QueryRequest) -> QuestionExpansion:
    """Usa el LLM para clasificar la query y expandirla en sub-preguntas por tópico."""

    user_prompt = f"""Recibiste esta consulta de la empresa {request.company_id}:

"{request.user_message}"

Contexto de conversación previo:
{request.conversation_context or "Sin contexto previo."}

Respondé ÚNICAMENTE con un JSON válido con esta estructura (sin texto adicional):
{{
  "original_query": "la pregunta exacta",
  "intent": "descripción de la intención",
  "complexity": "simple | medium | complex",
  "topics": {{
    "finanzas": {{
      "relevance": 0.0-1.0,
      "questions": ["pregunta 1", "pregunta 2"]
    }},
    "economia": {{
      "relevance": 0.0-1.0,
      "questions": ["pregunta 1", "pregunta 2"]
    }}
  }}
}}

Reglas:
- Si un tópico no es relevante, poné relevance < 0.2 y questions vacío.
- Máximo {settings.MAX_QUESTIONS_PER_TOPIC} preguntas por tópico.
- Las preguntas deben ser específicas y accionables.
"""

    response = await client.messages.create(
        model=settings.ORCHESTRATOR_MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = response.content[0].text.strip()
    # Extraer JSON del response (puede venir con markdown code blocks)
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    data = json.loads(raw)
    return QuestionExpansion(**data)


# ── Etapa 3: Despacho paralelo a agentes ──────────────

async def dispatch_to_agent(
    topic: str,
    agent_fn,
    request: AgentQueryRequest,
) -> AgentQueryResponse:
    """Llama a un agente individual."""
    return await agent_fn(request)


async def dispatch_all(
    expansion: QuestionExpansion,
    company_id: str,
    conversation_context: str | None,
    agent_registry: dict,
) -> dict[str, AgentQueryResponse]:
    """Despacha en paralelo a todos los agentes relevantes."""

    tasks: dict[str, asyncio.Task] = {}

    for topic_name, topic_data in expansion.topics.items():
        if topic_data.relevance < settings.RELEVANCE_THRESHOLD:
            continue
        if topic_name not in agent_registry:
            continue

        agent_request = AgentQueryRequest(
            original_query=expansion.original_query,
            questions=topic_data.questions,
            company_id=company_id,
            conversation_context=conversation_context,
        )

        tasks[topic_name] = asyncio.create_task(
            dispatch_to_agent(
                topic=topic_name,
                agent_fn=agent_registry[topic_name],
                request=agent_request,
            )
        )

    results: dict[str, AgentQueryResponse] = {}
    for topic_name, task in tasks.items():
        results[topic_name] = await task

    return results


# ── Etapa 3.5: Colaboración Inter-Agente ──────────────

async def resolve_inter_agent_dependencies(
    agent_responses: dict[str, AgentQueryResponse],
    company_id: str,
    original_query: str,
) -> dict[str, AgentQueryResponse]:
    """
    Revisa si algún agente necesita soporte de otro agente.
    Si needs_external_support == True, envía un support_request via el Message Broker.
    Luego enriquece la respuesta del agente solicitante con los artefactos recibidos.
    """
    enriched = dict(agent_responses)

    for topic, response in agent_responses.items():
        if not response.needs_external_support or not response.external_support_question:
            continue

        # Determinar el agente destino (el "otro" agente)
        other_agents = [t for t in agent_responses.keys() if t != topic]
        if not other_agents:
            continue

        target = other_agents[0]

        logger.info(
            "Inter-agent: %s solicita soporte de %s: '%s'",
            topic, target, response.external_support_question,
        )

        # Construir y enviar el support_request via el broker
        support_req = SupportRequest(
            source_agent=topic,
            target_agent=target,
            question=response.external_support_question,
            company_id=company_id,
            thread_id=response.thread_id,
            original_query=original_query,
            context_payload={
                "source_summary": response.summary,
                "source_answers_count": len(response.answers),
            },
        )

        support_resp = await message_broker.handle_support_request(support_req)

        if support_resp.resolved and support_resp.artifacts:
            # Agregar los artefactos como respuestas adicionales al agente original
            from schemas import AgentAnswer, DataPoint

            extra_answers = []
            for artifact in support_resp.artifacts:
                extra_answers.append(AgentAnswer(
                    question=f"[Inter-agent: {target}] {artifact.data.get('question', 'Soporte')}",
                    answer=artifact.data.get("answer", support_resp.summary),
                    confidence=artifact.confidence,
                    data_points=[
                        DataPoint(**dp) for dp in artifact.data.get("data_points", [])
                    ],
                ))

            # Enriquecer la respuesta original
            enriched_response = AgentQueryResponse(
                thread_id=response.thread_id,
                topic=response.topic,
                answers=response.answers + extra_answers,
                summary=f"{response.summary}\n\n[Soporte de {target}]: {support_resp.summary}",
                needs_external_support=False,
                external_support_question=None,
            )
            enriched[topic] = enriched_response

            # Guardar contexto en el store
            context_store.put(
                company_id,
                ContextEntry(
                    key=f"inter_agent_{topic}_{target}_{response.thread_id}",
                    value={
                        "source": topic,
                        "target": target,
                        "question": response.external_support_question,
                        "artifacts_count": len(support_resp.artifacts),
                        "summary": support_resp.summary,
                    },
                    source_agent=topic,
                    memory_priority="M_conv",
                ),
            )

            logger.info(
                "Inter-agent resolved: %s ← %s (%d artefactos)",
                topic, target, len(support_resp.artifacts),
            )
        else:
            logger.warning(
                "Inter-agent failed: %s → %s: %s",
                topic, target, support_resp.summary,
            )

    return enriched


# ── Etapa 4: Síntesis (MESH) ─────────────────────────

async def synthesize(
    original_query: str,
    agent_responses: dict[str, AgentQueryResponse],
) -> str:
    """Cruza respuestas de los agentes y genera una síntesis."""

    responses_text = ""
    for topic, resp in agent_responses.items():
        responses_text += f"\n### Agente: {topic}\n"
        responses_text += f"Resumen: {resp.summary}\n"
        for ans in resp.answers:
            responses_text += f"- **{ans.question}**: {ans.answer}\n"

    user_prompt = f"""Pregunta original del usuario: "{original_query}"

Respuestas de los agentes:
{responses_text}

Tu tarea:
1. Cruzá la información de todos los agentes.
2. Identificá conexiones entre los datos (ej: liquidez vs requisitos de crédito).
3. Generá una respuesta UNIFICADA en lenguaje natural, como Angela hablándole al usuario.
4. Sé concreta, con números y datos específicos.
5. Si hay acciones que el usuario puede tomar, mencionálas.

Respondé ÚNICAMENTE con un JSON válido:
{{
  "message": "respuesta natural para el usuario",
  "confidence": 0.0-1.0,
  "sources_used": ["finanzas", "economia"],
  "key_data_points": [
    {{"label": "nombre", "value": "valor", "source": "tópico"}}
  ],
  "recommendations": [
    {{"action": "acción", "impact": "impacto", "urgency": "alta|media|baja"}}
  ],
  "follow_up_suggestions": ["pregunta sugerida"]
}}
"""

    response = await client.messages.create(
        model=settings.ORCHESTRATOR_MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    return response.content[0].text.strip()


# ── Etapa 5: Evaluación de repreguntas ─────────────────

async def evaluate_follow_up(
    original_query: str,
    synthesis: str,
    iteration: int,
) -> FollowUpEvaluation:
    """Decide si se necesitan repreguntas adicionales."""

    if iteration >= settings.MAX_REASK_ITERATIONS:
        return FollowUpEvaluation(
            needs_follow_up=False,
            reason="Max iterations reached",
            iteration_count=iteration,
            stop_loss_check=StopLossCheck(
                maintains_original_objective=True,
                adding_value=False,
                max_iterations_reached=True,
            ),
        )

    user_prompt = f"""Pregunta original: "{original_query}"
Síntesis actual (iteración {iteration}):
{synthesis}

¿Se necesitan más preguntas para mejorar la respuesta? Respondé con JSON:
{{
  "needs_follow_up": true/false,
  "reason": "por qué",
  "follow_up_questions": {{
    "finanzas": ["pregunta si aplica"],
    "economia": ["pregunta si aplica"]
  }},
  "iteration_count": {iteration},
  "stop_loss_check": {{
    "maintains_original_objective": true/false,
    "adding_value": true/false,
    "max_iterations_reached": false
  }}
}}

Solo pedí repreguntas si la información cruzada revela un gap que CAMBIA la respuesta.
Si la respuesta cubre > 80% de lo necesario, NO repreguntés.
"""

    response = await client.messages.create(
        model=settings.ORCHESTRATOR_MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    data = json.loads(raw)
    return FollowUpEvaluation(**data)


# ── Pipeline completo ──────────────────────────────────

async def process_query(
    request: QueryRequest,
    agent_registry: dict,
) -> QueryResponse:
    """Pipeline completo del orquestador RAC."""

    start = time.time()
    total_sub_questions = 0
    iteration = 0
    agents_activated: set[str] = set()

    # Etapa 1+2: Expandir
    expansion = await expand_query(request)
    for topic_data in expansion.topics.values():
        total_sub_questions += len(topic_data.questions)

    synthesis_raw = None

    while iteration < settings.MAX_REASK_ITERATIONS:
        iteration += 1

        # Etapa 3: Despacho paralelo
        agent_responses = await dispatch_all(
            expansion=expansion,
            company_id=request.company_id,
            conversation_context=request.conversation_context,
            agent_registry=agent_registry,
        )
        agents_activated.update(agent_responses.keys())

        # Etapa 3.5: Resolver dependencias inter-agente
        agent_responses = await resolve_inter_agent_dependencies(
            agent_responses=agent_responses,
            company_id=request.company_id,
            original_query=expansion.original_query,
        )

        # Etapa 4: Síntesis
        synthesis_raw = await synthesize(
            original_query=expansion.original_query,
            agent_responses=agent_responses,
        )

        # Etapa 5: Evaluar repreguntas
        follow_up = await evaluate_follow_up(
            original_query=expansion.original_query,
            synthesis=synthesis_raw,
            iteration=iteration,
        )

        if not follow_up.needs_follow_up:
            break

        # Re-expandir con las nuevas preguntas
        for topic_name, questions in follow_up.follow_up_questions.items():
            if topic_name in expansion.topics:
                expansion.topics[topic_name].questions = questions
                total_sub_questions += len(questions)
            # Si el tópico no existía, lo ignoramos (solo finanzas y economia)

    # Etapa 6: Parsear síntesis a respuesta estructurada
    if synthesis_raw and synthesis_raw.startswith("```"):
        synthesis_raw = synthesis_raw.split("```")[1]
        if synthesis_raw.startswith("json"):
            synthesis_raw = synthesis_raw[4:]
    synthesis_raw = (synthesis_raw or "{}").strip()

    try:
        response_data = json.loads(synthesis_raw)
        payload = ResponsePayload(**response_data)
    except (json.JSONDecodeError, Exception):
        payload = ResponsePayload(
            message=synthesis_raw,
            confidence=0.5,
            sources_used=list(agents_activated),
        )

    # Obtener log de colaboración inter-agente
    collab_log = message_broker.get_collaboration_log(request.conversation_id or "default")
    inter_agent_calls = collab_log.total_inter_calls if collab_log else 0

    return QueryResponse(
        response=payload,
        metadata=OrchestratorMetadata(
            conversation_id=request.conversation_id or "",
            iterations=iteration,
            agents_activated=list(agents_activated),
            total_sub_questions=total_sub_questions,
            inter_agent_calls=inter_agent_calls,
        ),
    )
