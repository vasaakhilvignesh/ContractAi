# PHASE_STATUS.md — Project Roadmap & Progress Tracker

This document tracks the active phase, completed milestones, blockers, and immediate next actions for **ContractIQ**.

---

## 1. Project Health & Metadata

| Metric | Value |
| :--- | :--- |
| **Current Phase** | **Phase 2A: Contract API Foundation** |
| **Status** | **COMPLETE** |
| **Last Verified State** | Backend: 60 passed, 0 skipped (`pytest`); Frontend: `npm run build` & `npx tsc` clean (0 errors) |
| **Last Git Commit** | `fa22bf2` ("feat: complete phase 1 backend database foundation") |
| **Git Remote** | `https://github.com/vasaakhilvignesh/ContractAi.git` (branch: `main`) |
| **Next Phase** | **Phase 2B: Contract Upload API** |
| **Exact Next Action** | Commence Phase 2B (PDF file upload endpoint, file validation, and document storage handler). |

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
- [ ] **Phase 2: PDF Ingestion, Text Extraction & Chunking Engine**
  - [x] **Phase 2A: Contract API Foundation** *(Completed)*
    - [x] Pydantic v2 schemas (`ContractBase`, `ContractCreate`, `ContractUpdate`, `ContractResponse`, `ContractListResponse`).
    - [x] Contract service layer with data-access operations, attribute filtering, and deterministic pagination.
    - [x] Contract REST API router mounted at `/contracts` and `/api/v1/contracts` (`POST`, `GET`, `GET /{id}`, `PATCH /{id}`, `DELETE /{id}`).
    - [x] 12 comprehensive contract API unit/integration tests covering CRUD, pagination, 404/422 errors against live Neon DB.
    - [x] Backend test suite passes: 60 passed (48 Phase 1 + 12 Phase 2A).
    - [x] Zero database migration required; fully compatible with Phase 1 schema.
  - [ ] **Phase 2B: Contract Upload API & Storage**
    - [ ] PDF upload handler with file validation (MIME, size) and storage backend.
  - [ ] **Phase 2C: Text Extraction & Clause Chunking**
    - [ ] Text extraction preserving page numbers, section headers, and tabular data.
    - [ ] Clause-aware chunking pipeline with page-level lineage metadata.
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


