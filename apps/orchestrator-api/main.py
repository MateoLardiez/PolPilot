"""
PolPilot Orchestrator API — Gateway Principal.

Endpoints:
  POST /query                    → Pipeline completo del orquestador
  POST /agents/finanzas/query    → Agente de Finanzas directo
  POST /agents/economia/query    → Agente de Economía directo
  GET  /health                   → Health check
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from schemas import (
    AgentQueryRequest,
    AgentQueryResponse,
    QueryRequest,
    QueryResponse,
)
from services.agent_economia import query_economia
from services.agent_finanzas import query_finanzas
from services.orchestrator import process_query

# ── App ────────────────────────────────────────────────

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restringir en producción
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Registry de agentes (para el orquestador) ─────────

AGENT_REGISTRY = {
    "finanzas": query_finanzas,
    "economia": query_economia,
}


# ── Endpoints ──────────────────────────────────────────

@app.get("/health")
async def health():
    """Health check."""
    return {"status": "ok", "version": settings.VERSION}


@app.post("/query", response_model=QueryResponse)
async def orchestrator_query(request: QueryRequest):
    """
    Pipeline completo del orquestador RAC.

    Recibe una pregunta del usuario, la expande en sub-preguntas por tópico,
    despacha a los agentes en paralelo, sintetiza las respuestas, evalúa
    repreguntas y devuelve la respuesta final.

    Request:
    ```json
    {
      "company_id": "taller_frenos_001",
      "user_message": "¿A qué crédito puedo aplicar?",
      "conversation_id": "uuid (opcional)",
      "conversation_context": "resumen previo (opcional)"
    }
    ```
    """
    if not request.user_message.strip():
        raise HTTPException(status_code=400, detail="user_message is required")

    result = await process_query(request, AGENT_REGISTRY)
    return result


@app.post("/agents/finanzas/query", response_model=AgentQueryResponse)
async def finanzas_query(request: AgentQueryRequest):
    """
    Endpoint directo al Agente de Finanzas.

    Permite que el orquestador (o cualquier servicio) envíe preguntas
    específicas sobre la situación financiera interna de una empresa.

    Request:
    ```json
    {
      "thread_id": "uuid",
      "original_query": "pregunta original del usuario",
      "questions": [
        "¿Cuál es el flujo de caja neto?",
        "¿Hay deudas vigentes?"
      ],
      "company_id": "taller_frenos_001",
      "conversation_context": "opcional"
    }
    ```
    """
    return await query_finanzas(request)


@app.post("/agents/economia/query", response_model=AgentQueryResponse)
async def economia_query(request: AgentQueryRequest):
    """
    Endpoint directo al Agente de Economía.

    Permite que el orquestador (o cualquier servicio) envíe preguntas
    específicas sobre contexto macroeconómico, créditos, tasas y regulaciones.

    Request:
    ```json
    {
      "thread_id": "uuid",
      "original_query": "pregunta original del usuario",
      "questions": [
        "¿Qué líneas de crédito PyME hay disponibles?",
        "¿Cuáles son las tasas BCRA actuales?"
      ],
      "company_id": "taller_frenos_001",
      "conversation_context": "opcional"
    }
    ```
    """
    return await query_economia(request)


# ── Run ────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
