"""
PolPilot API — Gateway Principal (v2: Super-Agente).

Cambios respecto a v1 (multiagente):
  - /query usa exclusivamente services/super_agent.py
  - Eliminado: wiring de message_broker y AGENT_REGISTRY
  - Eliminado: endpoints /broker/* (deprecados junto con message_broker.py)
  - Eliminado: endpoints /agents/finanzas/query, /agents/economia/query,
               /agents/investigador/query (los agentes individuales son legacy)
  - Mantenidos sin cambios: /context/*, /db/*, /ingest, /market/dolares, /health

Endpoints activos:
  POST /query                          → Pipeline super-agente (único punto de orquestación)
  GET  /context/{company_id}           → Estado del Context Store de una empresa
  GET  /context/{company_id}/artifacts → Artefactos almacenados de una empresa
  POST /context/{company_id}           → Escribe entrada en Context Store
  GET  /db/status/{empresa_id}         → Estado de las DBs
  POST /db/init/{empresa_id}           → Inicializa y seedea las DBs
  POST /db/sync/{empresa_id}           → Sincroniza datos externos (BCRA + DolarAPI)
  POST /ingest                         → Ingesta de documentos al vector store
  GET  /market/dolares                 → Tipos de cambio en tiempo real
  GET  /health                         → Health check
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from schemas import (
    Artifact,
    ContextEntry,
    QueryRequest,
    QueryResponse,
)
from services.context_store import context_store
from services.data_bridge import (
    ensure_initialized,
    get_live_dollar_rates,
    ingest_document,
    run_external_sync,
    run_seed,
    get_dashboard_data,
    get_finanzas_data,
    get_creditos_data,
)
from services.super_agent import process_query


# ── Lifespan ───────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    status = ensure_initialized(settings.DEFAULT_EMPRESA_ID)
    if status["has_data"]:
        print(f"[PolPilot] DB lista para '{settings.DEFAULT_EMPRESA_ID}' ✓ (super-agente activo)")
    elif status["polpilot_available"]:
        print(f"[PolPilot] DB vacía. Ejecutar: POST /db/init/{settings.DEFAULT_EMPRESA_ID}")
    else:
        print("[PolPilot] polpilot.backend no disponible — usando mock data")
    yield


# ── App ────────────────────────────────────────────────

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="2.0.0",
    description=(
        "PolPilot API v2 — Arquitectura de super-agente con skills. "
        "Un único punto de orquestación LLM reemplaza el sistema multiagente."
    ),
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


# ── Endpoints: Datos estructurados para el frontend ───

@app.get("/dashboard/{empresa_id}")
async def dashboard(empresa_id: str):
    """
    Datos consolidados del dashboard para el frontend.
    Devuelve: profile, financials, indicators, cashPosition, morosos, benchmark, alerts.
    Si la DB no está inicializada retorna 404 (el frontend cae en mock automáticamente).
    """
    data = get_dashboard_data(empresa_id)
    if not data:
        raise HTTPException(status_code=404, detail="No hay datos para esta empresa. Ejecutá POST /db/init primero.")
    return data


@app.get("/finanzas/{empresa_id}")
async def finanzas(empresa_id: str):
    """
    Datos financieros internos para la vista Finanzas del frontend.
    Devuelve: financials, indicators, clients, morosos, products, suppliers, employees.
    """
    data = get_finanzas_data(empresa_id)
    if not data:
        raise HTTPException(status_code=404, detail="No hay datos de finanzas para esta empresa.")
    return data


@app.get("/creditos/{empresa_id}")
async def creditos(empresa_id: str):
    """
    Datos de créditos, macro y regulaciones para la vista Créditos del frontend.
    Devuelve: credits, creditProfile, macro, regulations, sectorSignals.
    """
    data = get_creditos_data(empresa_id)
    if not data:
        raise HTTPException(status_code=404, detail="No hay datos de créditos para esta empresa.")
    return data


# ── Endpoints: Core ────────────────────────────────────

@app.get("/health")
async def health():
    """Health check."""
    return {"status": "ok", "version": "2.0.0", "architecture": "super-agent"}


@app.post("/query", response_model=QueryResponse)
async def super_agent_query(request: QueryRequest):
    """
    Pipeline completo del super-agente.

    Flujo interno (automático, un solo call de usuario):
      ingest → client_db → novelty → classify (LLM) →
      execute skills → synthesize (LLM) → memory_write → response

    Request:
    ```json
    {
      "company_id": "taller_frenos_001",
      "user_message": "¿A qué crédito puedo aplicar?",
      "conversation_id": "uuid (opcional — se genera automáticamente)",
      "conversation_context": "resumen previo (opcional)"
    }
    ```

    Nota: `metadata.agents_activated` ahora lista las skills invocadas,
    no agentes. `metadata.inter_agent_calls` siempre es 0 en v2.
    """
    if not request.user_message.strip():
        raise HTTPException(status_code=400, detail="user_message is required")

    result = await process_query(request)
    return result


# ── Endpoints: Context Store ───────────────────────────

@app.get("/context/{company_id}")
async def get_company_context(company_id: str):
    """
    Estado completo del Context Store para una empresa.

    Retorna todas las entradas de contexto con su jerarquía de verdad:
    - M_int (máxima): Fuentes estructuradas (ERP, integraciones)
    - M_onb (media): Datos de onboarding / perfil PyME
    - M_conv (baja): Datos conversacionales
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
    """Artefactos almacenados para una empresa, filtrables por origen."""
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

    Aplica jerarquía de verdad automáticamente.
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
    """Verifica el estado de las bases de datos de una empresa."""
    return ensure_initialized(empresa_id)


@app.post("/db/init/{empresa_id}")
async def db_init(empresa_id: str):
    """
    Inicializa y seedea las 3 bases de datos de una empresa.

    Crea internal.sqlite, external.sqlite, memory.sqlite y vectors/ (ChromaDB).
    Idempotente: si los datos ya existen se vuelven a cargar.
    """
    result = run_seed(empresa_id)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Seed falló"))
    return result


@app.post("/db/sync/{empresa_id}")
async def db_sync(empresa_id: str, mode: str = "all"):
    """
    Sincroniza datos externos desde APIs del BCRA y DolarAPI.

    Query param `mode`:
      - 'all'     → macro + perfil crediticio + catálogo de créditos
      - 'macro'   → solo tasas, inflación, tipos de cambio
      - 'credits' → solo catálogo de préstamos BCRA Transparencia
      - 'profile' → solo perfil crediticio BCRA Central de Deudores
    """
    result = run_external_sync(empresa_id, mode=mode)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Sync falló"))
    return result


# ── Endpoints: Ingest ──────────────────────────────────

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
    """
    content: str = ""

    if file is not None:
        filename = file.filename or "archivo"
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in ("txt", "md", ""):
            raise HTTPException(
                status_code=415,
                detail=f"Formato .{ext} no soportado. Usá .txt o .md, o enviá texto directo.",
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


# ── Endpoints: Market data ─────────────────────────────

@app.get("/market/dolares")
async def market_dolares():
    """
    Retorna los tipos de cambio en tiempo real desde DolarAPI.com.
    No requiere empresa_id ni DB inicializada.
    """
    rates = get_live_dollar_rates()
    if not rates:
        raise HTTPException(status_code=503, detail="No se pudo obtener cotizaciones")
    return {"source": "dolarapi.com", "rates": rates}


# ── Run ────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
