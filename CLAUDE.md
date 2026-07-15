# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Semiconductor Industry Knowledge Graph (半导体产业链图谱系统) — a dual-frontend acceptance platform with a FastAPI backend, React admin portal, and React user portal. The system provides deep retrieval, evidence-gated Q&A, graph visualization, governance operations, and industry search over a Neo4j + Graphiti knowledge graph.

## Commands

### Backend (API Server)

```powershell
# Install dependencies
cd apps/api-server
python -m pip install -e .

# Run all tests
python -m pytest -q

# Run a single test file
python -m pytest tests/test_qa_pipeline.py -q

# Run a single test by name
python -m pytest tests/test_retrieval.py::test_merge_candidates_deduplication -q

# Start the API server (from repo root)
$env:APP_ENV = "development"
$env:ADMIN_PASSWORD = "admin"
$env:SESSION_SECRET = "<random-secret>"
$env:COOKIE_SECURE = "false"
python -m uvicorn app.main:app --app-dir apps/api-server --host 127.0.0.1 --port 8001 --workers 1
```

### Frontend (Admin Portal — port 7871)

```powershell
cd apps/admin-portal
pnpm install
pnpm dev          # dev server
pnpm test         # vitest run
pnpm build        # tsc + vite build
```

### Frontend (User Portal — port 7870)

```powershell
cd apps/user-portal
pnpm install
pnpm dev          # dev server
pnpm test         # vitest run
pnpm build        # tsc + vite build
```

### One-Click Start/Stop

```powershell
.\start-acceptance-platform.bat   # starts API + both frontends
.\stop-acceptance-platform.bat    # stops them (does not stop Neo4j)
```

## Architecture

### Three-App Monorepo

- **`apps/api-server/`** — Python 3.11+ FastAPI backend. Entry point: `app/main.py` → `create_app()`. Uses SQLite for observability (conversations, query runs, retrieval traces, LLM call logs, background jobs) and Neo4j + Graphiti for the knowledge graph.
- **`apps/admin-portal/`** — React + Vite + TypeScript admin UI (Cytoscape graph canvas, governance panel, trace monitor, decision signals, industry search). Port 7871.
- **`apps/user-portal/`** — React + Vite + TypeScript user-facing Q&A UI. Port 7870.

### Backend Service Layer (`apps/api-server/app/services/`)

The backend follows a layered architecture: **Routers → Services → Storage/External**.

Key services and their roles:

- **`qa_pipeline.py`** — `QuestionAnsweringPipeline`: orchestrates the full Q&A flow: question rewrite → deep retrieval → evidence gate → answer generation. Each stage is traced and persisted to SQLite.
- **`retrieval.py`** — `DeepSearchService`: multi-slice retrieval combining 4 algorithms in parallel (vector cosine, BM25, BFS from entity origins, Neo4j lexical). Results are deduplicated by UUID/content-hash, merged via RRF, then reranked by CrossEncoder (SiliconFlow reranker) with RRF fallback. Configurable limits: `slice_limit=20`, `candidate_pool_limit=60`, `final_result_limit=12`.
- **`trust.py`** — `EvidenceGate` + `TrustBuilder`: evidence gate refuses answers lacking public evidence; trust builder outputs 4 independent dimensions (evidence quality, confidence, freshness, verification) — never a composite score. `potential_fit` and `inferred` claims never upgrade to confirmed.
- **`evidence.py`** — `EvidenceIndex`: loads JSONL evidence files from `data/evidence/`, indexes by `evidence_id`, resolves citations for retrieval candidates.
- **`governance.py`** — `GovernanceService`: saga summarization (paginated LLM calls), community rebuild (Louvain on NetworkX + LLM naming), all write-locked to group `semiconductor_dc_kg`.
- **`unified_graph.py`** — `UnifiedGraphService`: hierarchical graph expansion with 8 branches (hierarchy, business, facts, timeline, saga, community, evidence, digital_china). Translates Neo4j Cypher results into `GraphPayload` with positioned nodes.
- **`decision_signals.py`** — Import decision signals (policy/tech/industry/business) from links, PDFs, or text into Graphiti episodes under a dedicated saga.
- **`web_search.py`** — `WebSearchService`: multi-provider web search (Tavily, Bocha) for industry search.
- **`group_context.py`** — Multi-tenancy: resolves `group_id` from query param, `X-Graph-Group` header, or default setting.
- **`runtime.py`** — `OpenAICompatibleChatClient`: wraps OpenAI SDK for question rewrite and answer generation via SiliconFlow.
- **`tracing.py`** — Optional OpenTelemetry integration (disabled by default). `start_span()` is a no-op when OTEL is not configured.
- **`events.py`** — `RequestEventBroker`: in-process SSE event streaming for real-time Q&A progress.

### Data Flow: Q&A Pipeline

1. User sends question → `POST /api/v1/user/conversations/{id}/messages`
2. `QuestionAnsweringPipeline.run()`:
   - **Rewrite**: if conversation history exists, LLM rewrites the question
   - **Deep Retrieval**: 4 parallel slices (vector, BM25, BFS, lexical) → merge → dedup → RRF → CrossEncoder rerank → top-12 selected
   - **Evidence Gate**: only candidates with resolvable `evidence_ids` pass; `no_public_evidence` claims are rejected
   - **Answer Generation**: LLM generates answer from supporting candidates; falls back to fact summary on LLM failure
3. Result includes answer, citations, trust profile, and full retrieval trace

### Storage

- **SQLite** (`data/runtime/qa_observability.db`): conversations, messages, query_runs, retrieval_slices, retrieval_candidates, llm_calls, background_jobs. Uses WAL mode. `Repository` class in `storage.py` manages all access.
- **Neo4j**: knowledge graph (entities, relationships, episodes, sagas, communities, evidence). Accessed via Graphiti SDK or direct Cypher.
- **JSONL** (`data/evidence/*.jsonl`): evidence records loaded at startup by `EvidenceIndex`.

### Authentication

- Cookie-based: `CookieSigner` in `auth.py` signs/verifies user and admin cookies
- Admin access requires `ADMIN_PASSWORD` login → admin cookie
- User identity is anonymous session-based (auto-generated UUID)
- Non-development environments require `SESSION_SECRET` or the server refuses to start

### Key Configuration (Environment Variables)

| Variable | Default | Notes |
|---|---|---|
| `APP_ENV` | `development` | Non-dev requires `SESSION_SECRET` |
| `NEO4J_URI` | `bolt://localhost:7687` | |
| `NEO4J_PASSWORD` | `password` | Override in production |
| `GROUP_ID` | `semiconductor_dc_kg` | Default graph group |
| `API_PORT` | `8001` | |
| `ADMIN_PASSWORD` | (empty) | Must be set |
| `SILICONFLOW_API_KEY` | (empty) | Required for LLM/embedding/reranker |
| `GRAPHITI_LLM_MODEL` | `deepseek-ai/DeepSeek-V3.2` | |
| `GRAPHITI_EMBEDDING_MODEL` | `BAAI/bge-m3` | |
| `GRAPHITI_RERANKER_MODEL` | `BAAI/bge-reranker-v2-m3` | |
| `OTEL_ENABLED` | `false` | Enable OpenTelemetry tracing |

### Scripts (`scripts/`)

Data processing and maintenance scripts for building, importing, enriching, and verifying the knowledge graph. These are standalone scripts (not part of the API server) that operate directly on Neo4j/Graphiti. Key shared utilities in `scripts/kg_common.py`.

### Data (`data/`)

- `business_graph/` — CSV files for L1-L4 segments, products, company relationships, competition, digital China relations, business opportunities
- `company_pool/` — Company candidates, leaders, and relationship data
- `evidence/` — JSONL evidence records (stages 1-3, decision signals)
- `graphiti/` — Graphiti episode data and migration notes
- `decision_signals/` — Seed decision signal definitions
- `runtime/` — SQLite DB and runtime artifacts (gitignored)

### API Routes

- `/api/v1/user/*` — User-facing: conversations, messages (SSE streaming), graph expand
- `/api/v1/admin/*` — Admin: governance (saga summarize, community rebuild), graph visualization, trace monitor, decision signal import, industry search, background jobs
- `/api/v1/groups/*` — Group management
- `/health` — Health check (verifies SQLite connectivity)

### Frontend-Backend Contract

Both frontends call the API at `http://127.0.0.1:8001`. CORS only allows `http://127.0.0.1:7870` and `http://127.0.0.1:7871` with credentials. The admin portal uses Cytoscape for graph visualization; the user portal is a simpler Q&A interface.

## Testing

- Backend tests use `pytest` with `httpx` `AsyncClient` (no live server needed). Tests mock Neo4j/Graphiti/LLM dependencies.
- Frontend tests use `vitest` + `@testing-library/react`.
- All test files follow `test_*.py` / `*.test.ts(x)` convention colocated in `tests/` directories.
