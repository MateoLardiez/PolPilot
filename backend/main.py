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

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, File, Form, UploadFile
from typing import Optional
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
from services.data_bridge import ensure_initialized, run_seed, run_external_sync, get_live_dollar_rates, ingest_document


# ── Lifespan ───────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    status = ensure_initialized(settings.DEFAULT_EMPRESA_ID)
    if status["has_data"]:
        print(f"[PolPilot] DB lista para '{settings.DEFAULT_EMPRESA_ID}' ✓")
    elif status["polpilot_available"]:
        print(f"[PolPilot] DB vacía. Ejecutar: POST /db/init/{settings.DEFAULT_EMPRESA_ID}")
    else:
        print("[PolPilot] polpilot.backend no disponible — usando mock data")
    yield


# ── App ────────────────────────────────────────────────

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    docs_url="/docs",
    openapi_url="/openapi.json",
    lifespan=lifespan,
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


# ── Endpoints: DB Management ───────────────────────────

@app.get("/db/status/{empresa_id}")
async def db_status(empresa_id: str):
    """
    Verifica el estado de las bases de datos de una empresa.
    Retorna si la DB tiene datos y si polpilot.backend está disponible.
    """
    return ensure_initialized(empresa_id)


@app.post("/db/init/{empresa_id}")
async def db_init(empresa_id: str):
    """
    Inicializa y seedea las 3 bases de datos de una empresa.

    Crea:
      - internal.sqlite (perfil, financials, indicadores, clientes, proveedores, productos)
      - external.sqlite (créditos, macro, regulaciones, perfil BCRA, señales sector)
      - memory.sqlite   (conversaciones — vacío listo para usar)
      - vectors/        (ChromaDB con embeddings iniciales)

    Idempotente: si los datos ya existen se vuelven a cargar.
    """
    result = run_seed(empresa_id)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Seed falló"))
    return result


@app.post("/db/sync/{empresa_id}")
async def db_sync(empresa_id: str, mode: str = "all"):
    """
    Sincroniza datos externos en tiempo real desde las APIs del BCRA y DolarAPI.

    Query param `mode`:
      - 'all'     → macro + perfil crediticio BCRA + catálogo de créditos bancarios
      - 'macro'   → solo tasas, inflación, tipos de cambio
      - 'credits' → solo catálogo de préstamos BCRA Transparencia
      - 'profile' → solo perfil crediticio BCRA Central de Deudores

    Requiere que la DB esté inicializada (POST /db/init primero).
    """
    result = run_external_sync(empresa_id, mode=mode)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Sync falló"))
    return result


@app.post("/ingest")
async def ingest(
    company_id: str = Form(default="emp_001"),
    title: str = Form(default="documento"),
    text: Optional[str] = Form(default=None),
    collection: str = Form(default="internal_docs"),
    file: Optional[UploadFile] = File(default=None),
):
    """
    Ingresa texto o archivo al vector store de la empresa (ChromaDB).

    Formatos soportados (MVP): texto plano, .txt, .md.
    Uso:
      - Texto directo:  form-data con `text` y `title`.
      - Archivo:        form-data con `file` (multipart).

    La empresa debe tener la DB inicializada (POST /db/init primero).
    """
    content: str = ""

    if file is not None:
        filename = file.filename or "archivo"
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in ("txt", "md", ""):
            raise HTTPException(
                status_code=415,
                detail=f"Formato .{ext} no soportado aún. Usá .txt o .md, o enviá texto directo.",
            )
        raw = await file.read()
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            content = raw.decode("latin-1")
        title = title if title != "documento" else filename

    elif text:
        content = text.strip()
    else:
        raise HTTPException(status_code=422, detail="Enviá 'text' o un 'file'.")

    if not content:
        raise HTTPException(status_code=422, detail="El contenido está vacío.")

    source = "file" if file else "manual"
    result = ingest_document(
        empresa_id=company_id,
        title=title,
        content=content,
        source=source,
        collection=collection,
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Ingest falló"))
    return result


@app.get("/market/dolares")
async def market_dolares():
    """
    Retorna los tipos de cambio en tiempo real desde DolarAPI.com.
    No requiere empresa_id ni DB inicializada.

    Incluye: oficial, blue, mep (bolsa), ccl, cripto, tarjeta, mayorista.
    """
    rates = get_live_dollar_rates()
    if not rates:
        raise HTTPException(status_code=503, detail="No se pudo obtener cotizaciones")
    return {"source": "dolarapi.com", "rates": rates}


# ── Run ────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
