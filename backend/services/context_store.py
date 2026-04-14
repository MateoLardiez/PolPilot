"""
Context Store — Estado compartido entre agentes.

Implementa la "Capa de Memoria" del diagrama de arquitectura:
- Contexto Activo (RAM): estado en memoria de la sesión actual
- Resolución de conflictos por Jerarquía de Verdad (M_int > M_onb > M_conv)
- Versionado de contexto para trazabilidad
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Optional

from schemas import Artifact, ContextEntry

logger = logging.getLogger(__name__)


class ContextStore:
    """
    Almacén de contexto compartido entre agentes (in-memory para MVP).

    Estructura por company_id:
      context[company_id][key] -> ContextEntry
      artifacts[company_id]   -> list[Artifact]
    """

    # Prioridad de memoria: cuanto más bajo, más prioridad
    PRIORITY_RANK = {"M_int": 0, "M_onb": 1, "M_conv": 2}

    def __init__(self) -> None:
        self._context: dict[str, dict[str, ContextEntry]] = defaultdict(dict)
        self._artifacts: dict[str, list[Artifact]] = defaultdict(list)
        self._version_counter: dict[str, int] = defaultdict(int)

    # ── Lectura ────────────────────────────────────────

    def get(self, company_id: str, key: str) -> Optional[ContextEntry]:
        return self._context.get(company_id, {}).get(key)

    def get_all(self, company_id: str) -> dict[str, ContextEntry]:
        return dict(self._context.get(company_id, {}))

    def get_by_agent(self, company_id: str, source_agent: str) -> dict[str, ContextEntry]:
        return {
            k: v for k, v in self._context.get(company_id, {}).items()
            if v.source_agent == source_agent
        }

    def get_context_version(self, company_id: str) -> int:
        return self._version_counter.get(company_id, 0)

    def get_context_ref(self, company_id: str) -> str:
        """Devuelve un ref string tipo 'v1.2' para el protocolo inter-agente."""
        return f"v{self.get_context_version(company_id)}"

    # ── Escritura con jerarquía de verdad ──────────────

    def put(self, company_id: str, entry: ContextEntry) -> bool:
        """
        Escribe o actualiza una entrada en el contexto.
        Aplica jerarquía de verdad: si ya existe una entrada con mayor prioridad,
        la nueva es rechazada.

        Returns True si se escribió, False si fue rechazada.
        """
        existing = self._context.get(company_id, {}).get(entry.key)

        if existing is not None:
            existing_rank = self.PRIORITY_RANK.get(existing.memory_priority, 99)
            new_rank = self.PRIORITY_RANK.get(entry.memory_priority, 99)

            if new_rank > existing_rank:
                logger.info(
                    "Context conflict: key=%s rejected. Existing priority %s > new %s",
                    entry.key, existing.memory_priority, entry.memory_priority,
                )
                return False

            # Misma o mayor prioridad → actualizar con versión incrementada
            entry.version = existing.version + 1

        self._version_counter[company_id] += 1
        self._context[company_id][entry.key] = entry
        return True

    def put_batch(self, company_id: str, entries: list[ContextEntry]) -> list[bool]:
        return [self.put(company_id, e) for e in entries]

    # ── Artefactos ─────────────────────────────────────

    def store_artifact(self, company_id: str, artifact: Artifact) -> None:
        self._artifacts[company_id].append(artifact)

    def get_artifacts(
        self, company_id: str, source_agent: Optional[str] = None
    ) -> list[Artifact]:
        arts = self._artifacts.get(company_id, [])
        if source_agent:
            return [a for a in arts if a.source_agent == source_agent]
        return list(arts)

    def get_artifact_by_id(
        self, company_id: str, artifact_id: str
    ) -> Optional[Artifact]:
        for a in self._artifacts.get(company_id, []):
            if a.artifact_id == artifact_id:
                return a
        return None

    # ── Resolución de conflictos ───────────────────────

    def resolve_conflict(
        self,
        company_id: str,
        key: str,
        fact_a: dict,
        fact_b: dict,
        priority_a: str,
        priority_b: str,
    ) -> dict:
        """
        Resuelve un conflicto entre dos hechos usando la jerarquía de verdad.
        Retorna el hecho ganador y actualiza el contexto.
        """
        rank_a = self.PRIORITY_RANK.get(priority_a, 99)
        rank_b = self.PRIORITY_RANK.get(priority_b, 99)

        if rank_a <= rank_b:
            winner, loser_priority = fact_a, priority_b
        else:
            winner, loser_priority = fact_b, priority_a

        return {
            "winner": winner,
            "conflict_resolved": True,
            "invalidated_priority": loser_priority,
        }

    # ── Reset por sesión ───────────────────────────────

    def clear(self, company_id: str) -> None:
        self._context.pop(company_id, None)
        self._artifacts.pop(company_id, None)
        self._version_counter.pop(company_id, None)


# Singleton global
context_store = ContextStore()
