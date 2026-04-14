"""
services/skills — Skills del Super-Agente PolPilot.

Cada skill es una unidad de responsabilidad única dentro del pipeline.
Importar skills individualmente:
  from services.skills import finance_skill
  from services.skills.finance_skill import execute, FinanceData
"""

from . import (  # noqa: F401
    ingest_skill,
    client_db_skill,
    novelty_skill,
    topic_skill,
    intent_skill,
    finance_skill,
    economy_skill,
    research_skill,
    memory_write_skill,
)
