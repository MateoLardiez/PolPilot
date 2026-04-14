"""
Topic Skill — Esquemas y helpers para la clasificación de tópico.

La clasificación efectiva (llamada LLM) ocurre en super_agent.py.
Este módulo define:
  - TopicClassification: dataclass con el resultado de la clasificación
  - parse_llm_response: parsea la respuesta JSON del LLM

Tópicos soportados:
  - finanzas    → datos internos del negocio (caja, clientes, stock)
  - economia    → macro, créditos, regulaciones, AFIP/BCRA
  - investigacion → datos en tiempo real (dólar, tasas live)
  - mixed       → combinación de dos o más tópicos
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

RELEVANCE_THRESHOLD = 0.20


@dataclass
class TopicDetail:
    """Detalle de un tópico dentro de la clasificación."""
    relevance: float  # 0.0–1.0
    sub_questions: list[str] = field(default_factory=list)

    @property
    def is_relevant(self) -> bool:
        return self.relevance >= RELEVANCE_THRESHOLD


@dataclass
class TopicClassification:
    """Resultado completo de la clasificación de tópico e intención."""
    primary_topic: str  # "finanzas" | "economia" | "investigacion" | "mixed"
    intent: str
    intent_description: str
    complexity: str  # "simple" | "medium" | "complex"
    requires_live_data: bool
    finanzas: TopicDetail = field(default_factory=lambda: TopicDetail(relevance=0.0))
    economia: TopicDetail = field(default_factory=lambda: TopicDetail(relevance=0.0))
    investigacion: TopicDetail = field(default_factory=lambda: TopicDetail(relevance=0.0))

    @property
    def active_topics(self) -> list[str]:
        """Tópicos con relevance >= threshold."""
        active = []
        if self.finanzas.is_relevant:
            active.append("finanzas")
        if self.economia.is_relevant:
            active.append("economia")
        if self.investigacion.is_relevant:
            active.append("investigacion")
        return active

    @property
    def all_sub_questions(self) -> list[str]:
        """Todas las sub-preguntas de todos los tópicos activos."""
        qs = []
        qs.extend(self.finanzas.sub_questions)
        qs.extend(self.economia.sub_questions)
        qs.extend(self.investigacion.sub_questions)
        return qs


def parse_llm_response(raw_json: str) -> TopicClassification:
    """
    Parsea la respuesta JSON del LLM para construir un TopicClassification.

    El LLM debe devolver:
    {
      "primary_topic": "finanzas|economia|investigacion|mixed",
      "intent": "descripción breve",
      "intent_description": "descripción extendida",
      "complexity": "simple|medium|complex",
      "requires_live_data": true|false,
      "topics": {
        "finanzas": {"relevance": 0.0-1.0, "sub_questions": [...]},
        "economia": {"relevance": 0.0-1.0, "sub_questions": [...]},
        "investigacion": {"relevance": 0.0-1.0, "sub_questions": [...]}
      }
    }
    """
    # Strip markdown code blocks if present
    raw = raw_json.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    data = json.loads(raw)
    topics_raw = data.get("topics", {})

    def _parse_topic(key: str) -> TopicDetail:
        t = topics_raw.get(key, {})
        return TopicDetail(
            relevance=float(t.get("relevance", 0.0)),
            sub_questions=list(t.get("sub_questions", [])),
        )

    classification = TopicClassification(
        primary_topic=data.get("primary_topic", "mixed"),
        intent=data.get("intent", "consulta general"),
        intent_description=data.get("intent_description", ""),
        complexity=data.get("complexity", "simple"),
        requires_live_data=bool(data.get("requires_live_data", False)),
        finanzas=_parse_topic("finanzas"),
        economia=_parse_topic("economia"),
        investigacion=_parse_topic("investigacion"),
    )

    return classification


def build_classification_prompt(
    user_message: str,
    memory_context: str,
    company_profile_summary: str,
    detected_keywords: list[str],
    max_questions_per_topic: int = 3,
) -> str:
    """Construye el prompt de clasificación que usará el super-agente."""
    keywords_str = ", ".join(detected_keywords) if detected_keywords else "ninguna"

    return f"""Analizá esta consulta de una empresa PyME argentina y clasificá el tópico e intención.

CONSULTA DEL USUARIO:
"{user_message}"

KEYWORDS DETECTADAS: {keywords_str}

CONTEXTO DE CONVERSACIÓN PREVIA:
{memory_context or "Sin conversación previa."}

PERFIL DE EMPRESA:
{company_profile_summary or "Sin datos de perfil disponibles."}

Respondé ÚNICAMENTE con un JSON válido (sin texto adicional):
{{
  "primary_topic": "finanzas|economia|investigacion|mixed",
  "intent": "descripción breve de la intención (máx 10 palabras)",
  "intent_description": "descripción extendida de lo que el usuario necesita",
  "complexity": "simple|medium|complex",
  "requires_live_data": true|false,
  "topics": {{
    "finanzas": {{
      "relevance": 0.0-1.0,
      "sub_questions": ["pregunta específica sobre datos internos del negocio"]
    }},
    "economia": {{
      "relevance": 0.0-1.0,
      "sub_questions": ["pregunta sobre créditos, macro, regulaciones"]
    }},
    "investigacion": {{
      "relevance": 0.0-1.0,
      "sub_questions": ["pregunta que requiere dato fresco/tiempo real"]
    }}
  }}
}}

REGLAS:
- "finanzas" = datos internos (caja, clientes, proveedores, stock, empleados, flujo)
- "economia" = análisis de créditos disponibles, macro contextual, AFIP/BCRA/regulaciones
- "investigacion" = dólar hoy, tasas BCRA live, cotización actual, dato fresco
- Si un tópico NO es relevante: relevance < 0.2 y sub_questions vacío
- Máximo {max_questions_per_topic} sub_questions por tópico
- requires_live_data = true SOLO si la respuesta requiere datos de mercado en tiempo real
"""
