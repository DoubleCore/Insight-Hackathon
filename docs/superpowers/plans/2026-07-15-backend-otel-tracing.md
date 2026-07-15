# Backend OTEL Tracing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add optional OpenTelemetry spans to the API server so one QA request can be traced across request handling, retrieval, evidence gating, and LLM generation.

**Architecture:** Introduce a dependency-safe tracing wrapper that no-ops when OTEL libraries are unavailable or disabled. Persist the generated `trace_id` on `query_runs`, expose it through admin trace APIs, and add spans around existing pipeline/retrieval boundaries without storing prompts or full context as span attributes.

**Tech Stack:** FastAPI, SQLite repository, Pydantic schemas, optional OpenTelemetry SDK/OTLP exporter, existing pytest suite.

---

### Task 1: Tracing Helper And Configuration

**Files:**
- Create: `apps/api-server/app/services/tracing.py`
- Modify: `apps/api-server/app/config.py`
- Modify: `apps/api-server/app/main.py`
- Test: `apps/api-server/tests/test_tracing.py`

- [ ] **Step 1: Add settings for optional tracing**

Add `otel_enabled`, `otel_service_name`, and `otel_exporter_otlp_endpoint` to `Settings`, parsed from `OTEL_ENABLED`, `OTEL_SERVICE_NAME`, and `OTEL_EXPORTER_OTLP_ENDPOINT`.

- [ ] **Step 2: Add no-op-safe tracing wrapper**

Create `start_span(name, attributes)` returning a context manager with `trace_id`, `set_attribute`, `set_attributes`, and automatic exception recording. If OTEL packages are missing or disabled, the context manager yields a no-op span.

- [ ] **Step 3: Configure tracing during app creation**

Call `configure_tracing(configured_settings)` in `create_app()` before routers are mounted.

- [ ] **Step 4: Test no-op startup**

Run: `python -m pytest apps/api-server/tests/test_tracing.py -q`
Expected: helper imports and app startup pass even without OTEL packages installed.

### Task 2: Persist Query Trace Id

**Files:**
- Modify: `apps/api-server/app/storage.py`
- Modify: `apps/api-server/app/schemas.py`
- Test: `apps/api-server/tests/test_storage.py`
- Test: `apps/api-server/tests/test_api.py`

- [ ] **Step 1: Add `query_runs.trace_id`**

Add nullable `trace_id TEXT` to the table schema and migration path in `Repository.initialize()`.

- [ ] **Step 2: Update repository methods**

Allow `create_query_run(..., trace_id=None)` and `update_query_run(..., trace_id=None)`.

- [ ] **Step 3: Expose `trace_id` in schemas**

Add optional `trace_id` to `QueryRunSummary`; `QueryTrace` inherits it.

- [ ] **Step 4: Test persistence and API exposure**

Run: `python -m pytest apps/api-server/tests/test_storage.py::test_query_run_lifecycle apps/api-server/tests/test_api.py::test_admin_authentication_and_trace_listing -q`
Expected: stored and API-returned query runs include `trace_id` when present.

### Task 3: Instrument QA And Retrieval Path

**Files:**
- Modify: `apps/api-server/app/routers/user.py`
- Modify: `apps/api-server/app/services/qa_pipeline.py`
- Modify: `apps/api-server/app/services/retrieval.py`
- Test: `apps/api-server/tests/test_api.py`
- Test: `apps/api-server/tests/test_qa_pipeline.py`
- Test: `apps/api-server/tests/test_retrieval.py`

- [ ] **Step 1: Root request span**

Wrap `_execute_request()` in `qa.request`, set `query_run_id`, `conversation_id`, `group_id`, `question_length`, and `question_hash`, then persist the root span `trace_id`.

- [ ] **Step 2: QA stage spans**

Add child spans for `qa.rewrite`, `qa.retrieval`, `qa.evidence_gate`, and `qa.answer_generation`. Record counts, status, fallback/refusal reason, and model name only.

- [ ] **Step 3: Retrieval slice spans**

Add child spans around vector, BM25, BFS, lexical, merge, and rerank work. Record algorithm, status, candidate counts, selected counts, and fallback reason.

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest apps/api-server/tests/test_api.py::test_user_question_request_exposes_sse_and_public_result_only apps/api-server/tests/test_qa_pipeline.py apps/api-server/tests/test_retrieval.py -q`
Expected: behavior is unchanged and trace id is populated for background QA requests when a trace id exists.

### Task 4: Final Verification

**Files:**
- `apps/api-server/pyproject.toml`

- [ ] **Step 1: Add OTEL dependencies**

Add `opentelemetry-api`, `opentelemetry-sdk`, and `opentelemetry-exporter-otlp` to the API server dependencies so deployments can enable export.

- [ ] **Step 2: Run API test suite**

Run: `python -m pytest apps/api-server/tests -q`
Expected: all API server tests pass.

- [ ] **Step 3: Run admin portal verification if frontend types changed**

Run: `npm test && npm run build` in `apps/admin-portal`.
Expected: admin portal remains green.
