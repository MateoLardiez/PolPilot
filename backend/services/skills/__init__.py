"""
services/skills — Skills del Super-Agente PolPilot v3.

Cada skill es una unidad de responsabilidad única registrada como tool
en el Agent SDK. El agente decide cuándo y cómo llamar cada skill.

Skills de datos (sin LLM):
  ingest_skill, client_db_skill, novelty_skill,
  finance_skill, economy_skill, research_skill

Skills de clasificación (helpers internos):
  topic_skill, intent_skill

Skills de sistema (agente puede llamarlas directamente):
  memory_management_skill  — memoria persistente en disco
  memory_write_skill       — escritura de interacción en shared_memory
  skill_creator_skill      — crea nuevas skills dinámicamente
  eval_skill               — evaluaciones de calidad de respuestas
  system_prompt_skill      — lee/actualiza system prompts del agente
"""

from . import (  # noqa: F401
    client_db_skill,
    economy_skill,
    eval_skill,
    finance_skill,
    ingest_skill,
    intent_skill,
    memory_management_skill,
    memory_write_skill,
    novelty_skill,
    research_skill,
    skill_creator_skill,
    system_prompt_skill,
    topic_skill,
)
