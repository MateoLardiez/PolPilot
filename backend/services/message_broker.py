"""
[DEPRECADO — v1 multiagente]

El Message Broker implementaba la colaboración inter-agente (A→B→A).
En v2 (super-agente), toda la orquestación ocurre en services/super_agent.py
y no hay inter-agent calls: el super-agente tiene acceso directo a todas las skills.

Motivo de eliminación:
  - La colaboración inter-agente era fuente de complejidad sin beneficio proporcional
  - El super-agente accede a todos los datos directamente vía skills
  - Elimina el riesgo de ciclos circulares y presupuesto de inter-calls

Este módulo se mantiene solo para referencia histórica.
NO se importa desde main.py en v2.

Ver: services/super_agent.py para el reemplazo.

---
Message Broker — Intermediario de mensajes entre agentes.

Implementa el protocolo de colaboración estructurada inter-agente:
1. Agente A envía support_request → Gateway/Auditor valida → Agente B recibe
2. Agente B responde con artifacts (FACT/CLAIM) → Gateway valida consistencia → Agente A recibe
3. Todo pasa por el broker, nunca punto a punto directo.

También maneja:
- Validación de presupuesto (max inter-calls por thread)
- Detección de ciclos circulares (A→B→A→B)
- Log de todas las interacciones para trazabilidad
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Callable, Awaitable, Optional

from schemas import (
    Artifact,
    ArtifactType,
    AgentQueryRequest,
    AgentQueryResponse,
    BrokerMessage,
    CollaborationLog,
    ContextEntry,
    SupportRequest,
    SupportResponse,
)
from services.context_store import context_store

logger = logging.getLogger(__name__)


class MessageBroker:
    """
    Gateway/Auditor + Message Broker del sistema inter-agente.

    Centraliza toda la comunicación entre agentes, valida requests,
    previene ciclos, y registra la colaboración.
    """

    MAX_INTER_CALLS_PER_THREAD = 4
    MAX_CHAIN_DEPTH = 3  # A→B→C máximo

    def __init__(self) -> None:
        # Registry de funciones de agentes
        self._agent_handlers: dict[str, Callable[..., Awaitable[AgentQueryResponse]]] = {}

        # Logs de colaboración por thread_id
        self._collaboration_logs: dict[str, CollaborationLog] = {}

        # Tracking de ciclos: thread_id → [(from, to), ...]
        self._call_chains: dict[str, list[tuple[str, str]]] = defaultdict(list)

        # Message queue
        self._messages: list[BrokerMessage] = []

    # ── Registro de agentes ────────────────────────────

    def register_agent(
        self, agent_name: str, handler: Callable[..., Awaitable[AgentQueryResponse]]
    ) -> None:
        self._agent_handlers[agent_name] = handler
        logger.info("Agent registered: %s", agent_name)

    def get_registered_agents(self) -> list[str]:
        return list(self._agent_handlers.keys())

    # ── Validaciones del Gateway/Auditor ───────────────

    def _validate_budget(self, thread_id: str) -> bool:
        """Valida que no se exceda el presupuesto de inter-calls."""
        log = self._collaboration_logs.get(thread_id)
        if log and log.total_inter_calls >= self.MAX_INTER_CALLS_PER_THREAD:
            logger.warning("Budget exceeded for thread %s", thread_id)
            return False
        return True

    def _detect_circular(self, thread_id: str, source: str, target: str) -> bool:
        """Detecta ciclos circulares: A→B→A."""
        chain = self._call_chains[thread_id]

        # Si ya hay una llamada target→source en la cadena, es un ciclo
        reverse_count = sum(1 for s, t in chain if s == target and t == source)
        if reverse_count >= 1:
            logger.warning("Circular dependency detected: %s↔%s in thread %s", source, target, thread_id)
            return True

        # Chain depth check
        if len(chain) >= self.MAX_CHAIN_DEPTH:
            logger.warning("Max chain depth reached for thread %s", thread_id)
            return True

        return False

    def _validate_target_exists(self, target_agent: str) -> bool:
        return target_agent in self._agent_handlers

    # ── Core: Procesar support_request ─────────────────

    async def handle_support_request(
        self, request: SupportRequest
    ) -> SupportResponse:
        """
        Protocolo completo de colaboración inter-agente:
        1. Agente origen envía support_request
        2. Gateway valida (budget, ciclo, target existe)
        3. Obtiene contexto de verdad del Context Store
        4. Envía solicitud estructurada al agente destino
        5. Agente destino responde con artifacts
        6. Gateway valida consistencia del artefacto
        7. Devuelve evidencia al agente origen
        """
        thread_id = request.thread_id or "default"

        # Inicializar log si es nuevo thread
        if thread_id not in self._collaboration_logs:
            self._collaboration_logs[thread_id] = CollaborationLog(thread_id=thread_id)
        log = self._collaboration_logs[thread_id]

        # 1. Registrar el request
        log.support_requests.append(request)

        # 2. Validar presupuesto
        if not self._validate_budget(thread_id):
            return SupportResponse(
                request_id=request.request_id,
                source_agent=request.source_agent,
                target_agent=request.target_agent,
                summary=f"Budget de inter-calls excedido ({self.MAX_INTER_CALLS_PER_THREAD} máx). "
                        f"Respondé con la información que tenés.",
                resolved=False,
            )

        # 3. Validar ciclos circulares
        if self._detect_circular(thread_id, request.source_agent, request.target_agent):
            return SupportResponse(
                request_id=request.request_id,
                source_agent=request.source_agent,
                target_agent=request.target_agent,
                summary="Dependencia circular detectada. Resolvé con la información disponible.",
                resolved=False,
            )

        # 4. Validar que el agente destino existe
        if not self._validate_target_exists(request.target_agent):
            return SupportResponse(
                request_id=request.request_id,
                source_agent=request.source_agent,
                target_agent=request.target_agent,
                summary=f"Agente '{request.target_agent}' no registrado. "
                        f"Agentes disponibles: {self.get_registered_agents()}",
                resolved=False,
            )

        # 5. Obtener contexto de verdad
        context_ref = context_store.get_context_ref(request.company_id)

        # 6. Registrar la cadena de llamadas
        self._call_chains[thread_id].append((request.source_agent, request.target_agent))

        # 7. Construir request estructurado para el agente destino
        agent_request = AgentQueryRequest(
            thread_id=thread_id,
            original_query=request.original_query or request.question,
            questions=[request.question],
            company_id=request.company_id,
            conversation_context=f"[SUPPORT_REQUEST from {request.source_agent}] "
                                 f"context_ref: {context_ref}. "
                                 f"Contexto adicional: {request.context_payload or {}}",
        )

        # 8. Llamar al agente destino
        handler = self._agent_handlers[request.target_agent]
        agent_response = await handler(agent_request)

        # 9. Convertir respuestas a artifacts
        artifacts: list[Artifact] = []
        for answer in agent_response.answers:
            artifact = Artifact(
                artifact_type=ArtifactType.FACT,
                source_agent=request.target_agent,
                data={
                    "question": answer.question,
                    "answer": answer.answer,
                    "data_points": [dp.model_dump() for dp in answer.data_points],
                },
                confidence=answer.confidence,
                context_ref=context_ref,
            )
            artifacts.append(artifact)
            # Guardar en el Context Store
            context_store.store_artifact(request.company_id, artifact)

        # 10. Registrar en el log
        log.total_inter_calls += 1
        log.artifacts_exchanged.extend(artifacts)

        # 11. Crear response
        support_response = SupportResponse(
            request_id=request.request_id,
            source_agent=request.source_agent,
            target_agent=request.target_agent,
            artifacts=artifacts,
            summary=agent_response.summary,
            resolved=True,
        )
        log.support_responses.append(support_response)

        # 12. Registrar mensaje en el broker
        self._messages.append(BrokerMessage(
            from_agent=request.target_agent,
            to_agent=request.source_agent,
            message_type="support_response",
            payload=support_response.model_dump(),
            status="delivered",
        ))

        logger.info(
            "Inter-agent: %s → %s resolved. Artifacts: %d. Thread: %s",
            request.source_agent, request.target_agent, len(artifacts), thread_id,
        )

        return support_response

    # ── Envío de artefactos directos ───────────────────

    async def deliver_artifact(
        self, company_id: str, artifact: Artifact, target_agent: str
    ) -> bool:
        """Entrega un artefacto directamente a un agente vía el broker."""
        context_store.store_artifact(company_id, artifact)

        self._messages.append(BrokerMessage(
            from_agent=artifact.source_agent,
            to_agent=target_agent,
            message_type="artifact_delivery",
            payload=artifact.model_dump(),
            status="delivered",
        ))
        return True

    # ── Notificaciones ─────────────────────────────────

    async def notify_dependency_resolved(
        self, thread_id: str, resolved_by: str, artifact_ids: list[str]
    ) -> None:
        """Notifica al Gateway que una dependencia fue resuelta."""
        self._messages.append(BrokerMessage(
            from_agent=resolved_by,
            to_agent="gateway",
            message_type="notification",
            payload={
                "event": "dependency_resolved",
                "thread_id": thread_id,
                "artifact_ids": artifact_ids,
            },
            status="delivered",
        ))

    # ── Queries de estado ──────────────────────────────

    def get_collaboration_log(self, thread_id: str) -> Optional[CollaborationLog]:
        return self._collaboration_logs.get(thread_id)

    def get_messages(
        self, agent_name: Optional[str] = None, status: Optional[str] = None
    ) -> list[BrokerMessage]:
        msgs = self._messages
        if agent_name:
            msgs = [m for m in msgs if m.to_agent == agent_name or m.from_agent == agent_name]
        if status:
            msgs = [m for m in msgs if m.status == status]
        return msgs

    def get_inter_call_count(self, thread_id: str) -> int:
        log = self._collaboration_logs.get(thread_id)
        return log.total_inter_calls if log else 0

    # ── Reset ──────────────────────────────────────────

    def clear_thread(self, thread_id: str) -> None:
        self._collaboration_logs.pop(thread_id, None)
        self._call_chains.pop(thread_id, None)


# Singleton global
message_broker = MessageBroker()
