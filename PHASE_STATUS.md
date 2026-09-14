# PHASE_STATUS.md — Project Roadmap & Progress Tracker

This document tracks the active phase, completed milestones, blockers, and immediate next actions for **ContractIQ**.

---

## 1. Project Health & Metadata

| Metric | Value |
| :--- | :--- |
| **Current Phase** | **Phase 20: Production Deployment (20A–20E)** |
| **Status** | **COMPLETE** |
| **Last Verified State** | Frontend: `npm run build` (built in 267ms, `_redirects` verified), `npx tsc --noEmit` (0 errors); Backend: `test_production_config.py` (11/11 passed), `test_observability.py` (17/17 passed), `test_secret_scanner.py` (6/6 passed, 0 secrets), `python -m compileall` (0 errors); Alembic migration `f31920b7c102` applied to Neon DB; Dockerfile & Render Blueprint verified |
| **Last Git Commit** | `14989e6` ("feat: implement performance and observability (Phase 19A-19E)") |
| **Git Remote** | `https://github.com/vasaakhilvignesh/ContractAi.git` (branch: `main`) |
| **Next Phase** | **Production Operations & Continuous Monitoring** |
| **Exact Next Action** | Production release ready for cloud provisioning on Render / Docker / Vercel. |

---

## 2. Phase Breakdown & Status

- [x] **Phase 20A–20E: Production Deployment & System Packaging** *(Completed)*
  - [x] **20A — Backend Deployment:** FastAPI backend configured for production with Uvicorn ASGI; `backend/Dockerfile` using Python 3.13-slim with non-root user `appuser`, automated curl healthcheck against `/health/liveness`; `backend/start.sh` entrypoint script running `alembic upgrade head` before Uvicorn startup; live Neon PostgreSQL connectivity with serverless SSL pooled connection; environment-variable driven configuration without hardcoded secrets.
  - [x] **20B — Frontend Deployment:** React 19 + Vite 8 SPA configured with dynamic API base URL (`VITE_API_BASE_URL` in `src/services/api.ts`); SPA client routing artifacts created (`public/_redirects` with `/* /index.html 200` and `vercel.json` rewrite configuration); verified production build emits all redirect assets to `dist/`.
  - [x] **20C — Production Configuration & Security:** Pydantic `Settings` model validator enforces production invariants: rejects default development JWT secrets, enforces >= 32 character secret length, validates non-empty `DATABASE_URL` and `GEMINI_API_KEY`, forces `APP_DEBUG=False`, disables interactive Swagger `/docs` and `/redoc` in production; strict CORS policy rejecting wildcard `*` with credentials and binding to configured `CORS_ORIGINS`.
  - [x] **20D — Multi-Target Deployment Artifacts:** Created `render.yaml` defining dual-service Infrastructure-as-Code Blueprint (`contractiq-api` web service and `contractiq-web` static site); created `docker-compose.prod.yml` for unified container orchestration; root `.env.example` and `backend/.env.example` updated with production variables.
  - [x] **20E — Production Verification & Documentation:** Implemented 11 production configuration tests in `backend/tests/test_production_config.py` (100% pass); updated `DECISIONS.md` with DEC-045; updated `FLOW.md` with production deployment topology; updated `README.md` with production operations guide.

- [x] **Phase 19A–19E: Performance & Observability** *(Completed)*
  - [x] **19A — Request & Latency Observability:** Added `RequestIDMiddleware` generating/propagating `X-Request-ID` across all requests; structured access log per response capturing method, route template, status code, and latency in ms (`time.perf_counter`); production JSON-line logging (`JSONLineFormatter`).
  - [x] **19B — RAG & Provider Metrics:** Instrumented discrete execution stages with wall-clock timing: `semantic_retrieval`, `keyword_retrieval`, `hybrid_rrf_fusion`, `gemini_embedding_batch`, `gemini_structured_llm_call`, `citation_validation`, and `rag_pipeline_execution`. All metadata filtered against `SAFE_LOG_KEYS`.
  - [x] **19C — Database Performance Indexing:** Created Alembic migration `f31920b7c102` adding composite indexes on `document_chunks(contract_id, chunk_index)`, `contract_facts(contract_id, fact_key)`, and `clauses(contract_id, clause_type)`. Successfully applied to live Neon database.
  - [x] **19D — Safe Error & Operational Handling:** `SafeLoggingFilter` automatically scrubs `DATABASE_URL` passwords, JWT Bearer tokens, Gemini API keys (`AIza...`), and authorization headers from all logs and tracebacks. Exception handlers mask secrets before client responses.
  - [x] **19E — Health, Readiness & Diagnostics:** Enhanced `/health` with safe environment, model, and connectivity flags without secrets. Added dedicated `/health/liveness` (process responsiveness) and `/health/readiness` (database dependency readiness returning 200/503) probes. Added 17 tests in `test_observability.py` (100% pass).


- [x] **Phase 18 Security Remediation & Secret Scanner Hardening** *(Completed)*
  - [x] **Secret Exposure Remediation:** Located exposed Google API key fixture in test suite; replaced with dynamic synthetic token constructors (`mock_gemini_key = "AIza" + ("SyntheticKeyForMaskTesting" * 2)[:35]`); purged literal string from all tracked code.
  - [x] **Git History Purge:** Rewrote affected commit tip via `git commit --amend`, ensuring zero occurrences of the key exist across all 50 commits in reachable Git history.
  - [x] **Lightweight Secret Scanner:** Implemented `backend/app/core/secret_scanner.py` detecting Google/Gemini API keys, private keys, database credentials, AWS access keys, and bearer JWTs; safe reporting never echoes secret values; verified git ignore status for `.env` files.
  - [x] **Automated Secret Regression Suite:** Implemented `backend/tests/test_secret_scanner.py` (6/6 tests passing) verifying safe placeholders pass, unmarked credentials flag alerts, Google API patterns are caught, repository contains no secrets, `.env` files remain ignored, and no secrets are printed in output.

- [x] **Phase 18A–18E: Security & Reliability Hardening** *(Completed)*
  - [x] **18A — Prompt Injection Protection:** Hardened Grounded RAG & Analyst prompt builders; wrapped retrieved contract chunks in `<untrusted_contract_text chunk_id="{id}" page="{page}">` XML tags with explicit negative directives prohibiting execution of instructions embedded within contracts; preserved 100% exact substring citation verification.
  - [x] **18B — Authentication & Authorization (IDOR) Hardening:** Re-verified JWT validation (tampered signature, expired, missing, malformed token rejection); enforced tenant ownership (`verify_contract_access_by_id`, `verify_contracts_access_by_ids`) across all 28+ contract endpoints, analyst queries, obligations, and multi-contract comparison routes.
  - [x] **18C — Input & File Security:** Enforced `sanitize_filename` path traversal defense, strict `%PDF-` magic byte validation, 20 MB size ceiling, non-empty payload requirement, and atomic cleanup of stored files on transaction failure.
  - [x] **18D — Provider & Database Reliability:** Implemented `mask_secrets` utility scrubbing database passwords, `postgresql://` URIs, `GEMINI_API_KEY`, JWT secrets, and Authorization Bearer credentials from all client-facing error payloads and FastAPI global exception handlers.
  - [x] **18E — Comprehensive Security & Reliability Test Suite:** Created 18 focused tests in `backend/tests/test_security_and_reliability.py` verifying prompt injection defense, multi-contract isolation, IDOR across all routers, token tampering/expiration, file upload security, and secret masking (100% pass rate).

- [x] **Phase 17A–17E: RAG Evaluation & Quality Benchmarking** *(Completed)*
  - [x] **17A — Retrieval Regression Evaluation:** Extended existing Phase 5D metrics (`precision_at_k`, `recall_at_k`, `reciprocal_rank_at_k`), deterministic benchmark query suite with ground truth relevance labels.
  - [x] **17B — Grounded Generation Evaluation:** Implemented grounding metrics (`claim_groundedness_rate`, `citation_validity_rate`, `citation_completeness_rate`, `calculate_grounding_metrics`) measuring supported vs unsupported claims and citation integrity.
  - [x] **17C — Hallucination & Unsupported-Claim Detection:** Deterministic evaluation detecting wrong-contract citations, hallucinated chunk IDs, verbatim text mismatches, page number mismatches, and insufficient evidence handling.
  - [x] **17D — RAG Failure-Case Regression Suite:** Dedicated evaluation across 13 distinct failure modes (no retrieval matches, low retrieval confidence, irrelevant top-k, non-existent chunk ID, wrong-contract citation, verbatim text mismatch, page mismatch, malformed structured LLM output, provider API failure, empty retrieved context, conflicting facts, missing extracted facts, cross-contract evidence bleeding).
  - [x] **17E — Quality Reporting & Invariant Protection:** Automated test assertions verifying 0% wrong-contract citation acceptance, 0% hallucinated chunk acceptance, 100% text mismatch rejection, and 100% insufficient-evidence detection. Structured JSON & Markdown evaluation summary reports.

- [x] **Phase 15A–15D: Analyst Query UI & Grounded Citations** *(Completed)*
  - [x] Natural language query input with document scope selector (1–10 contracts) and multi-document query history.
  - [x] Grounded answer UI with structured claims badges (verified claim vs unverified) and interactive citation jumping.
  - [x] Traceable citation list with contract title, 1-indexed page number, chunk ID, and exact verbatim snippet.
  - [x] Insufficient-evidence alert banner preventing hallucinated contractual claims.
  - [x] Expandable retrieval diagnostics panel displaying hybrid RRF method, contract counts, chunk counts, context character lengths, latency, and chunk rank metrics.
- [x] **Phase 16A–16D: Contract Document Viewer & Navigation** *(Completed)*
  - [x] Contract Overview header and executive summary with risk level, processing status, and key terms.
  - [x] Document & Evidence Viewer with page-by-page selector, chunk-level inspection, and verbatim PDF text display.
  - [x] Structured Clauses tab with verbatim text, legal category, extraction confidence, and direct links to source document chunks.
  - [x] Extracted Obligations tab displaying responsible parties, due dates, frequencies, and verbatim quotes.
  - [x] Deterministic Risk Signals tab detailing triggered rules, reasons, and recommended counsel actions.
  - [x] Structured Facts tab presenting normalized parameters with page citations and source links.
  - [x] Cross-route navigation linking `/contracts`, `/contracts/:id`, `/analyst`, `/obligations`, `/risks`, and `/compare`.

- [x] **Phase 0: Project Baseline, Audit & Memory Protocol** *(Completed)*
  - [x] Full codebase audit of dependencies, tooling, routes, components, and styling.
  - [x] Verification of production build and type checking.
  - [x] Git repository and remote safety audit.
  - [x] Creation of `AGENTS.md` (Operational protocol & 12 development rules).
  - [x] Creation of `DECISIONS.md` (Decision record for baseline & pending architecture).
  - [x] Creation of `FLOW.md` (Current application flow & planned system architecture).
  - [x] Creation of `PHASE_STATUS.md` (This roadmap).
  - [x] Architecture baseline documentation updated in `README.md`.
- [x] **Phase 1: Backend Scaffolding, Data Modeling & Database (PostgreSQL + pgvector)** *(Completed)*
  - [x] Backend technology selection: Python FastAPI + SQLAlchemy 2.0 (DEC-006, DEC-017).
  - [x] Python virtual environment setup (`backend/.venv`) and dependency installation (`requirements.txt`).
  - [x] FastAPI application scaffold with CORS, lifespan, and configuration (`backend/app/`).
  - [x] Database schema design: 7 models with strict evidence lineage (`User`, `Contract`, `DocumentChunk`, `Clause`, `Obligation`, `RiskSignal`, `AuditEvent`).
  - [x] pgvector integration: `Vector` column mapping on `DocumentChunk`.
  - [x] Alembic migration tooling configured (`backend/alembic/`) with dynamic environment variable loading.
  - [x] Health check endpoint (`GET /health`) verifying API process and database connectivity.
  - [x] Backend unit test suite (48 passed, 0 skipped).
  - [x] `DATABASE_URL` configured for Neon PostgreSQL in gitignored `backend/.env`.
  - [x] Live Neon PostgreSQL connection verified (PostgreSQL 18.6).
  - [x] Live pgvector extension verified (version 0.8.6).
  - [x] Initial Alembic migration generated (`20260912_1452_df2c477aaabb_initial_schema.py`).
  - [x] Initial migration applied to Neon PostgreSQL (`alembic upgrade head`).
  - [x] All 7 application tables and `alembic_version` verified in Neon public schema.
  - [x] All 12 foreign keys and pgvector column verified in Neon database.
  - [x] Live database health check test (`test_health_with_real_db_is_ok`) passed against Neon.
- [x] **Phase 2: PDF Ingestion & Contract State Foundation** *(Completed)*
  - [x] **Phase 2A: Contract API Foundation** *(Completed)*
    - [x] Pydantic v2 schemas (`ContractBase`, `ContractCreate`, `ContractUpdate`, `ContractResponse`, `ContractListResponse`).
    - [x] Contract service layer with data-access operations, attribute filtering, and deterministic pagination.
    - [x] Contract REST API router mounted at `/contracts` and `/api/v1/contracts` (`POST`, `GET`, `GET /{id}`, `PATCH /{id}`, `DELETE /{id}`).
    - [x] 12 comprehensive contract API unit/integration tests covering CRUD, pagination, 404/422 errors against live Neon DB.
    - [x] Backend test suite passes: 60 passed (48 Phase 1 + 12 Phase 2A).
    - [x] Zero database migration required; fully compatible with Phase 1 schema.
  - [x] **Phase 2B: Contract Upload API & Storage** *(Completed)*
    - [x] Dedicated upload endpoint: `POST /contracts/{contract_id}/upload` (with `/api/v1` alias).
    - [x] File validation: filename sanitization, `.pdf` extension enforcement, MIME type check.
    - [x] PDF signature verification: strict `%PDF-` magic bytes check.
    - [x] Size limitation: configurable limit (20 MB default) returning 413 on oversize.
    - [x] Path traversal prevention: UUID-based safe storage path generation.
    - [x] Contract association: updates `file_name`, `file_storage_key`, `processing_status="uploaded"`.
    - [x] Atomic failure cleanup: unlinks newly stored file if database commit fails.
    - [x] Deterministic re-upload: replaces contract file association and deletes previous physical file.
    - [x] 11 integration tests in `backend/tests/test_contract_upload_api.py` (71 total backend tests passing).
    - [x] Zero database migrations required; reuses Phase 1 schema fields.
  - [x] **Phase 2C: Contract Processing State** *(Completed)*
    - [x] Controlled lifecycle state enum (`ProcessingStatus`: `pending`, `uploaded`, `queued`, `processing`, `completed`, `failed`).
    - [x] Strict state machine rules with valid transitions: `uploaded` -> `queued` -> `processing` -> `completed` / `failed`, with `failed` -> `queued` (retry).
    - [x] Re-upload resets state back to `uploaded` and clears `processing_error`.
    - [x] Processing status endpoints: `GET /contracts/{contract_id}/processing-status` and `PATCH /contracts/{contract_id}/processing-status` (with `/api/v1` aliases).
    - [x] Robust validation: invalid transitions rejected with 400 Bad Request; unrecognized states rejected with 422; missing contracts return 404.
    - [x] 10 focused tests in `backend/tests/test_contract_processing_state.py` (81 total backend tests passing).
    - [x] Zero database migrations required; reuses existing `processing_status` and `processing_error` columns.
- [ ] **Phase 3: PDF Extraction, Text Normalization & Chunking Engine**
  - [x] **Phase 3A: PDF Text Extraction** *(Completed)*
    - [x] Integrated PyMuPDF (`pymupdf==1.28.2`) for fast, robust native PDF extraction.
    - [x] Defined strongly typed extraction schemas (`PageBlock`, `PageExtraction`, `ExtractionResult`, `ContractExtractionResponse`).
    - [x] Built independent PDF extraction service (`pdf_extraction_service.py`) with safe path traversal resolution.
    - [x] Preserved 1-indexed sequential page lineage and blank pages.
    - [x] Implemented block-level layout extraction and conservative heading candidate heuristics.
    - [x] Added scanned / image-only PDF detection (`is_scanned: True`, `extraction_status: "scanned_requires_ocr"`).
    - [x] Encrypted / password-protected PDF rejection without cracking.
    - [x] Synchronous extraction endpoint: `POST /contracts/{contract_id}/extract` (and `/api/v1` alias).
    - [x] Updates `Contract.page_count` in Neon PostgreSQL; zero schema migrations required.
    - [x] 19 comprehensive unit and integration tests in `backend/tests/test_pdf_extraction.py` (100 total backend tests passing).
  - [x] **Phase 3B: Text Normalization & Clause-Aware Chunking Pipeline** *(Completed)*
    - [x] Defined strongly typed Pydantic v2 chunk schemas (`ChunkBase`, `ChunkCreate`, `ChunkResponse`, `ContractChunkingResponse`, `ContractChunkListResponse`, `DocumentChunkSummary`).
    - [x] Conservative, non-destructive text normalization service (`text_normalization_service.py`) supporting NFKC ligature resolution, safe soft-hyphen/line-break healing, CRLF/blank line collapse, and uppercase/number/currency preservation.
    - [x] Deterministic clause-aware chunking engine (`chunking_service.py`) with legal section/article/clause detection and cross-page header propagation.
    - [x] Page-bounded chunk construction with 1-indexed `page_number` and contiguous global `chunk_index`.
    - [x] Accurate `char_start` and `char_end` tracking relative to normalized page text.
    - [x] Atomic and idempotent database persistence to `document_chunks` table with `embedding=None`.
    - [x] REST API endpoints `POST /contracts/{id}/chunk` and `GET /contracts/{id}/chunks` with `/api/v1` versioned aliases.
    - [x] Zero database migrations required; fully compatible with initial schema.
    - [x] 32 comprehensive unit and integration tests in `backend/tests/test_chunking.py` (132 total backend tests passing).
- [x] **Phase 4A: Embedding Provider Abstraction** *(Completed)*
  - [x] Pinned modern, compatible dependency: `google-genai==2.23.0` in `backend/requirements.txt`.
  - [x] Extended `Settings` safely with `gemini_api_key`, `embedding_model="gemini-embedding-2"`, `embedding_dimension=768`, and `embedding_batch_size=100`.
  - [x] Implemented credential hygiene with masked summary property (`safe_gemini_key_summary`), preventing raw secrets or API keys in logs/exceptions.
  - [x] Implemented `EmbeddingProvider` abstract base class and `EmbeddingTaskType` enum (`RETRIEVAL_DOCUMENT`, `RETRIEVAL_QUERY`).
  - [x] Implemented concrete `GeminiEmbeddingProvider` using official `google.genai` SDK with `output_dimensionality=768`.
  - [x] Built `get_embedding_provider` factory for clean, interview-defensible dependency injection.
  - [x] Enforced strict input/output validation, sequential batching (default 100 items), and $N \to N$ ordering preservation.
  - [x] Implemented 23 comprehensive mocked unit tests in `backend/tests/test_embedding_provider.py` (100% mocked, 0 real API calls, 0 secrets).
  - [x] Zero database migrations, zero schema changes, zero premature background queues.
- [x] **Phase 4B: Document Chunk Embedding & pgvector Persistence** *(Completed)*
  - [x] Defined strongly typed Pydantic v2 embedding schemas (`ContractEmbedRequest`, `ContractEmbeddingResponse`).
  - [x] Built standalone embedding generation service (`embedding_generation_service.py`) using `EmbeddingProvider` and `get_embedding_provider`.
  - [x] Enforced strict 1-to-1 chunk-to-embedding mapping and index ordering (`order_by(DocumentChunk.chunk_index.asc())`).
  - [x] Implemented idempotent execution: skips chunks with `embedding IS NOT NULL` when `force_reembed=False`, re-embeds all when `force_reembed=True`.
  - [x] Strict 768-dimensional output validation prior to persistence.
  - [x] Atomic persistence: single per-contract commit; automatic `db.rollback()` on provider or validation failure.
  - [x] REST API endpoints `POST /contracts/{contract_id}/embed` and `/api/v1/contracts/{contract_id}/embed`.
  - [x] Zero database migrations required; preserves existing schema and untyped `Vector` column.
  - [x] 13 comprehensive unit/integration tests in `backend/tests/test_embedding_generation.py` (100% mocked, zero real API keys/calls).
- [x] **Phase 4C: Vector Column Typing, Indexing & Retrieval Preparation** *(Completed)*
  - [x] Configured `DocumentChunk.embedding` model to use `Vector(768)` linking to `settings.embedding_dimension`.
  - [x] Created Alembic migration `18338ecd31a9_typed_vector_and_hnsw_index` altering column from untyped vector to `vector(768)`.
  - [x] Preserved `nullable=True` to support un-embedded chunks.
  - [x] Created HNSW index `idx_document_chunks_embedding_hnsw` on `document_chunks` using `vector_cosine_ops` with pgvector defaults (`m=16, ef_construction=64`).
  - [x] Implemented and verified safe, reversible downgrade path reverting column to untyped vector and dropping HNSW index.
  - [x] Implemented 8 focused schema and database tests in `backend/tests/test_vector_schema.py` verifying model definition, database catalog type, HNSW index metadata, nullability, 768-dim vector persistence, and dimension mismatch rejection.
  - [x] All 176 backend tests passing against live Neon PostgreSQL (100% pass rate).
  - [x] Semantic retrieval strictly deferred to Phase 5A; zero search or retrieval endpoints introduced.
- [ ] **Phase 5: Hybrid Search & Semantic Retrieval Engine**
  - [x] **Phase 5A: Semantic Vector Retrieval Engine** *(Completed)*
    - [x] Defined strongly typed Pydantic v2 schemas (`ContractQueryRequest`, `ChunkMatch`, `ContractQueryResponse`).
    - [x] Reused `EmbeddingProvider.embed_query()` with `task_type=RETRIEVAL_QUERY` producing 768-dim query vectors.
    - [x] Built standalone `retrieval_service.py` with `query_contract_chunks()` executing pgvector cosine distance queries (`<=>`).
    - [x] Exact mathematical mapping: `similarity_score = 1.0 - cosine_distance`.
    - [x] Enforced strict contract scoping (`DocumentChunk.contract_id == contract_id`) and NULL embedding exclusion.
    - [x] Bounded `top_k` (`ge=1, le=20`, default `5`) and optional `min_similarity` filtering.
    - [x] REST API endpoints `POST /contracts/{contract_id}/query` and `/api/v1/contracts/{contract_id}/query`.
    - [x] 18 comprehensive unit and integration tests in `backend/tests/test_vector_retrieval.py` (100% mocked, 0 real Gemini API calls).
    - [x] Zero database migrations, zero schema changes, zero premature background queues.
  - [x] **Phase 5B: Keyword Full-Text Retrieval Engine** *(Completed)*
    - [x] Added stored generated `search_vector` column to `DocumentChunk` (`to_tsvector('english', text)`).
    - [x] Created Alembic migration `fd983c1fd05f_add_search_vector_and_gin_index` with GIN indexing.
    - [x] Defined Pydantic v2 schemas (`ContractKeywordQueryRequest`, `KeywordChunkMatch`, `ContractKeywordQueryResponse`).
    - [x] Implemented standalone `keyword_retrieval_service.py` with `query_contract_keywords()`.
    - [x] Safe natural language search parsing via `websearch_to_tsquery('english', query)`.
    - [x] Relevance scoring via Cover Density ranking (`ts_rank_cd`).
    - [x] Enforced strict contract scoping (`DocumentChunk.contract_id == contract_id`).
    - [x] Bounded `top_k` (`ge=1, le=20`, default 5) and clean empty responses for no-match queries.
    - [x] REST API endpoints `POST /contracts/{contract_id}/keyword-query` and `/api/v1/contracts/{contract_id}/keyword-query`.
    - [x] 14 comprehensive unit and integration tests in `backend/tests/test_keyword_retrieval.py` (100% pass rate against live Neon PostgreSQL).
    - [x] Verified zero regressions on Phase 5A vector retrieval (18/18 passed).
  - [x] **Phase 5C: Hybrid Retrieval Fusion & RRF** *(Completed)*
    - [x] Defined Pydantic v2 schemas (`ContractHybridQueryRequest`, `HybridChunkMatch`, `ContractHybridQueryResponse`).
    - [x] Implemented standalone `hybrid_retrieval_service.py` combining Phase 5A vector similarity and Phase 5B keyword retrieval.
    - [x] Applied standard Reciprocal Rank Fusion (RRF) formula: `score = sum(1.0 / (k + rank))` with fixed smoothing constant `k = 60`.
    - [x] Deduplicated chunks appearing in both retrieval paths with combined RRF scores and transparent rank/score provenance.
    - [x] Preserved full chunk metadata (`page_number`, `chunk_index`, `section_header`, `char_start`, `char_end`, `text`).
    - [x] Enforced strict contract scoping (`DocumentChunk.contract_id == contract_id`).
    - [x] Handled empty result sets gracefully without failure (semantic-only, keyword-only, both-empty).
    - [x] Zero vector embedding leakage in responses.
    - [x] REST API endpoints `POST /contracts/{contract_id}/hybrid-query` and `/api/v1/contracts/{contract_id}/hybrid-query`.
    - [x] 22 comprehensive unit, integration, and API tests in `backend/tests/test_hybrid_retrieval.py` (100% pass rate).
    - [x] Verified zero regressions on Phase 5A vector retrieval and Phase 5B keyword retrieval endpoints.
  - [x] **Phase 5D: Retrieval Evaluation & Benchmarking** *(Completed)*
    - [x] Implemented standard IR ranking metrics (`backend/app/evaluation/metrics.py`): Precision@K, Recall@K, and MRR@K.
    - [x] Version-controlled benchmark dataset in JSON (`backend/app/evaluation/data/retrieval_eval_dataset.json`) with enterprise MSA chunks and test queries.
    - [x] Strongly typed Pydantic dataset schemas and loader (`backend/app/evaluation/dataset.py`).
    - [x] Deterministic evaluation runner (`backend/app/evaluation/evaluator.py`) benchmarking semantic, keyword, and hybrid retrieval paths without live Gemini API calls using orthogonal unit vectors.
    - [x] Multi-cutoff evaluation ($K \in [1, 3, 5]$) and audit-ready markdown summary reporting.
    - [x] 10 unit and integration tests in `backend/tests/test_retrieval_evaluation.py` (100% pass rate).
- [ ] **Phase 6: Structured Output, Extraction & Intelligence Engine**
  - [x] **Phase 6A: Structured Output Infrastructure** *(Completed)*
    - [x] Defined vendor-independent `StructuredLLMProvider` abstract base class with async `generate_structured`.
    - [x] Created `structured_output_validator.py` with custom exception hierarchy (`StructuredOutputError`, `StructuredOutputConfigurationError`, `StructuredOutputProviderError`, `StructuredOutputParseError`, `StructuredOutputValidationError`).
    - [x] Implemented defensive JSON normalization and markdown code fence stripping (`clean_json_text`).
    - [x] Implemented strict Pydantic model validation (`validate_structured_output`) with structured field-level error reporting.
    - [x] Implemented `GeminiStructuredOutputProvider` using official `google-genai` SDK and `types.GenerateContentConfig(response_mime_type="application/json", response_schema=...)`.
    - [x] Built `get_structured_llm_provider` factory with dependency injection support (`client: genai.Client | None`).
    - [x] Extended `Settings` with `llm_provider`, `llm_model="gemini-3.8-flash"` (updated from `gemini-2.5-flash`), `llm_temperature=0.0`, and updated `.env.example`.
    - [x] Exported all structured output classes, functions, and exceptions from `backend/app/services/__init__.py`.
    - [x] 25 comprehensive unit and integration tests in `backend/tests/test_structured_output.py` (100% mocked, 0 real API calls, 100% pass rate).
  - [x] **Phase 6B: Structured Clause Extraction** *(Completed)*
    - [x] Defined Pydantic v2 schemas (`ClauseType`, `ExtractedClauseLLM`, `ChunkClauseExtractionResult`, `ClauseResponse`, `ContractClauseExtractionResponse`, `ContractClauseListResponse`).
    - [x] Implemented standalone `clause_extraction_service.py` using `StructuredLLMProvider` and Phase 6A validation.
    - [x] Processed contract document chunks deterministically in sequential order (`chunk_index.asc()`).
    - [x] Preserved strict source evidence traceability: clause → chunk → page → contract.
    - [x] Idempotent persistence into `clauses` database table (skips existing unless `force_reextract=True`).
    - [x] Added REST API endpoints `POST /contracts/{contract_id}/extract-clauses` and `GET /contracts/{contract_id}/clauses` (with versioned `/api/v1` aliases).
    - [x] 13 comprehensive unit and integration tests in `backend/tests/test_clause_extraction.py` (100% pass rate).
  - [x] **Phase 6C: Structured Obligation Extraction** *(Completed)*
    - [x] Defined Pydantic v2 obligation extraction schemas (`ObligationType`, `ExtractedObligationLLM`, `ClauseObligationExtractionResult`, `ObligationBase`, `ObligationResponse`, `ContractObligationExtractionRequest`, `ContractObligationExtractionResponse`, `ContractObligationListResponse`).
    - [x] Extended `Obligation` database model with `obligation_type`, `deadline_info`, and `extraction_confidence`.
    - [x] Created and verified reversible Alembic migration `c82e75f1b94a_add_obligation_type_and_deadline_info` on Neon PostgreSQL.
    - [x] Implemented standalone `obligation_extraction_service.py` extracting obligations from extracted clauses using Phase 6A `StructuredLLMProvider`.
    - [x] Preserved strict 5-tier source evidence traceability: obligation → clause → chunk → page → contract.
    - [x] Implemented idempotent persistence (skips existing records unless `force_reextract=True`).
    - [x] Robust error handling against malformed or missing structured LLM outputs.
    - [x] Added REST API endpoints `POST /contracts/{contract_id}/extract-obligations` and `GET /contracts/{contract_id}/obligations` (with versioned `/api/v1` aliases).
    - [x] 13 comprehensive unit and integration tests in `backend/tests/test_obligation_extraction.py` (100% pass rate).
  - [x] **Phase 6D: Structured Contract Fact Extraction** *(Completed)*
    - [x] Defined Pydantic v2 schemas (`FactKey`, `ExtractedFactLLM`, `ClauseFactExtractionResult`, `ContractFactBase`, `ContractFactResponse`, `ContractFactExtractionRequest`, `ContractFactExtractionResponse`, `ContractFactListResponse`).
    - [x] Implemented standalone `contract_fact_service.py` extracting contract-level facts (effective date, expiration date, contract value, payment terms, currency, parties, governing law, notice period, renewal term, termination notice period, liability cap, etc.) using Phase 6A `StructuredLLMProvider`.
    - [x] Preserved strict 5-tier evidence lineage: `fact → source clause → chunk → page → contract`.
    - [x] Implemented database persistence with `contract_facts` table and Alembic migration `e41a982f63cb_add_contract_facts_table`.
    - [x] Implemented idempotency (returns existing facts on rerun unless `force_reextract=True`).
    - [x] Added REST API endpoints `POST /contracts/{contract_id}/extract-facts` and `GET /contracts/{contract_id}/facts` (with versioned `/api/v1` aliases).
    - [x] 13 comprehensive unit and integration tests in `backend/tests/test_contract_fact_extraction.py` (100% pass rate).
  - [ ] **Phase 6E: Deterministic Risk Rules & Risk Signals**
    - [ ] Implementation of deterministic business risk rules (notice period thresholds, uncapped liability, auto-renewal deadlines).
    - [ ] Generation and database persistence of `RiskSignal` records.
- [ ] **Phase 7: Evidence Architecture, API & Frontend Integration**
  - [x] **Phase 7A: Persistent Evidence Model & Lineage Architecture** *(Completed)*
    - [x] Implemented source-oriented immutable `Evidence` model (`backend/app/models/evidence.py`).
    - [x] Applied Alembic migration `a71f49b1a03e_add_evidence_table` with check constraints and indexes.
    - [x] Enforced 6-tier evidence lineage: `evidence → source item → clause → chunk → page → contract`.
    - [x] Enforced immutability via `before_update` listener.
    - [x] 16 tests in `backend/tests/test_evidence_model.py` passing.
  - [x] **Phase 7B: Evidence API & Lineage Retrieval** *(Completed)*
    - [x] Service layer in `backend/app/services/evidence_service.py` (`create_evidence`, `get_evidence_by_id`, `list_contract_evidence`, `get_evidence_lineage`, `list_evidence_lineage`).
    - [x] REST endpoints: `POST /contracts/{contract_id}/evidence`, `GET /contracts/{contract_id}/evidence`, `GET /contracts/{contract_id}/evidence/{evidence_id}`, `GET /contracts/{contract_id}/evidence/lineage`, `GET /contracts/{contract_id}/evidence/{evidence_id}/lineage` (with `/api/v1` aliases).
    - [x] Filtering support: `source_item_type`, `source_item_id`, and `page_number`.
  - [x] **Phase 7C: Deterministic Evidence Validation Service** *(Completed)*
    - [x] Deterministic validation in `backend/app/services/evidence_service.py` (`validate_single_evidence`, `validate_contract_evidence`).
    - [x] Verifies contract ownership, source item presence, structural clause/chunk integrity, page consistency, verbatim text matching, and character span bounds.
    - [x] Detects invalid, missing, broken lineage, or stale evidence.
    - [x] REST endpoint: `POST /contracts/{contract_id}/evidence/validate` (with `/api/v1` alias).
    - [x] 8 comprehensive unit/integration tests in `backend/tests/test_evidence_api_and_validation.py` (100% pass rate).
  - [ ] **Phase 7D: Frontend Integration & Live API Wiring**
    - [ ] Replacement of static mock data with API client services.
    - [ ] Upload wizard connection to backend ingestion pipeline.
    - [ ] Implementation of missing `/analyst` (AI chat with citation panel) and `/audit` pages.
    - [ ] Interactive source citation highlighting (click citation -> navigate to page view).
- [x] **Phase 8: Contract Risk Engine & Risk API (Phase 8A–8D)** *(Completed)*
  - [x] **Phase 8A: Deterministic Risk Rule Framework** *(Completed)*
    - [x] Modular architecture (`BaseRiskRule`, `ContractEvaluationContext`, `RiskRuleOutput`, `evaluate_contract_rules`).
    - [x] Context ingestion over structured contract facts, clauses, obligations, and chunks.
    - [x] Absolute prohibition on LLM severity/trigger decision-making.
    - [x] Zero false positives: rules never fire or hallucinate when contractual facts are missing.
  - [x] **Phase 8B: Renewal Rules** *(Completed)*
    - [x] `RULE_CONTRACT_EXPIRED`: flags passed expiration dates as critical.
    - [x] `RULE_CONTRACT_EXPIRING_SOON`: flags contracts expiring within 60 days (high <= 30d, medium <= 60d).
    - [x] `RULE_AUTO_RENEWAL_ACTIVE`: flags agreements renewing automatically without active cancellation.
    - [x] `RULE_AUTO_RENEWAL_SHORT_NOTICE`: flags notice windows <= 30 days in auto-renewing agreements.
  - [x] **Phase 8C: Contract Risk Rules** *(Completed)*
    - [x] `RULE_TERMINATION_NOTICE_SHORT`: flags termination notice periods <= 15 days.
    - [x] `RULE_UNCAPPED_LIABILITY`: flags uncapped aggregate liability or broad liability carveouts.
    - [x] `RULE_BROAD_INDEMNIFICATION`: flags uncapped or broad indemnification obligations.
    - [x] `RULE_MISSING_GOVERNING_LAW`: flags agreements lacking governing law or jurisdiction.
    - [x] `RULE_HIGH_PRIORITY_OVERDUE_OBLIGATION`: flags unfulfilled high-priority obligations past due.
    - [x] Strict 6-tier evidence lineage: `risk → rule → structured fact/clause/obligation → evidence → chunk → page → contract`.
  - [x] **Phase 8D: Risk API & Idempotent Persistence** *(Completed)*
    - [x] Service layer in `backend/app/services/risk_service.py` (`evaluate_and_persist_contract_risks`, `list_contract_risk_signals`).
    - [x] Idempotent evaluation: returns existing signals without duplication unless `force_reevaluate=True`.
    - [x] REST endpoints: `POST /contracts/{contract_id}/risks/evaluate` and `GET /contracts/{contract_id}/risks` (with `/api/v1` aliases).
    - [x] Filtering support: `severity` (`critical`, `high`, `medium`, `low`) and `category` (`renewal`, `termination`, `liability`, etc.).
- [x] **Phase 9: Grounded RAG Generation & Citation Validation (Phase 9A–9E)** *(Completed)*
  - [x] **Phase 9A: Grounded Context Construction** *(Completed)*
    - [x] Context formatter (`build_grounded_context`) assembling retrieved hybrid chunks with page metadata and section headers.
    - [x] Strict bounding (`max_chars` parameter) preserving deterministic chunk ordering and metadata provenance.
  - [x] **Phase 9B: Grounded LLM Generation** *(Completed)*
    - [x] Structured output contract question-answering with `StructuredLLMProvider` using `StructuredRAGAnswerLLM`.
    - [x] Temperature 0.0 with strict system instruction to answer ONLY from supplied evidence.
    - [x] Explicit `has_sufficient_evidence=False` when evidence is missing or insufficient.
  - [x] **Phase 9C: Citation Lineage Assembly** *(Completed)*
    - [x] Every factual claim mapped to explicit supporting citations (`RAGCitation`).
    - [x] Complete lineage preserved: `answer → claim → citation/evidence → chunk → page → contract`.
  - [x] **Phase 9D: Deterministic Citation Verification** *(Completed)*
    - [x] `verify_citation` service validating contract ownership, page number match, chunk existence, and verbatim substring presence.
    - [x] Flags citations as `verified`, `text_mismatch`, `page_mismatch`, `chunk_not_found`, or `unsupported`.
  - [x] **Phase 9E: Not-Found Handling & Confidence Gating** *(Completed)*
    - [x] Pre-LLM confidence gate checking retrieval match count and minimum RRF score threshold.
    - [x] Safe deterministic not-found response without LLM invocation when evidence is absent or below threshold.
    - [x] REST endpoint `POST /contracts/{contract_id}/query/grounded` (and `/api/v1` alias).
    - [x] 9 comprehensive unit and integration tests in `backend/tests/test_grounded_rag.py` (100% pass rate).
- [x] **Phase 10: AI Analyst API & Multi-Contract RAG (Phase 10A–10E)** *(Completed)*
  - [x] **Phase 10A: Analyst API Foundation** *(Completed)*
    - [x] Dedicated service layer in `backend/app/services/analyst_service.py` built on grounded RAG pipeline.
    - [x] Pydantic v2 schemas in `backend/app/schemas/analyst.py` (`AnalystQueryResponse`, `SingleContractAnalystRequest`, `CrossContractAnalystRequest`).
    - [x] Exception handling wrapping provider and scoping errors (`AnalystServiceError`, `ContractScopingError`).
  - [x] **Phase 10B: Single-Contract Questions** *(Completed)*
    - [x] Natural language questions against a single contract (`ask_contract_analyst_single`).
    - [x] Hybrid retrieval -> bounded context -> structured LLM generation -> citation validation.
  - [x] **Phase 10C: Cross-Contract Multi-Document Questions** *(Completed)*
    - [x] Multi-contract comparative question-answering (`ask_contract_analyst_cross`) across 2 to 10 contracts.
    - [x] Strict per-contract scoping, distinct section headers, and zero evidence bleeding across contracts.
  - [x] **Phase 10D: Evidence-Backed Responses** *(Completed)*
    - [x] Every factual claim mapped to verified citations (`AnalystEvidenceCitation`) preserving 6-tier lineage: `answer → claim → evidence → chunk → page → contract`.
    - [x] Deterministic validation detecting text mismatches, wrong-contract chunks, and unsupported claims.
  - [x] **Phase 10E: Retrieval & Debug Metadata** *(Completed)*
    - [x] Optional retrieval debug metadata (`include_debug=True`) returning method, selected chunks with ranks/scores, context char count, and timing.
    - [x] Zero exposure of vector embeddings or credentials.
    - [x] REST endpoints: `POST /analyst/query`, `POST /analyst/contracts/{contract_id}/query`, and `POST /analyst/query/cross` (with `/api/v1` aliases).
    - [x] 10 comprehensive unit and integration tests in `backend/tests/test_analyst_api.py` (100% pass rate).
- [x] **Phase 11: Cross-Contract Comparison API (Phase 11A–11E)** *(Completed)*
  - [x] **Phase 11A: Comparison API Foundation** *(Completed)*
    - [x] Strongly typed Pydantic v2 schemas in `backend/app/schemas/comparison.py` (`ContractComparisonRequest`, `ContractComparisonResponse`, `FieldComparisonRow`, `DeterministicFieldDifference`, `ObligationComparisonItem`).
    - [x] Standalone service layer in `backend/app/services/comparison_service.py` with custom exception handling (`ComparisonServiceError`, `ComparisonScopingError`).
    - [x] REST API endpoints: `POST /contracts/compare` and `GET /contracts/compare` (with versioned `/api/v1` aliases).
  - [x] **Phase 11B: Structured Cross-Contract Comparison** *(Completed)*
    - [x] Multi-contract side-by-side comparison across 2 to 10 contracts using already-extracted `ContractFact`, `Obligation`, `Clause`, and `Contract` metadata.
    - [x] Compared fields include contract value, notice period, payment terms, renewal terms, liability caps, governing law, and key obligations.
    - [x] Missing or unavailable terms clearly distinguished (`is_available=False`, `MISSING_FIELD`) without hallucination or default guessing.
  - [x] **Phase 11C: Evidence-Backed Comparison & Lineage Audit** *(Completed)*
    - [x] Every compared field value includes full 6-tier evidence lineage: `comparison → fact/obligation/clause → chunk → page → contract`.
    - [x] Lineage verification strictly validates contract ownership and flags foreign contract chunks with `LineageStatus.WRONG_CONTRACT`.
  - [x] **Phase 11D: Deterministic Variance & Difference Analysis** *(Completed)*
    - [x] 100% code-based deterministic variance calculation for financial sums, day durations, and text mismatches.
    - [x] Identifies min/max contracts, percentage variance from baseline, absolute delta, and severity (`HIGH`, `MEDIUM`, `LOW`, `INFO`).
    - [x] Zero real LLM or external API calls required for comparison.
  - [x] **Phase 11E: REST API Endpoints & Contract Scoping Enforcement** *(Completed)*
    - [x] Rejection of fewer than 2 or greater than 10 contract IDs, duplicate IDs, and non-existent IDs.
    - [x] 7 comprehensive unit, integration, and API tests in `backend/tests/test_comparison_api.py` (100% pass rate against live Neon PostgreSQL).
- [x] **Phase 12: Obligation API & Deterministic Analysis (Phase 12A–12E)** *(Completed)*
  - [x] **Phase 12A: Obligation API Foundation** *(Completed)*
    - [x] Built dedicated service layer in `backend/app/services/obligation_service.py` and Pydantic v2 schemas in `backend/app/schemas/obligation_api.py`.
    - [x] Strongly typed responses and structured domain exceptions (`ObligationServiceError`, `ContractNotFoundError`, `ObligationNotFoundError`, `ObligationScopingError`).
  - [x] **Phase 12B: Obligation Listing & Multi-Facet Filtering** *(Completed)*
    - [x] Contract-scoped obligation retrieval with filtering by responsible party, obligation type, tracking status, priority, recurrence, and due date boundaries.
    - [x] Zero invention of missing obligation fields or hallucinated dates.
  - [x] **Phase 12C: Obligation Evidence & Lineage Verification** *(Completed)*
    - [x] Assembled complete 6-tier evidence lineage: `obligation → clause → chunk → page → contract`.
    - [x] Deterministic validation detecting and flagging `WRONG_CONTRACT`, `CHUNK_NOT_FOUND`, `PAGE_MISMATCH`, and `TEXT_MISMATCH`.
  - [x] **Phase 12D: Deterministic Obligation Analysis** *(Completed)*
    - [x] Pure code calculations for derived status: `is_overdue`, `days_until_due`, standard cadence representation, and extraction confidence tier.
    - [x] Aggregate analysis metrics: breakdowns by party, type, status, priority, recurrence counts, overdue/upcoming counts, and lineage integrity summary.
    - [x] Zero LLM calls in analysis pipeline (100% deterministic).
  - [x] **Phase 12E: REST API & Contract Scoping Enforcement** *(Completed)*
    - [x] REST API endpoints: `GET /contracts/{contract_id}/obligations/query`, `POST /contracts/{contract_id}/obligations/query`, and `GET /contracts/{contract_id}/obligations/{obligation_id}` (with `/api/v1` aliases).
    - [x] Strict contract scoping enforcement: nonexistent contracts return 404, cross-contract obligation access returns 404.
    - [x] 10 comprehensive unit, integration, and API tests in `backend/tests/test_obligation_api.py` (100% pass rate).
- [x] **Phase 13: Authentication & Authorization (Phase 13A–13E)** *(Completed)*
  - [x] **Phase 13A: Authentication Foundation** *(Completed)*
    - [x] Stateless JWT access tokens signed with HMAC-SHA256 (`HS256`).
    - [x] Cryptographically salted password hashing using standard library PBKDF2-HMAC-SHA256 (600,000 rounds, 16-byte random salt).
    - [x] Strongly typed Pydantic v2 schemas (`UserRegisterRequest`, `UserLoginRequest`, `TokenResponse`, `UserResponse`, `TokenPayload`).
    - [x] Zero plain-text credentials stored or exposed in logs/responses. Safe `.env.example` templates.
  - [x] **Phase 13B: User & Account Management** *(Completed)*
    - [x] Alembic migration `e911249325b6_add_hashed_password_to_users` applied to live Neon database with verified reversibility.
    - [x] User registration (`POST /auth/register`) with duplicate email detection (HTTP 409 Conflict).
    - [x] User login (`POST /auth/login`) with credential verification (HTTP 401 Unauthorized).
  - [x] **Phase 13C: Authorization & Ownership Enforcement** *(Completed)*
    - [x] FastAPI dependencies `get_current_user` and `get_current_user_optional` for Bearer token extraction and claim verification.
    - [x] Deterministic ownership verification guard `verify_contract_access` enforcing `Contract.uploaded_by == user.id` (IDOR prevention, HTTP 403 Forbidden).
    - [x] Full administrative bypass for `admin` role across all contracts.
  - [x] **Phase 13D: Protected API Surface** *(Completed)*
    - [x] Contract CRUD routes integrated with user association and ownership verification.
    - [x] User profile endpoint `GET /auth/me` returning sanitized public profile.
    - [x] Public health endpoint `GET /health` remains unauthenticated.
  - [x] **Phase 13E: Security & Comprehensive Test Suite** *(Completed)*
    - [x] Error handling for expired tokens (`TokenExpiredError`), malformed tokens, and tampered signatures (`TokenError`).
    - [x] 6 comprehensive unit, integration, and IDOR protection tests in `backend/tests/test_auth_and_ownership.py` (100% pass rate).
- [x] **Phase 14: Frontend Integration & Application Shell (Phase 14A–14H)** *(Completed)*
  - [x] **Phase 14A: API Client Foundation** *(Completed)*
    - [x] Implemented typed frontend API client with fetch wrapper in `src/api/client.ts`.
    - [x] Centralized base URL configuration, JWT Bearer header injection, and standardized error handling (`ApiError`).
    - [x] Zero credential leakage or hardcoded secrets.
  - [x] **Phase 14B: Authentication UI** *(Completed)*
    - [x] Built dedicated `Login.tsx` and `Register.tsx` pages with enterprise form validation and error handling.
    - [x] Created `AuthContext.tsx` with user state, token persistence in localStorage, session expiry event listeners, and logout.
  - [x] **Phase 14C: Protected Application Shell** *(Completed)*
    - [x] Protected route wrapper `ProtectedRoute.tsx` redirecting unauthenticated users to `/login`.
    - [x] Dynamic user profile display (initials, name, role) and logout action in `Sidebar.tsx`.
  - [x] **Phase 14D: Contract API Integration** *(Completed)*
    - [x] Integrated `Contracts.tsx` and `ContractOverview.tsx` with live `contractsApi.list` and `contractsApi.get`.
    - [x] Connected `UploadContract.tsx` to live backend contract creation, PDF upload, extraction, chunking, and risk evaluation endpoints.
  - [x] **Phase 14E: Analyst / RAG Integration** *(Completed)*
    - [x] Built `Analyst.tsx` connected to Phase 10 `analystApi.query`.
    - [x] Multi-contract selection (1 to 10 contracts), grounded answers, verified factual claims with citation indices, and optional retrieval debug panel.
  - [x] **Phase 14F: Comparison & Obligation Integration** *(Completed)*
    - [x] Integrated `Compare.tsx` with Phase 11 `comparisonApi.compare`.
    - [x] Integrated `Obligations.tsx` with Phase 12 `obligationsApi.query`.
  - [x] **Phase 14G: Risk & Dashboard Integration** *(Completed)*
    - [x] Connected `RiskMonitor.tsx` and `Dashboard.tsx` with live contract signals and portfolio metrics.
  - [x] **Phase 14H: Frontend Reliability & UX** *(Completed)*
    - [x] Fixed unrouted sidebar links by mounting `/analyst` and `/audit` in `App.tsx`.
    - [x] Verified zero TypeScript compilation errors (`npx tsc --noEmit`) and clean production build (`npm run build`).
- [ ] **Phase 15: Evaluation, End-to-End Testing & Production Hardening**

---

## 3. Known Issues & Technical Debt (Discovered in Phase 0 Audit)

1. **Unrouted Sidebar & Header Links:**
   - The Sidebar and Header declare links to `/analyst` ("AI Analyst") and `/audit` ("Audit Log"), and `ContractOverview.tsx` has an "Ask AI Analyst" button targeting `/analyst`.
   - `src/App.tsx` has no route definitions for these paths; clicking them triggers the wildcard redirect to `/`.
2. **Local Mock Clauses Disconnected from Global Mock:**
   - `src/pages/ContractOverview.tsx` defines a local constant `sampleClauses` rather than retrieving contract-specific clauses from `src/data/mock.ts`.
3. **Hardcoded KPI Counters on Dashboard:**
   - The primary metrics in `src/pages/Dashboard.tsx` (Total Contracts: 42, Active Obligations: 86, High Risk Contracts: 7, Upcoming Renewals: 5) are hardcoded string literals rather than computed dynamically from `contracts`, `risks`, and `obligations`.
4. **No State Persistence:**
   - User interactions such as "Upload Contract", "Mark Reviewed", or "Mark Complete" are simulated only in client UI state and reset upon page refresh.
5. **No Unit or E2E Testing Framework:**
   - `package.json` contains no test runner (e.g. Vitest, Jest, Playwright).
6. **Package Name Artifact:**
   - `package.json` retains the scaffold name `"figma-make-app"` rather than `"contractiq"`.

---

## 4. Verification History

| Date | Verification Step | Command | Result |
| :--- | :--- | :--- | :--- |
| 2026-09-12 | Frontend Build | `npm run build` | **PASSED** (built in 209ms, 0 errors) |
| 2026-09-12 | TypeScript Typecheck | `npx tsc --noEmit` | **PASSED** (0 errors) |
| 2026-09-12 | Live Neon DB Connection | `check_database_connection()` | **PASSED** (PostgreSQL 18.6, pgvector 0.8.6 verified) |
| 2026-09-12 | Alembic Schema Migration | `alembic upgrade head` | **PASSED** (applied revision `df2c477aaabb_initial_schema`) |
| 2026-09-12 | Live Neon Schema Audit | `information_schema.tables` | **PASSED** (all 7 application tables, 12 foreign keys, and vector column verified) |
| 2026-09-12 | Complete Backend Test Suite | `pytest tests/ -v` | **PASSED** (48 passed, 0 skipped, live DB health test verified) |
| 2026-09-12 | Git Safety & Secrets Audit | `git check-ignore backend/.env` | **PASSED** (`backend/.env` is untracked & ignored, secrets safe) |
| 2026-09-12 | Phase 2A Contract API Tests | `pytest tests/test_contracts_api.py -v` | **PASSED** (12 passed, 0 skipped against Neon PostgreSQL) |
| 2026-09-12 | Full Suite Verification (Phase 2A) | `pytest tests/ -v` | **PASSED** (60 passed, 0 skipped against Neon PostgreSQL) |
| 2026-09-12 | Frontend Build (Phase 2A Check) | `npm run build` | **PASSED** (built in 191ms, 0 errors) |
| 2026-09-12 | TypeScript Verification (Phase 2A Check) | `npx tsc --noEmit` | **PASSED** (0 errors) |
| 2026-09-12 | Phase 2B Contract Upload Tests | `pytest tests/test_contract_upload_api.py -v` | **PASSED** (11 passed, 0 skipped against Neon PostgreSQL) |
| 2026-09-12 | Full Suite Verification (Phase 2B) | `pytest tests/ -v` | **PASSED** (71 passed, 0 skipped against Neon PostgreSQL) |
| 2026-09-12 | Frontend Build (Phase 2B Check) | `npm run build` | **PASSED** (built in 235ms, 0 errors) |
| 2026-09-12 | TypeScript Verification (Phase 2B Check) | `npx tsc --noEmit` | **PASSED** (0 errors) |
| 2026-09-12 | Phase 2C Processing State Tests | `pytest tests/test_contract_processing_state.py -v` | **PASSED** (10 passed, 0 skipped against Neon PostgreSQL) |
| 2026-09-12 | Full Suite Verification (Phase 2C) | `pytest tests/ -v` | **PASSED** (81 passed, 0 skipped against Neon PostgreSQL) |
| 2026-09-12 | Frontend Build (Phase 2C Check) | `npm run build` | **PASSED** (built in 199ms, 0 errors) |
| 2026-09-12 | TypeScript Verification (Phase 2C Check) | `npx tsc --noEmit` | **PASSED** (0 errors) |
| 2026-09-12 | Phase 3A PDF Extraction Tests | `pytest tests/test_pdf_extraction.py -v` | **PASSED** (19 passed, 0 skipped against Neon PostgreSQL) |
| 2026-09-12 | Full Suite Verification (Phase 3A) | `pytest tests/ -v` | **PASSED** (100 passed, 0 skipped against Neon PostgreSQL) |
| 2026-09-12 | Frontend Build (Phase 3A Check) | `npm run build` | **PASSED** (built in 212ms, 0 errors) |
| 2026-09-12 | TypeScript Verification (Phase 3A Check) | `npx tsc --noEmit` | **PASSED** (0 errors) |
| 2026-09-12 | Phase 3B Chunking Tests | `pytest tests/test_chunking.py -v` | **PASSED** (32 passed, 0 skipped against Neon PostgreSQL) |
| 2026-09-12 | Full Suite Verification (Phase 3B) | `pytest tests/ -v` | **PASSED** (132 passed, 0 skipped against Neon PostgreSQL) |
| 2026-09-12 | Frontend Build (Phase 3B Check) | `npm run build` | **PASSED** (built in 427ms, 0 errors) |
| 2026-09-12 | TypeScript Verification (Phase 3B Check) | `npx tsc --noEmit` | **PASSED** (0 errors) |
| 2026-09-12 | Phase 4A Embedding Provider Tests | `pytest tests/test_embedding_provider.py -v` | **PASSED** (23 passed, 0 skipped, 100% mocked) |
| 2026-09-12 | Full Suite Verification (Phase 4A) | `pytest tests/ -v` | **PASSED** (155 passed, 0 skipped against Neon PostgreSQL) |
| 2026-09-12 | Frontend Build (Phase 4A Check) | `npm run build` | **PASSED** (built in 448ms, 0 errors) |
| 2026-09-12 | TypeScript Verification (Phase 4A Check) | `npx tsc --noEmit` | **PASSED** (0 errors) |
| 2026-09-12 | Phase 4B Embedding Generation Tests | `pytest tests/test_embedding_generation.py -v` | **PASSED** (13 passed, 0 skipped, 100% mocked) |
| 2026-09-12 | Full Suite Verification (Phase 4B) | `pytest tests/ -v` | **PASSED** (168 passed, 0 skipped against Neon PostgreSQL) |
| 2026-09-12 | Frontend Build (Phase 4B Check) | `npm run build` | **PASSED** (built in 472ms, 0 errors) |
| 2026-09-12 | TypeScript Verification (Phase 4B Check) | `npx tsc --noEmit` | **PASSED** (0 errors) |
| 2026-09-12 | Phase 4C Alembic Migration | `alembic upgrade head` | **PASSED** (applied revision `18338ecd31a9_typed_vector_and_hnsw_index`) |
| 2026-09-12 | Phase 4C Alembic Downgrade Reversibility | `alembic downgrade -1` & `upgrade head` | **PASSED** (reversibility verified on live Neon PostgreSQL) |
| 2026-09-12 | Phase 4C Vector Schema & HNSW Tests | `pytest tests/test_vector_schema.py -v` | **PASSED** (8 passed, 0 skipped against Neon PostgreSQL) |
| 2026-09-12 | Full Suite Verification (Phase 4C) | `pytest tests/ -v` | **PASSED** (176 passed, 0 skipped against Neon PostgreSQL) |
| 2026-09-12 | Frontend Build (Phase 4C Check) | `npm run build` | **PASSED** (built in 213ms, 0 errors) |
| 2026-09-12 | TypeScript Verification (Phase 4C Check) | `npx tsc --noEmit` | **PASSED** (0 errors) |
| 2026-09-12 | Phase 5A Vector Retrieval Tests | `pytest tests/test_vector_retrieval.py -v` | **PASSED** (18 passed, 0 skipped, 100% mocked) |
| 2026-09-12 | Python Bytecode Compilation (Phase 5A) | `python -m compileall app/` | **PASSED** (all modules compiled cleanly, 0 errors) |
| 2026-09-12 | Frontend Build (Phase 5A Check) | `npm run build` | **PASSED** (built in 449ms, 0 errors) |
| 2026-09-12 | TypeScript Verification (Phase 5A Check) | `npx tsc --noEmit` | **PASSED** (0 errors) |
| 2026-09-12 | Phase 5B Alembic Migration | `alembic upgrade head` | **PASSED** (applied revision `fd983c1fd05f_add_search_vector_and_gin_index`) |
| 2026-09-12 | Phase 5B Keyword Retrieval Tests | `pytest tests/test_keyword_retrieval.py -v` | **PASSED** (14 passed, 0 skipped against Neon PostgreSQL) |
| 2026-09-12 | Phase 5A Regression Verification | `pytest tests/test_vector_retrieval.py -v` | **PASSED** (18 passed, 0 skipped, 100% mocked) |
| 2026-09-12 | Python Bytecode Compilation (Phase 5B) | `python -m compileall app/` | **PASSED** (all modules compiled cleanly, 0 errors) |
| 2026-09-12 | Frontend Build (Phase 5B Check) | `npm run build` | **PASSED** (built in 435ms, 0 errors) |
| 2026-09-12 | TypeScript Verification (Phase 5B Check) | `npx tsc --noEmit` | **PASSED** (0 errors) |
| 2026-09-12 | Phase 5C Hybrid Retrieval Tests | `pytest tests/test_hybrid_retrieval.py -v` | **PASSED** (22 passed, 0 skipped against Neon PostgreSQL) |
| 2026-09-12 | Phase 5B Regression Verification | `pytest tests/test_keyword_retrieval.py -v` | **PASSED** (14 passed, 0 skipped against Neon PostgreSQL) |
| 2026-09-12 | Python Bytecode Compilation (Phase 5C) | `python -m compileall app/` | **PASSED** (all modules compiled cleanly, 0 errors) |
| 2026-09-12 | Frontend Build (Phase 5C Check) | `npm run build` | **PASSED** (built in 579ms, 0 errors) |
| 2026-09-12 | TypeScript Verification (Phase 5C Check) | `npx tsc --noEmit` | **PASSED** (0 errors) |
| 2026-09-12 | Phase 5D Retrieval Evaluation Tests | `pytest tests/test_retrieval_evaluation.py -v` | **PASSED** (10 passed, 0 skipped, 100% deterministic) |
| 2026-09-12 | Python Bytecode Compilation (Phase 5D) | `python -m compileall app/evaluation` | **PASSED** (all modules compiled cleanly, 0 errors) |
| 2026-09-12 | Frontend Build (Phase 5D Check) | `npm run build` | **PASSED** (built in 487ms, 0 errors) |
| 2026-09-12 | TypeScript Verification (Phase 5D Check) | `npx tsc --noEmit` | **PASSED** (0 errors) |
| 2026-09-13 | Phase 6A Structured Output Tests | `pytest tests/test_structured_output.py -v` | **PASSED** (25 passed, 0 skipped, 100% mocked) |
| 2026-09-13 | Phase 4A Regression Verification | `pytest tests/test_embedding_provider.py -v` | **PASSED** (23 passed, 0 skipped, 100% mocked) |
| 2026-09-13 | Python Bytecode Compilation (Phase 6A) | `python -m compileall app/` | **PASSED** (all modules compiled cleanly, 0 errors) |
| 2026-09-13 | Frontend Build (Phase 6A Check) | `npm run build` | **PASSED** (built in 463ms, 0 errors) |
| 2026-09-13 | TypeScript Verification (Phase 6A Check) | `npx tsc --noEmit` | **PASSED** (0 errors) |
| 2026-09-13 | Phase 6B Clause Extraction Tests | `pytest tests/test_clause_extraction.py -v` | **PASSED** (13 passed, 0 skipped against Neon PostgreSQL) |
| 2026-09-13 | Phase 6A Regression Verification | `pytest tests/test_structured_output.py -v` | **PASSED** (25 passed, 0 skipped, 100% mocked) |
| 2026-09-13 | Python Bytecode Compilation (Phase 6B) | `python -m compileall app/` | **PASSED** (all modules compiled cleanly, 0 errors) |
| 2026-09-13 | Frontend Build (Phase 6B Check) | `npm run build` | **PASSED** (built in 637ms, 0 errors) |
| 2026-09-13 | TypeScript Verification (Phase 6B Check) | `npx tsc --noEmit` | **PASSED** (0 errors) |
| 2026-09-13 | Phase 6C Alembic Migration | `alembic upgrade head` | **PASSED** (applied revision `c82e75f1b94a_add_obligation_type_and_deadline_info`) |
| 2026-09-13 | Phase 6C Alembic Downgrade Reversibility | `alembic downgrade -1` & `upgrade head` | **PASSED** (reversibility verified on live Neon PostgreSQL) |
| 2026-09-13 | Phase 6C Obligation Extraction Tests | `pytest tests/test_obligation_extraction.py -v` | **PASSED** (13 passed, 0 skipped against Neon PostgreSQL) |
| 2026-09-13 | Phase 6B Regression Verification | `pytest tests/test_clause_extraction.py -v` | **PASSED** (13 passed, 0 skipped against Neon PostgreSQL) |
| 2026-09-13 | Phase 6A Regression Verification | `pytest tests/test_structured_output.py -v` | **PASSED** (25 passed, 0 skipped, 100% mocked) |
| 2026-09-13 | Python Bytecode Compilation (Phase 6C) | `python -m compileall app/` | **PASSED** (all modules compiled cleanly, 0 errors) |
| 2026-09-13 | Frontend Build (Phase 6C Check) | `npm run build` | **PASSED** (built in 626ms, 0 errors) |
| 2026-09-13 | TypeScript Verification (Phase 6C Check) | `npx tsc --noEmit` | **PASSED** (0 errors) |
| 2026-09-13 | Phase 6D Alembic Migration | `alembic upgrade head` | **PASSED** (applied revision `e41a982f63cb_add_contract_facts_table`) |
| 2026-09-13 | Phase 6D Contract Fact Extraction Tests | `pytest tests/test_contract_fact_extraction.py -v` | **PASSED** (13 passed, 0 skipped against Neon PostgreSQL) |
| 2026-09-13 | Phase 6C Regression Verification | `pytest tests/test_obligation_extraction.py -v` | **PASSED** (13 passed, 0 skipped against Neon PostgreSQL) |
| 2026-09-13 | Phase 6B Regression Verification | `pytest tests/test_clause_extraction.py -v` | **PASSED** (13 passed, 0 skipped against Neon PostgreSQL) |
| 2026-09-13 | Phase 6A Regression Verification | `pytest tests/test_structured_output.py -v` | **PASSED** (25 passed, 0 skipped, 100% mocked) |
| 2026-09-13 | Python Bytecode Compilation (Phase 6D) | `python -m compileall app/` | **PASSED** (all modules compiled cleanly, 0 errors) |
| 2026-09-13 | Frontend Build (Phase 6D Check) | `npm run build` | **PASSED** (built in 435ms, 0 errors) |
| 2026-09-13 | TypeScript Verification (Phase 6D Check) | `npx tsc --noEmit` | **PASSED** (0 errors) |
| 2026-09-13 | Phase 11 Comparison API Tests | `pytest tests/test_comparison_api.py -v` | **PASSED** (7 passed, 0 skipped against Neon PostgreSQL) |
| 2026-09-13 | Frontend Build (Phase 11 Check) | `npm run build` | **PASSED** (built in 488ms, 0 errors) |
| 2026-09-13 | TypeScript Verification (Phase 11 Check) | `npx tsc --noEmit` | **PASSED** (0 errors) |
| 2026-09-14 | Phase 12 Obligation API Tests | `pytest tests/test_obligation_api.py -v` | **PASSED** (10 passed, 0 skipped against Neon PostgreSQL) |
| 2026-09-14 | Frontend Build (Phase 12 Check) | `npm run build` | **PASSED** (built in 1.77s, 0 errors) |
| 2026-09-14 | TypeScript Verification (Phase 12 Check) | `npx tsc --noEmit` | **PASSED** (0 errors) |
| 2026-09-14 | Phase 13B Alembic Migration | `alembic upgrade head` | **PASSED** (applied revision `e911249325b6_add_hashed_password_to_users`) |
| 2026-09-14 | Phase 13B Alembic Downgrade Reversibility | `alembic downgrade -1` & `upgrade head` | **PASSED** (reversibility verified on live Neon PostgreSQL) |
| 2026-09-14 | Phase 13 Auth & Ownership Tests | `pytest tests/test_auth_and_ownership.py -v` | **PASSED** (6 passed, 0 skipped against Neon PostgreSQL) |
| 2026-09-14 | Frontend Build (Phase 13 Check) | `npm run build` | **PASSED** (built in 325ms, 0 errors) |
| 2026-09-14 | TypeScript Verification (Phase 13 Check) | `npx tsc --noEmit` | **PASSED** (0 errors) |
| 2026-09-14 | Frontend Build (Phase 14 Check) | `npm run build` | **PASSED** (built in 282ms, 0 errors) |
| 2026-09-14 | TypeScript Verification (Phase 14 Check) | `npx tsc --noEmit` | **PASSED** (0 errors) |
| 2026-09-14 | Backend Health Verification | `python -c "from app.main import app"` | **PASSED** (Backend app import healthy, 0 errors) |
| 2026-09-14 | Phase 17 RAG Evaluation Tests | `pytest tests/test_rag_evaluation.py -v` | **PASSED** (23 passed, 0 skipped, 100% pass rate against Neon PostgreSQL) |
| 2026-09-14 | Phase 5D Regression Verification | `pytest tests/test_retrieval_evaluation.py -v` | **PASSED** (10 passed, 0 skipped, 100% deterministic) |
| 2026-09-14 | Frontend Build (Phase 17 Check) | `npm run build` | **PASSED** (built in 487ms, 0 errors) |
| 2026-09-14 | TypeScript Verification (Phase 17 Check) | `npx tsc --noEmit` | **PASSED** (0 errors) |
| 2026-09-14 | Phase 18 Security & Reliability Suite | `pytest tests/test_security_and_reliability.py -v` | **PASSED** (18 passed, 0 skipped, 100% pass rate) |
| 2026-09-14 | Core RAG & API Regression Suite | `pytest tests/test_grounded_rag.py tests/test_analyst_api.py tests/test_comparison_api.py tests/test_obligation_api.py tests/test_auth_and_ownership.py -v` | **PASSED** (42 passed, 0 skipped, 100% pass rate) |
| 2026-09-14 | Frontend Production Build (Phase 18 Check) | `npm run build` | **PASSED** (built in 478ms, 0 errors) |
| 2026-09-14 | TypeScript Verification (Phase 18 Check) | `npx tsc --noEmit` | **PASSED** (0 errors) |
| 2026-09-14 | Phase 18 Git History Purge Verification | `scan_history.py` across all reachable commits | **PASSED** (0 secret pattern matches found in git history) |
| 2026-09-14 | Secret Scanner Regression Suite | `pytest tests/test_secret_scanner.py -v` | **PASSED** (6 passed, 0 skipped, 100% pass rate) |
| 2026-09-14 | Repository Tracked Secret Scan | `python app/core/secret_scanner.py` | **PASSED** (0 secrets detected in repository tracked files) |
| 2026-09-14 | Frontend Production Build (Remediation Check) | `npm run build` | **PASSED** (built in 536ms, 0 errors) |
| 2026-09-14 | TypeScript Verification (Remediation Check) | `npx tsc --noEmit` | **PASSED** (0 errors)
