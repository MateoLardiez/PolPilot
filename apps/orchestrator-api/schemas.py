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
