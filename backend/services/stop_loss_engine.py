"""
Stop-Loss Engine — Motor de Stop-Loss Cognitivo.

Implementa la fórmula del diagrama de arquitectura:

  StopLossScore = (R*0.3 + N*0.2 + G*0.25 + CR*0.15) - (Drift*0.3 + Redundancy*0.2 + Cost*0.2)

Donde:
  GANANCIA (positivo):
    R  = Relevancia    — Similitud con la query raíz
    N  = Novedad       — Info nueva vs iteración previa
    G  = Coverage_Gain — KPIs/preguntas resueltas
    CR = Contradiction_Resolution — Contradicciones resueltas

  RIESGO (negativo):
    Drift      = Deriva semántica respecto al objetivo original
    Redundancy = Información repetida entre iteraciones
    Cost       = Costo acumulado de tokens e inter-calls

Decisiones:
  Score >= 0.18 AND budget disponible → CONTINUE
  Score >= 0.18 AND sin budget       → STOP (Budget Cap)
  Score < 0.18                       → STOP (Marginal Utility)
"""

from __future__ import annotations

import json
import logging
from typing import Optional

import anthropic

from config import settings
from schemas import (
    AgentAnswer,
    AgentQueryResponse,
    StopLossDecision,
    StopLossEvaluation,
    StopLossMetrics,
    StopLossRisks,
)

logger = logging.getLogger(__name__)

client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

# ── Constantes ─────────────────────────────────────────

SCORE_THRESHOLD = 0.18

# Pesos de la fórmula (del diagrama)
W_RELEVANCE = 0.30
W_NOVELTY = 0.20
W_COVERAGE = 0.25
W_CONTRADICTION = 0.15

W_DRIFT = 0.30
W_REDUNDANCY = 0.20
W_COST = 0.20

# Budget: cada iteración consume ~1 unidad, máximo = MAX_REASK_ITERATIONS
BUDGET_PER_ITERATION = 1.0


class StopLossEngine:
    """
    Motor de Stop-Loss Cognitivo.

    Evalúa después de cada iteración del orquestador si vale la pena
    seguir expandiendo (CONTINUE) o si hay que detenerse (STOP).
    """

    def __init__(self, max_budget: Optional[float] = None) -> None:
        self._max_budget = max_budget or float(settings.MAX_REASK_ITERATIONS)
        self._history: list[StopLossEvaluation] = []

    # ── Cálculo de métricas ────────────────────────────

    def _calculate_metrics_heuristic(
        self,
        original_query: str,
        current_answers: dict[str, AgentQueryResponse],
        previous_answers: Optional[dict[str, AgentQueryResponse]],
        iteration: int,
    ) -> tuple[StopLossMetrics, StopLossRisks]:
        """
        Calcula métricas heurísticas sin llamada a LLM (rápido, sin costo).
        Usa señales estructurales de las respuestas de los agentes.
        """
        # ─ GANANCIA ─

        # Relevance: proporción de respuestas con confidence > 0.5
        all_answers: list[AgentAnswer] = []
        for resp in current_answers.values():
            all_answers.extend(resp.answers)

        if all_answers:
            high_conf = sum(1 for a in all_answers if a.confidence > 0.5)
            relevance = high_conf / len(all_answers)
        else:
            relevance = 0.0

        # Novelty: si hay respuestas previas, medimos cuánta info nueva hay
        if previous_answers:
            prev_answers_text = set()
            for resp in previous_answers.values():
                for a in resp.answers:
                    prev_answers_text.add(a.answer[:100])  # primeros 100 chars

            curr_answers_text = set()
            for a in all_answers:
                curr_answers_text.add(a.answer[:100])

            new_info = curr_answers_text - prev_answers_text
            novelty = len(new_info) / max(len(curr_answers_text), 1)
        else:
            novelty = 1.0  # primera iteración = todo es nuevo

        # Coverage: proporción de preguntas respondidas con data_points
        if all_answers:
            with_data = sum(1 for a in all_answers if a.data_points)
            coverage_gain = with_data / len(all_answers)
        else:
            coverage_gain = 0.0

        # Contradiction Resolution: señalado por needs_external_support
        support_resolved = sum(
            1 for resp in current_answers.values()
            if not resp.needs_external_support  # ya se resolvió o no necesitaba
        )
        contradiction_resolution = support_resolved / max(len(current_answers), 1)

        # ─ RIESGO ─

        # Drift: penalizar iteraciones tardías (más probable que se desvíe)
        drift_risk = min(iteration / settings.MAX_REASK_ITERATIONS, 1.0) * 0.5

        # Redundancy: si hay respuestas previas, medir overlap
        if previous_answers:
            prev_summaries = {t: r.summary for t, r in previous_answers.items()}
            curr_summaries = {t: r.summary for t, r in current_answers.items()}
            overlap = sum(
                1 for t in curr_summaries
                if t in prev_summaries and curr_summaries[t][:50] == prev_summaries[t][:50]
            )
            redundancy = overlap / max(len(curr_summaries), 1)
        else:
            redundancy = 0.0

        # Cost: basado en iteración + inter-calls
        cost = iteration / settings.MAX_REASK_ITERATIONS

        metrics = StopLossMetrics(
            relevance=round(relevance, 3),
            novelty=round(novelty, 3),
            coverage_gain=round(coverage_gain, 3),
            contradiction_resolution=round(contradiction_resolution, 3),
        )
        risks = StopLossRisks(
            drift_risk=round(drift_risk, 3),
            redundancy=round(redundancy, 3),
            cost=round(cost, 3),
        )
        return metrics, risks

    async def _calculate_metrics_llm(
        self,
        original_query: str,
        current_synthesis: str,
        previous_synthesis: Optional[str],
        iteration: int,
    ) -> tuple[StopLossMetrics, StopLossRisks]:
        """
        Calcula métricas usando LLM para análisis semántico profundo.
        Más preciso pero con costo de tokens.
        """
        prev_text = previous_synthesis or "No hay síntesis previa (primera iteración)."

        prompt = f"""Sos el motor de Stop-Loss de PolPilot. Evaluá si vale la pena seguir iterando.

PREGUNTA ORIGINAL DEL USUARIO:
"{original_query}"

SÍNTESIS ACTUAL (iteración {iteration}):
{current_synthesis}

SÍNTESIS PREVIA:
{prev_text}

Evaluá estas métricas de 0.0 a 1.0 y respondé SOLO con JSON:
{{
  "metrics": {{
    "relevance": 0.0-1.0,
    "novelty": 0.0-1.0,
    "coverage_gain": 0.0-1.0,
    "contradiction_resolution": 0.0-1.0
  }},
  "risks": {{
    "drift_risk": 0.0-1.0,
    "redundancy": 0.0-1.0,
    "cost": 0.0-1.0
  }}
}}

CRITERIOS:
- relevance: ¿La respuesta actual es relevante para la pregunta original?
- novelty: ¿Esta iteración trajo información NUEVA vs la anterior?
- coverage_gain: ¿Se resolvieron KPIs/datos que faltaban?
- contradiction_resolution: ¿Se resolvieron contradicciones entre agentes?
- drift_risk: ¿La respuesta se desvió del objetivo original?
- redundancy: ¿Se repitió información que ya teníamos?
- cost: Considerá iteración {iteration} de {settings.MAX_REASK_ITERATIONS} máximas.
"""

        try:
            response = await client.messages.create(
                model="claude-haiku-4-20250414",  # modelo ligero para stop-loss
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )

            raw = response.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()

            data = json.loads(raw)
            metrics = StopLossMetrics(**data.get("metrics", {}))
            risks = StopLossRisks(**data.get("risks", {}))
            return metrics, risks

        except Exception as e:
            logger.warning("LLM stop-loss failed, falling back to heuristic: %s", e)
            # Fallback: generar métricas vacías (el heurístico ya se usó o se usará)
            return StopLossMetrics(), StopLossRisks()

    # ── Fórmula principal ──────────────────────────────

    @staticmethod
    def compute_score(metrics: StopLossMetrics, risks: StopLossRisks) -> float:
        """
        Aplica la fórmula:
        Score = (R*0.3 + N*0.2 + G*0.25 + CR*0.15) - (Drift*0.3 + Redundancy*0.2 + Cost*0.2)
        """
        utility = (
            metrics.relevance * W_RELEVANCE
            + metrics.novelty * W_NOVELTY
            + metrics.coverage_gain * W_COVERAGE
            + metrics.contradiction_resolution * W_CONTRADICTION
        )
        risk = (
            risks.drift_risk * W_DRIFT
            + risks.redundancy * W_REDUNDANCY
            + risks.cost * W_COST
        )
        return round(utility - risk, 4)

    # ── Evaluación completa ────────────────────────────

    async def evaluate(
        self,
        original_query: str,
        current_answers: dict[str, AgentQueryResponse],
        current_synthesis: str,
        previous_answers: Optional[dict[str, AgentQueryResponse]],
        previous_synthesis: Optional[str],
        iteration: int,
        inter_agent_calls: int = 0,
        use_llm: bool = False,
    ) -> StopLossEvaluation:
        """
        Evaluación completa del Stop-Loss Cognitivo.

        Args:
            use_llm: Si True, usa LLM para métricas semánticas (más preciso, más costo).
                     Si False, usa heurísticas (rápido, sin costo adicional).
        """

        # 1. Calcular métricas
        if use_llm and current_synthesis:
            metrics, risks = await self._calculate_metrics_llm(
                original_query, current_synthesis, previous_synthesis, iteration,
            )
        else:
            metrics, risks = self._calculate_metrics_heuristic(
                original_query, current_answers, previous_answers, iteration,
            )

        # Ajustar cost con inter-agent calls
        total_cost_factor = (iteration + inter_agent_calls * 0.5) / (self._max_budget + 2)
        risks.cost = round(min(total_cost_factor, 1.0), 3)

        # 2. Calcular score
        score = self.compute_score(metrics, risks)

        # 3. Calcular budget restante
        budget_used = iteration * BUDGET_PER_ITERATION
        budget_remaining = max(0.0, (self._max_budget - budget_used) / self._max_budget)

        # 4. Decisión
        if iteration >= settings.MAX_REASK_ITERATIONS:
            decision = StopLossDecision.STOP_MAX_ITER
            reason = f"Máximo de iteraciones alcanzado ({settings.MAX_REASK_ITERATIONS})"
        elif score < SCORE_THRESHOLD:
            decision = StopLossDecision.STOP_MARGINAL
            reason = f"Score {score:.3f} < threshold {SCORE_THRESHOLD}. Utilidad marginal insuficiente."
        elif budget_remaining <= 0:
            decision = StopLossDecision.STOP_BUDGET
            reason = f"Presupuesto agotado (iteración {iteration}/{int(self._max_budget)})"
        else:
            decision = StopLossDecision.CONTINUE
            reason = f"Score {score:.3f} >= {SCORE_THRESHOLD} y budget disponible ({budget_remaining:.0%})"

        # 5. Sugerir nuevos sub-tópicos si CONTINUE
        suggested = []
        if decision == StopLossDecision.CONTINUE:
            # Sugerir tópicos donde la cobertura es baja
            for topic, resp in current_answers.items():
                low_conf_questions = [
                    a.question for a in resp.answers if a.confidence < 0.5
                ]
                if low_conf_questions:
                    suggested.extend(low_conf_questions[:2])

        evaluation = StopLossEvaluation(
            iteration=iteration,
            metrics=metrics,
            risks=risks,
            score=score,
            threshold=SCORE_THRESHOLD,
            budget_remaining=round(budget_remaining, 3),
            decision=decision,
            reason=reason,
            suggested_new_topics=suggested,
        )

        self._history.append(evaluation)

        logger.info(
            "Stop-Loss iter=%d score=%.3f decision=%s reason='%s'",
            iteration, score, decision.value, reason,
        )

        return evaluation

    # ── Historial ──────────────────────────────────────

    def get_history(self) -> list[StopLossEvaluation]:
        return list(self._history)

    def get_last_evaluation(self) -> Optional[StopLossEvaluation]:
        return self._history[-1] if self._history else None

    def reset(self) -> None:
        self._history.clear()


# Factory: crear una instancia por query (no singleton)
def create_stop_loss_engine() -> StopLossEngine:
    return StopLossEngine(max_budget=float(settings.MAX_REASK_ITERATIONS))
