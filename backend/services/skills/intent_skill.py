"""
Intent Skill — Esquemas para la clasificación de intención.

La clasificación de intención se realiza en el MISMO call LLM que topic_skill
(dentro de super_agent.py). Este módulo provee los esquemas de datos y helpers
para interpretar y usar la intención clasificada.

Intenciones soportadas:
  - diagnostico      → el usuario quiere entender el estado actual
  - accion           → el usuario quiere hacer algo (solicitar crédito, etc.)
  - proyeccion       → el usuario quiere proyectar / simular escenarios
  - comparacion      → el usuario quiere comparar opciones
  - informacion      → el usuario pide información general
  - alerta           → el usuario reporta un problema / urgencia
"""

from __future__ import annotations

from dataclasses import dataclass

# Mapeo de intenciones a instrucciones de tono para el LLM de síntesis
INTENT_TONE_HINTS: dict[str, str] = {
    "diagnostico": (
        "Respondé con un diagnóstico claro y estructurado. "
        "Incluí números concretos y terminá con una evaluación general."
    ),
    "accion": (
        "Respondé con pasos concretos y accionables. "
        "Priorizá las recomendaciones por impacto."
    ),
    "proyeccion": (
        "Respondé con escenarios (optimista / realista / conservador). "
        "Usá datos actuales como base."
    ),
    "comparacion": (
        "Respondé con una comparación clara entre opciones. "
        "Usá formato tabla mental: pros/contras o métricas lado a lado."
    ),
    "informacion": (
        "Respondé de forma concisa y educativa. "
        "Explica el contexto antes de los datos específicos."
    ),
    "alerta": (
        "Respondé con urgencia apropiada. "
        "Identifica el riesgo y sugiere acciones inmediatas."
    ),
}

DEFAULT_TONE = (
    "Respondé de forma clara, concisa y con datos concretos."
)


@dataclass
class IntentResult:
    """Resultado de la clasificación de intención."""
    intent: str
    intent_description: str
    tone_hint: str  # instrucción de tono para el LLM de síntesis
    urgency: str  # "alta" | "media" | "baja"


def from_classification(intent: str, intent_description: str) -> IntentResult:
    """
    Construye un IntentResult a partir de los datos de clasificación del LLM.

    Args:
        intent: Intención clasificada por el LLM.
        intent_description: Descripción extendida de la intención.

    Returns:
        IntentResult con el tono apropiado para la síntesis.
    """
    # Normalizar: el LLM puede devolver variantes
    normalized = intent.lower().strip()
    # Mapear variantes comunes
    aliases = {
        "diagnóstico": "diagnostico",
        "acción": "accion",
        "proyección": "proyeccion",
        "comparación": "comparacion",
        "información": "informacion",
    }
    normalized = aliases.get(normalized, normalized)

    # Detectar urgencia por keywords en la descripción
    desc_lower = intent_description.lower()
    if any(w in desc_lower for w in ["urgente", "urgencia", "problema", "riesgo", "alerta"]):
        urgency = "alta"
    elif any(w in desc_lower for w in ["pronto", "esta semana", "próximo"]):
        urgency = "media"
    else:
        urgency = "baja"

    return IntentResult(
        intent=normalized,
        intent_description=intent_description,
        tone_hint=INTENT_TONE_HINTS.get(normalized, DEFAULT_TONE),
        urgency=urgency,
    )
