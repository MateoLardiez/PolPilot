"""
PolPilot Orchestrator API — Gateway Principal.

Endpoints:
  POST /query                          → Pipeline completo del orquestador
  POST /agents/finanzas/query          → Agente de Finanzas directo
  POST /agents/economia/query          → Agente de Economía directo
  POST /broker/support-request         → Colaboración inter-agente via Message Broker
  POST /broker/artifact                → Entrega directa de artefacto a un agente
  GET  /broker/log/{thread_id}         → Log de colaboración de un thread
  GET  /context/{company_id}           → Estado del Context Store de una empresa
  GET  /context/{company_id}/artifacts → Artefactos almacenados de una empresa
  GET  /health                         → Health check
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from schemas import (
    AgentQueryRequest,
    AgentQueryResponse,
    Artifact,
    CollaborationLog,
    ContextEntry,
    QueryRequest,
    QueryResponse,
    SupportRequest,
    SupportResponse,
)
from services.agent_economia import query_economia
from services.agent_finanzas import query_finanzas
from services.context_store import context_store
from services.message_broker import message_broker
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

# Registrar agentes en el Message Broker para colaboración inter-agente
message_broker.register_agent("finanzas", query_finanzas)
message_broker.register_agent("economia", query_economia)


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


# ── Endpoints: Colaboración Inter-Agente ───────────────

@app.post("/broker/support-request", response_model=SupportResponse)
async def broker_support_request(request: SupportRequest):
    """
    Protocolo de colaboración inter-agente via Message Broker.

    Un agente puede solicitar soporte a otro agente. El Gateway/Auditor:
    1. Valida presupuesto de inter-calls
    2. Detecta ciclos circulares (A→B→A)
    3. Obtiene contexto de verdad del Context Store
    4. Envía solicitud estructurada al agente destino
    5. Valida consistencia del artefacto de respuesta
    6. Devuelve evidencia al agente origen

    Request:
    ```json
    {
      "source_agent": "economia",
      "target_agent": "finanzas",
      "question": "¿Cuánta liquidez disponible tiene la empresa?",
      "company_id": "taller_frenos_001",
      "thread_id": "uuid del hilo actual",
      "original_query": "¿A qué crédito puedo aplicar?",
      "context_payload": {"credito_requiere": "$2M de liquidez"}
    }
    ```
    """
    if request.source_agent == request.target_agent:
        raise HTTPException(status_code=400, detail="source_agent y target_agent no pueden ser iguales")

    return await message_broker.handle_support_request(request)


@app.post("/broker/artifact")
async def broker_deliver_artifact(
    company_id: str,
    target_agent: str,
    artifact: Artifact,
):
    """
    Entrega directa de un artefacto estructurado a un agente.

    Tipos de artefacto: FACT, CLAIM, RECOMMENDATION, VALIDATION.
    El artefacto se almacena en el Context Store y se notifica al agente destino.
    """
    success = await message_broker.deliver_artifact(company_id, artifact, target_agent)
    if not success:
        raise HTTPException(status_code=500, detail="Error al entregar artefacto")
    return {"status": "delivered", "artifact_id": artifact.artifact_id}


@app.get("/broker/log/{thread_id}")
async def broker_collaboration_log(thread_id: str):
    """
    Obtiene el log completo de colaboración inter-agente de un thread.

    Incluye: support_requests enviados, support_responses recibidos,
    artefactos intercambiados, y total de inter-calls.
    """
    log = message_broker.get_collaboration_log(thread_id)
    if not log:
        raise HTTPException(status_code=404, detail=f"No hay log para thread '{thread_id}'")
    return log


@app.get("/broker/agents")
async def broker_registered_agents():
    """Lista los agentes registrados en el Message Broker."""
    return {"agents": message_broker.get_registered_agents()}


# ── Endpoints: Context Store ───────────────────────────

@app.get("/context/{company_id}")
async def get_company_context(company_id: str):
    """
    Estado completo del Context Store para una empresa.

    Retorna todas las entradas de contexto con su jerarquía de verdad:
    - M_int (máxima): Fuentes estructuradas (ERP, integraciones)
    - M_onb (media): Datos de onboarding / perfil PyME
    - M_conv (baja): Datos conversacionales

    Incluye la versión actual del contexto.
    """
    entries = context_store.get_all(company_id)
    return {
        "company_id": company_id,
        "context_ref": context_store.get_context_ref(company_id),
        "entries_count": len(entries),
        "entries": {k: v.model_dump() for k, v in entries.items()},
    }


@app.get("/context/{company_id}/artifacts")
async def get_company_artifacts(company_id: str, source_agent: str = None):
    """
    Artefactos almacenados para una empresa.

    Opcionalmente filtrables por agente de origen.
    """
    artifacts = context_store.get_artifacts(company_id, source_agent=source_agent)
    return {
        "company_id": company_id,
        "artifacts_count": len(artifacts),
        "artifacts": [a.model_dump() for a in artifacts],
    }


@app.post("/context/{company_id}")
async def put_context_entry(company_id: str, entry: ContextEntry):
    """
    Escribe o actualiza una entrada en el Context Store.

    Aplica jerarquía de verdad automáticamente: si ya existe una entrada
    con mayor prioridad, la nueva es rechazada.
    """
    accepted = context_store.put(company_id, entry)
    if not accepted:
        raise HTTPException(
            status_code=409,
            detail=f"Entry rejected: existing entry for key '{entry.key}' has higher memory priority",
        )
    return {"status": "accepted", "key": entry.key, "version": entry.version}


# ── Run ────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
