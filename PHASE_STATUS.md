# PHASE_STATUS.md — Project Roadmap & Progress Tracker

This document tracks the active phase, completed milestones, blockers, and immediate next actions for **ContractIQ**.

---

## 1. Project Health & Metadata

| Metric | Value |
| :--- | :--- |
| **Current Phase** | **Phase 0: Inspection, Architecture Baseline & Project Memory** |
| **Status** | **IN PROGRESS** |
| **Last Verified State** | Frontend builds cleanly (`npm run build`), TypeScript passes with 0 errors (`npx tsc`) |
| **Last Git Commit** | `edef663` ("Changes are made") |
| **Git Remote** | `https://github.com/vasaakhilvignesh/ContractAi.git` (branch: `main`) |
| **Next Phase** | **Phase 1: Backend Foundation, Data Modeling & Database Setup** |
| **Exact Next Action** | Await user instruction to conclude Phase 0 and review recommendations before initiating Phase 1. |

---

## 2. Phase Breakdown & Status

- [x] **Phase 0: Project Baseline, Audit & Memory Protocol** *(Current)*
  - [x] Full codebase audit of dependencies, tooling, routes, components, and styling.
  - [x] Verification of production build and type checking.
  - [x] Git repository and remote safety audit.
  - [x] Creation of `AGENTS.md` (Operational protocol & 12 development rules).
  - [x] Creation of `DECISIONS.md` (Decision record for baseline & pending architecture).
  - [x] Creation of `FLOW.md` (Current application flow & planned system architecture).
  - [x] Creation of `PHASE_STATUS.md` (This roadmap).
  - [x] Architecture baseline documentation updated in `README.md`.
- [ ] **Phase 1: Backend Scaffolding, Data Modeling & Database (PostgreSQL + pgvector)**
  - [ ] Backend technology selection (Python FastAPI vs Node.js).
  - [ ] Database schema design (Contracts, Document Chunks, Clauses, Obligations, Risks, Users, Audit Logs).
  - [ ] pgvector extension enablement and vector column indexing.
  - [ ] Database migration tooling and initial seed script.
  - [ ] Core REST API endpoints for Contract listing, retrieval, and metadata.
- [ ] **Phase 2: PDF Ingestion, Text Extraction & Chunking Engine**
  - [ ] PDF upload handler with file validation and storage.
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
| 2026-09-12 | Clean build | `npm run build` | **PASSED** (built in 393ms, 0 errors) |
| 2026-09-12 | TypeScript Typecheck | `npx tsc` | **PASSED** (0 errors) |
| 2026-09-12 | Git Status Audit | `git status` | Clean working tree on `main` |
