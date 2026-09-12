# PHASE_STATUS.md — Project Roadmap & Progress Tracker

This document tracks the active phase, completed milestones, blockers, and immediate next actions for **ContractIQ**.

---

## 1. Project Health & Metadata

| Metric | Value |
| :--- | :--- |
| **Current Phase** | **Phase 3A: PDF Text Extraction** |
| **Status** | **COMPLETE** |
| **Last Verified State** | Backend: 100 passed, 0 skipped (`pytest`); Frontend: `npm run build` & `npx tsc` clean (0 errors) |
| **Last Git Commit** | `d6e2b82` ("feat: add contract processing state") |
| **Git Remote** | `https://github.com/vasaakhilvignesh/ContractAi.git` (branch: `main`) |
| **Next Phase** | **Phase 3B: Text Normalization & Clause-Aware Chunking Pipeline** |
| **Exact Next Action** | Commence Phase 3B (Text normalization, clause boundary segmentation, chunking engine with page-level lineage metadata). |

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
  - [ ] **Phase 3B: Text Normalization & Clause-Aware Chunking Pipeline**
    - [ ] Text normalization and cleaning without semantic alteration.
    - [ ] Clause-aware chunking pipeline with page-level lineage metadata and boundary segmentation.
  - [ ] **Phase 3C: Dense Embedding Generation & pgvector Insertion**
    - [ ] Integration of embedding model to generate dense vectors.
    - [ ] Insertion of document chunks into PostgreSQL with pgvector embeddings.
- [ ] **Phase 3: Hybrid Search & RAG Retrieval Engine**
  - [ ] Keyword full-text search implementation (tsvector / BM25).
  - [ ] Semantic vector search implementation (pgvector cosine similarity).
  - [ ] Hybrid retrieval fusion (Reciprocal Rank Fusion - RRF).
  - [ ] Top-K reranking and context boundary pruning.
  - [ ] Grounded question-answering prompt engineering with verifiable page citations.
  - [ ] Fallback "evidence not found" response handling when confidence is below threshold.
- [ ] **Phase 4: Structured Extraction & Deterministic Risk Rules Engine**
  - [ ] Structured extraction schema for clauses (Renewal, Termination, Liability, Indemnification).
  - [ ] Structured obligation extraction (responsible party, due date, frequency, source clause).
  - [ ] Implementation of deterministic business risk rules (notice period thresholds, uncapped liability, auto-renewal deadlines).
  - [ ] Storage and linking of generated risk signals to source contract chunks.
- [ ] **Phase 5: Frontend Integration & Live API Wiring**
  - [ ] Replacement of static mock data with API client services.
  - [ ] Upload wizard connection to backend ingestion pipeline.
  - [ ] Implementation of missing `/analyst` (AI chat with citation panel) and `/audit` pages.
  - [ ] Interactive source citation highlighting (click citation -> navigate to page view).
- [ ] **Phase 6: Authentication, Evaluation, Testing & Production Hardening**
  - [ ] User authentication and organization-level multi-tenancy.
  - [ ] Retrieval evaluation suite (precision, recall, hallucination rate).
  - [ ] Automated end-to-end and integration tests.
  - [ ] Production build containerization and deployment configuration.

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





