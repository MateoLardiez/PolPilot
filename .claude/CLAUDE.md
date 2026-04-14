# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PolPilot is an AI-powered executive operating system for Argentine SMBs (PyMEs). It acts as a virtual CFO + Economist accessible via WhatsApp. The hackathon scope (April 2026) focuses on two features:

1. **Automatic loan detection** — identify which bank loans an SMB qualifies for based on their financial data
2. **Strategic capital deployment plan** — explain how to invest borrowed money to maximize return

The project is bilingual: documentation is primarily in **Spanish**, code and technical specs use English terminology.

## Current State

The project has **database layer implemented** and is building the backend. The repository contains design documents, flow diagrams, research, team discussion transcripts, and working database code with seed data.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Input channel | WhatsApp Business API (Twilio / 360dialog) |
| Backend / API | Node.js (Gateway) + FastAPI (Python, agent services) |
| Main LLM | Claude Sonnet (Anthropic API) |
| Audio processing | Whisper (OpenAI) |
| Document OCR | Google Vision API |
| Database | SQLite (per-client isolation) + ChromaDB (vector search) |
| PDF generation | ReportLab / WeasyPrint |

## Database

Each client gets 4 isolated data stores under `polpilot/data/{empresa_id}/`:

- **internal.sqlite** — business data (profile, financials, clients, suppliers, products, employees, documents). AI agents **cannot write** here.
- **external.sqlite** — external data (credits, macro indicators, regulations, sector signals, credit profile, collective intelligence). Research/Economy agents can write.
- **memory.sqlite** — conversations, messages, summaries, query log. Data Service and Orchestrator write.
- **vectors/** (ChromaDB) — semantic search embeddings across 3 collections: `internal_docs`, `external_research`, `conversation_context`.

Code: `polpilot/backend/data/db.py` (SQLite connections + schemas + FTS5) and `polpilot/backend/data/vector_store.py` (ChromaDB wrapper). Seed script: `python -m polpilot.backend.seed.seed_database`. See `polpilot/data/README.md` for full details.

## Architecture

The system is a **controlled-expansion multi-agent orchestrator** with this pipeline:

```
User Input (WhatsApp) → Normalization → Dummy Analyzer → Topic Analyzer
  → Gateway/Orchestrator → Parallel Agent Mesh → Synthesizer → Stop-Loss Engine → Response
```

**Key architectural concepts:**

- **Stop-Loss Cognitive Control** — expansion only continues if a utility score exceeds a threshold (S_t >= 0.18). Prevents over-analysis and cost overruns.
- **Structured Artifacts** — agents exchange typed JSON objects (FACT, CLAIM, HYPOTHESIS, REQUEST), not free-form text. This is critical for token efficiency and auditability.
- **Gateway as single authority** — all agent communication flows through the gateway/orchestrator. Agents never talk directly to each other.
- **Memory Truth Hierarchy** — `integrated > onboarded > conversational > inferred > reasoning_trees`. Prevents conversational noise from overwriting verified facts.
- **Hard constraints** — max 3 iterations, max 4 agents, max 7s latency (complex queries), 2.5s target (simple).

**Active modules (hackathon):**
- **CFO Module** — builds financial profile from multimodal input (invoices, photos, voice memos), produces cash flow projections, solvency ratios, health score
- **Economist Module** — crosses internal data with macroeconomic context (inflation, rates, sector cycles) from BCRA APIs

## Key Documents

| Document | Location | Purpose |
|----------|----------|---------|
| Hackathon scope & features | `PolPilot idea.md` | What we're building and why |
| Formal system specification | `Ideas/Documento_Tecnico_InterAgente_PolPilot_v2.md` | Mathematical spec: objective function, stop-loss formula, agent activation scoring |
| Logical & technical design | `Ideas/PolPilot_diseno_logico_formal_y_tecnico.txt` | Detailed logical architecture |
| Implementation guide | `Ideas/polpilot_documentacion_tecnica_detallada_v_1.md` | Layer-by-layer technical breakdown |
| Architecture sketch | `Ideas/polpilot_boceto_arquitectura.md` | High-level architecture overview |
| Credit data research | `investigacion-creditos-pyme.md` | API viability analysis for Argentine bank data sources |
| Flow diagrams | `Flows_scheme/` | System macro flow, agent interaction, stop-loss logic, query lifecycle (PlantUML) |
| Team discussions | `Transcript/` | Voice message transcripts with implementation decisions |

## External Data Sources

Argentine bank websites lack public APIs. The viable programmatic sources are:

- **BCRA Transparency API** — interest rates by bank (best source for loan rates)
- **BCRA Central de Deudores API** — credit profile lookup by CUIT (tax ID)
- **BCRA Economic Variables API** — reference rates, monetary indicators
- **datos.gob.ar** — government open data for credit statistics

Bank-specific SME credit lines (Banco Provincia, Banco Galicia, etc.) require **manual data curation** — their sites are SPAs with no structured data access.

## Permitted External Domains

The `.claude/settings.local.json` allows WebFetch to: `bcra.gob.ar`, `estadisticasbcra.com`, `datos.gob.ar`, `bancoprovincia.com.ar`, `galicia.ar`, `boletinoficial.gob.ar`.
