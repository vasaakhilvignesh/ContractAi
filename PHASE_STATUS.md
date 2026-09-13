# PHASE_STATUS.md — Project Roadmap & Progress Tracker

This document tracks the active phase, completed milestones, blockers, and immediate next actions for **ContractIQ**.

---

## 1. Project Health & Metadata

| Metric | Value |
| :--- | :--- |
| **Current Phase** | **Phase 10A–10E: AI Analyst API & Multi-Contract RAG** |
| **Status** | **COMPLETE** |
| **Last Verified State** | Backend: 10 passed (`test_analyst_api.py`), 9 passed (`test_grounded_rag.py`), 8 passed (`test_risk_engine.py`), 8 passed (`test_evidence_api_and_validation.py`), 16 passed (`test_evidence_model.py`); Frontend: `npm run build` & `npx tsc` clean (0 errors) |
| **Last Git Commit** | `d87f0ad` ("feat: add grounded rag generation") |
| **Git Remote** | `https://github.com/vasaakhilvignesh/ContractAi.git` (branch: `main`) |
| **Next Phase** | **Phase 11: Frontend Integration & Interactive Citation Highlighting** |
| **Exact Next Action** | Wire frontend API client services with live contract, extraction, evidence, risk, and analyst endpoints. |

---

## 2. Phase Breakdown & Status

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
    - [x] Extended `Settings` with `llm_provider`, `llm_model="gemini-2.5-flash"`, `llm_temperature=0.0`, and updated `.env.example`.
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
- [ ] **Phase 11: Frontend Integration & Interactive Citation Highlighting**
  - [ ] Replacement of static mock data with API client services.
  - [ ] Upload wizard connection to backend ingestion pipeline.
  - [ ] Implementation of missing `/analyst` (AI chat with citation panel) and `/audit` pages.
  - [ ] Interactive source citation highlighting (click citation -> navigate to page view).
- [ ] **Phase 12: Authentication, Evaluation, Testing & Production Hardening**

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
