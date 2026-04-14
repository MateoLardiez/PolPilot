"""
Eval Skill — Evaluaciones de calidad de respuestas del agente.

Permite correr casos de prueba para verificar que Angela responde
correctamente antes de un demo o deploy. MVP: devuelve los casos
de prueba listos para ejecutar contra POST /query.

Casos predefinidos cubren: finanzas, economía macro y datos en tiempo real.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ── Casos de prueba predefinidos ───────────────────────

DEFAULT_TEST_CASES = [
    {
        "id": "tc_001",
        "query": "¿Cuál es el flujo de caja este mes?",
        "expected_topics": ["finanzas"],
        "expected_keywords": ["flujo", "caja", "$"],
        "min_confidence": 0.5,
        "description": "Consulta básica de liquidez",
    },
    {
        "id": "tc_002",
        "query": "¿Cómo está el dólar blue hoy?",
        "expected_topics": ["investigacion"],
        "expected_keywords": ["dólar", "blue"],
        "min_confidence": 0.7,
        "description": "Dato en tiempo real — DolarAPI",
    },
    {
        "id": "tc_003",
        "query": "¿Qué créditos PyME puedo tomar con la inflación actual?",
        "expected_topics": ["economia", "investigacion"],
        "expected_keywords": ["crédito", "tasa", "banco"],
        "min_confidence": 0.5,
        "description": "Créditos + macro BCRA",
    },
    {
        "id": "tc_004",
        "query": "Dame un diagnóstico completo de la empresa",
        "expected_topics": ["finanzas"],
        "expected_keywords": ["diagnóstico", "empresa"],
        "min_confidence": 0.4,
        "description": "Diagnóstico integral — todos los skills",
    },
    {
        "id": "tc_005",
        "query": "¿Cuánto debo a proveedores?",
        "expected_topics": ["finanzas"],
        "expected_keywords": ["proveedores", "$"],
        "min_confidence": 0.5,
        "description": "Consulta de cuentas por pagar",
    },
]

# Criterios de evaluación
EVALUATION_CRITERIA = {
    "keyword_coverage": (
        "% de keywords esperadas presentes en la respuesta "
        "(mínimo 60% para pasar)"
    ),
    "confidence_threshold": (
        "La respuesta debe alcanzar el min_confidence definido por caso"
    ),
    "response_format": (
        "La respuesta debe ser JSON válido con campos: "
        "message, confidence, sources_used"
    ),
    "no_invented_data": (
        "Si no hay datos reales, confidence debe ser < 0.6 "
        "y el mensaje debe indicarlo"
    ),
}


def _evaluate_response(response: dict, test_case: dict) -> dict:
    """
    Evalúa una respuesta del agente contra un caso de prueba.
    Usado internamente o desde tests de integración.
    """
    message = response.get("message", "").lower()
    confidence = response.get("confidence", 0.0)
    sources = response.get("sources_used", [])

    # Keyword coverage
    expected_kw = test_case.get("expected_keywords", [])
    missing_kw = [kw for kw in expected_kw if kw.lower() not in message]
    kw_score = 1.0 - (len(missing_kw) / len(expected_kw)) if expected_kw else 1.0

    # Confidence check
    min_conf = test_case.get("min_confidence", 0.4)
    confidence_ok = confidence >= min_conf

    # Topic coverage
    expected_topics = test_case.get("expected_topics", [])
    topics_found = [t for t in expected_topics if t in sources]
    topic_score = len(topics_found) / len(expected_topics) if expected_topics else 1.0

    passed = kw_score >= 0.6 and confidence_ok

    return {
        "test_id": test_case.get("id"),
        "passed": passed,
        "keyword_score": round(kw_score, 2),
        "confidence_ok": confidence_ok,
        "actual_confidence": confidence,
        "topic_score": round(topic_score, 2),
        "missing_keywords": missing_kw,
        "topics_found": topics_found,
    }


def execute(
    test_cases: Optional[list[dict]] = None,
    company_id: str = "emp_001",
    evaluate_response: Optional[dict] = None,
    evaluate_against_case_id: Optional[str] = None,
) -> dict:
    """
    Ejecuta o prepara evaluaciones de calidad.

    Modos:
      1. Sin parámetros extra → devuelve los casos de prueba listos para correr
      2. Con evaluate_response + evaluate_against_case_id → evalúa una respuesta

    Args:
        test_cases: Casos custom; si None usa DEFAULT_TEST_CASES
        company_id: Empresa a evaluar
        evaluate_response: dict de ResponsePayload para evaluar inline
        evaluate_against_case_id: ID del test case contra el que evaluar

    Returns:
        dict con casos de prueba o resultado de evaluación
    """
    cases = test_cases or DEFAULT_TEST_CASES

    # Modo evaluación inline
    if evaluate_response and evaluate_against_case_id:
        target_case = next(
            (c for c in cases if c.get("id") == evaluate_against_case_id), None
        )
        if not target_case:
            return {"error": f"Test case '{evaluate_against_case_id}' no encontrado"}
        result = _evaluate_response(evaluate_response, target_case)
        return {"mode": "inline_eval", "result": result}

    # Modo: devolver casos listos para ejecutar
    return {
        "status": "ready",
        "company_id": company_id,
        "total_cases": len(cases),
        "test_cases": cases,
        "evaluation_criteria": EVALUATION_CRITERIA,
        "instructions": (
            f"Enviar cada query a POST /query con company_id='{company_id}' "
            "y verificar keywords + confidence mínimo. "
            "Usar evaluate_response + evaluate_against_case_id para eval inline."
        ),
    }
