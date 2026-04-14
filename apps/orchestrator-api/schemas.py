"""Pydantic schemas para el Orchestrator API."""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────

class QueryType(str, Enum):
    new_query = "new_query"
    continuity = "continuity"
    simple = "simple"


class Complexity(str, Enum):
    simple = "simple"
    medium = "medium"
    complex = "complex"


class Urgency(str, Enum):
    alta = "alta"
    media = "media"
    baja = "baja"


class TopicName(str, Enum):
    finanzas = "finanzas"
    economia = "economia"


# ── Request / Response del Gateway ─────────────────────

class QueryRequest(BaseModel):
    """Request que llega desde el frontend / WhatsApp."""
    company_id: str
    user_message: str
    conversation_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    conversation_context: Optional[str] = None


class DataPoint(BaseModel):
    label: str
    value: str
    source: str


class Recommendation(BaseModel):
    action: str
    impact: str
    urgency: Urgency


class ResponsePayload(BaseModel):
    message: str
    confidence: float = Field(ge=0, le=1)
    sources_used: list[str]
    key_data_points: list[DataPoint] = []
    recommendations: list[Recommendation] = []
    follow_up_suggestions: list[str] = []


class OrchestratorMetadata(BaseModel):
    conversation_id: str
    iterations: int
    agents_activated: list[str]
    total_sub_questions: int
    inter_agent_calls: int = 0


class QueryResponse(BaseModel):
    """Response final que devuelve el Gateway al frontend."""
    response: ResponsePayload
    metadata: OrchestratorMetadata


# ── Schemas internos del Orquestador ──────────────────

class TopicExpansion(BaseModel):
    relevance: float = Field(ge=0, le=1)
    questions: list[str]


class QuestionExpansion(BaseModel):
    original_query: str
    intent: str
    complexity: Complexity
    topics: dict[str, TopicExpansion]


# ── Request / Response de los Agentes ─────────────────

class AgentQueryRequest(BaseModel):
    """Lo que el orquestador envía a cada agente."""
    thread_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    original_query: str
    questions: list[str]
    company_id: str
    conversation_context: Optional[str] = None


class AgentAnswer(BaseModel):
    question: str
    answer: str
    confidence: float = Field(ge=0, le=1)
    data_points: list[DataPoint] = []


class AgentQueryResponse(BaseModel):
    """Lo que cada agente devuelve al orquestador."""
    thread_id: str
    topic: str
    answers: list[AgentAnswer]
    summary: str
    needs_external_support: bool = False
    external_support_question: Optional[str] = None


# ── Stop-Loss / Repreguntas ───────────────────────────

class StopLossCheck(BaseModel):
    maintains_original_objective: bool
    adding_value: bool
    max_iterations_reached: bool


class FollowUpEvaluation(BaseModel):
    needs_follow_up: bool
    reason: Optional[str] = None
    follow_up_questions: dict[str, list[str]] = {}
    iteration_count: int
    stop_loss_check: StopLossCheck


# ── Colaboración Inter-Agente ─────────────────────────

class ArtifactType(str, Enum):
    FACT = "FACT"
    CLAIM = "CLAIM"
    RECOMMENDATION = "RECOMMENDATION"
    VALIDATION = "VALIDATION"


class ArtifactStatus(str, Enum):
    pending = "pending"
    resolved = "resolved"
    rejected = "rejected"


class Artifact(BaseModel):
    """Artefacto estructurado que los agentes producen e intercambian."""
    artifact_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    artifact_type: ArtifactType
    source_agent: str
    data: dict
    confidence: float = Field(ge=0, le=1)
    context_ref: Optional[str] = None
    created_at: Optional[str] = Field(default_factory=lambda: __import__("datetime").datetime.now().isoformat())


class SupportRequest(BaseModel):
    """Solicitud de un agente a otro vía el Gateway/Auditor."""
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_agent: str
    target_agent: str
    question: str
    context_payload: Optional[dict] = None
    company_id: str
    thread_id: Optional[str] = None
    original_query: Optional[str] = None


class SupportResponse(BaseModel):
    """Respuesta a un support_request."""
    request_id: str
    source_agent: str
    target_agent: str
    artifacts: list[Artifact] = []
    summary: str
    resolved: bool = True


class BrokerMessage(BaseModel):
    """Mensaje interno del Message Broker."""
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    from_agent: str
    to_agent: str
    message_type: str  # "support_request" | "support_response" | "artifact_delivery" | "notification"
    payload: dict
    status: str = "pending"  # "pending" | "delivered" | "processed"
    created_at: Optional[str] = Field(default_factory=lambda: __import__("datetime").datetime.now().isoformat())


class ContextEntry(BaseModel):
    """Entrada en el Context Store (estado compartido)."""
    key: str
    value: dict
    source_agent: str
    version: int = 1
    memory_priority: str = "M_conv"  # "M_int" (máxima) | "M_onb" (media) | "M_conv" (baja)
    updated_at: Optional[str] = Field(default_factory=lambda: __import__("datetime").datetime.now().isoformat())


class CollaborationLog(BaseModel):
    """Log de una interacción inter-agente completa."""
    thread_id: str
    support_requests: list[SupportRequest] = []
    support_responses: list[SupportResponse] = []
    artifacts_exchanged: list[Artifact] = []
    total_inter_calls: int = 0
