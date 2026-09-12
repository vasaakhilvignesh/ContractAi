# DECISIONS.md — Architecture & Technical Decision Record

This document records all significant architectural, technical, and implementation decisions for **ContractIQ**.

Format for each record:
- **Decision:** What was chosen
- **Context:** Problem statement and situation
- **Why this decision was made:** Justification and technical reasoning
- **Alternatives considered:** Other options evaluated
- **Why alternatives were rejected:** Disadvantages or mismatches
- **Consequences / Trade-offs:** Technical debt, operational requirements, or downstream implications
- **Phase:** Project phase when decided
- **Date:** Decision date (YYYY-MM-DD)

---

## 1. Implemented & Baseline Decisions (Phase 0)

### DEC-001: Frontend Framework & Build Tooling
- **Decision:** React 19 (`react` 19.0.0, `react-dom` 19.0.0) with TypeScript 5.7 and Vite 8 (`@vitejs/plugin-react`).
- **Context:** Project requires a fast, interactive single-page dashboard for contract analysis, filtering, and evidence inspection.
- **Why this decision was made:** Existing working codebase was provided with React 19 + TypeScript + Vite. It provides near-instant hot module replacement (HMR), strict type checking, and clean modern React idioms without framework bloat.
- **Alternatives considered:** Next.js (App Router), Remix, Vue 3, vanilla JavaScript.
- **Why alternatives were rejected:** Rule 1 & Rule 2 prohibit rewriting working functionality. The existing Vite SPA is fast, lightweight, and completely sufficient for client dashboard interactions.
- **Consequences / Trade-offs:** Pure SPA requires a separate backend API server (e.g. FastAPI / Express) and reverse proxy routing for production deployment rather than unified serverless functions.
- **Phase:** Phase 0 (Baseline)
- **Date:** 2026-09-12

### DEC-002: Client-Side Routing Architecture
- **Decision:** React Router v7 (`react-router-dom` 7.18.3) using `BrowserRouter`.
- **Context:** Need navigation across Dashboard, Contracts library, Contract overview, Obligations tracker, Risk monitor, Comparison tool, and Contract upload.
- **Why this decision was made:** Already implemented with nested layout routing via `<Shell />` and `<Outlet />`, providing clean route-driven page views and deep-linking capabilities (e.g. `/contracts/:id`).
- **Alternatives considered:** TanStack Router, state-based tab switching, Next.js page routing.
- **Why alternatives were rejected:** React Router v7 was already implemented and working cleanly with the existing component hierarchy.
- **Consequences / Trade-offs:** Production static file server or reverse proxy must rewrite all routes to `index.html` (SPA fallback).
- **Phase:** Phase 0 (Baseline)
- **Date:** 2026-09-12

### DEC-003: Styling & Design System Approach
- **Decision:** Tailwind CSS v4 via `@tailwindcss/vite` and CSS custom variables for semantic design tokens.
- **Context:** Enterprise contract management interface requiring clean data tables, badges, risk color scales, and typography.
- **Why this decision was made:** Tailwind CSS v4 is configured with `@theme inline` in `src/index.css`, linking variables like `--background`, `--primary` (`#1E3A5F`), `--accent` (`#2563EB`), and semantic risk levels (`critical`, `high`, `medium`, `low`). Inter and JetBrains Mono provide crisp readability.
- **Alternatives considered:** Tailwind CSS v3 with `tailwind.config.js`, CSS Modules, Styled Components, Material UI.
- **Why alternatives were rejected:** Tailwind v4 Vite plugin provides faster compilation, zero runtime overhead, and already styles all existing screens cleanly.
- **Consequences / Trade-offs:** Tailwind v4 lacks a standalone `tailwind.config.js` file; theme customizations must be maintained directly in `src/index.css` via `@theme` directives.
- **Phase:** Phase 0 (Baseline)
- **Date:** 2026-09-12

### DEC-004: Baseline Mock Data Architecture
- **Decision:** Strongly-typed mock records centralized in `src/data/mock.ts`.
- **Context:** Need realistic domain data to develop and audit UI layouts prior to backend and database implementation.
- **Why this decision was made:** `mock.ts` defines explicit domain interfaces (`Contract`, `Risk`, `Obligation`, `AuditEvent`, `RiskLevel`, `ContractStatus`, `ProcessingStatus`) with realistic legal contract data (Salesforce MSA, AWS SaaS, Accenture PSA, etc.) that mirror expected schema definitions.
- **Alternatives considered:** MSW (Mock Service Worker), local JSON fixtures, ad-hoc component state.
- **Why alternatives were rejected:** In-memory TypeScript exports allow full type inference, zero external mock server dependencies, and immediate rendering during the baseline phase.
- **Consequences / Trade-offs:** State is read-only; actions like "Mark Reviewed", "Upload", or "Mark Complete" currently lack persistence until an API client is connected.
- **Phase:** Phase 0 (Baseline)
- **Date:** 2026-09-12

### DEC-005: Shell Layout Pattern
- **Decision:** Two-tier persistent layout: fixed `Sidebar` (left) + fixed `Header` (top) wrapping a scrollable main content area.
- **Context:** Contract analysts need persistent access to navigation, search, notifications, and profile details without losing view context.
- **Why this decision was made:** Standard, robust SaaS layout implemented in `src/components/layout/Shell.tsx`. Fits dense enterprise data displays.
- **Alternatives considered:** Single horizontal navbar, collapsible side drawer, floating navigation bar.
- **Why alternatives were rejected:** Deep hierarchical navigation (Contracts -> Overview -> Clauses) benefits from fixed lateral orientation.
- **Consequences / Trade-offs:** Consumes horizontal screen real estate (~240px); mobile responsiveness is not yet implemented.
- **Phase:** Phase 0 (Baseline)
- **Date:** 2026-09-12

---

## 2. Pending & Undecided Decisions (To Be Documented in Future Phases)

The following architectural decisions have **not yet been made** and will be formally resolved in subsequent phases:

### DEC-006: Backend Language & Framework
- **Status:** **Not decided yet.**
- **Candidates:** Python (FastAPI) vs Node.js/TypeScript (Express / Fastify / NestJS).
- **Considerations:** Python has dominant ecosystem support for document processing, OCR, LangChain/LlamaIndex, and embedding pipelines; Node.js would unify frontend/backend language. Will be evaluated during Phase 1.

### DEC-007: Primary Database & Vector Store
- **Status:** **Not decided yet.**
- **Project Direction:** PostgreSQL with `pgvector` extension.
- **Considerations:** PostgreSQL provides ACID guarantees for contract metadata, clauses, obligations, and risk rules, while `pgvector` enables unified relational + vector queries without introducing a separate vector DB (such as Pinecone or Milvus). Exact ORM/driver (e.g. SQLAlchemy, Prisma, Drizzle) is not decided yet.

### DEC-008: PDF Text Extraction & OCR Strategy
- **Status:** **Not decided yet.**
- **Candidates:** `pypdf`, `pdfplumber`, `PyMuPDF` (fitz), or OCR tools (Tesseract) for scanned docs.
- **Considerations:** Must preserve page numbers, layout coordinates, and table structures to enable page-level citations.

### DEC-009: Document Chunking Strategy
- **Status:** **Not decided yet.**
- **Candidates:** Recursive character splitter, clause-aware semantic boundary chunking, Markdown/header-aware chunking.
- **Considerations:** Contract clauses must not be split arbitrarily across sentences; chunk metadata must retain exact page numbers and clause section identifiers.

### DEC-010: Embedding Model
- **Status:** **Not decided yet.**
- **Candidates:** OpenAI `text-embedding-3-small`, Google Gemini embeddings (`text-embedding-004`), open-source HuggingFace sentence-transformers (e.g., `BAAI/bge-small-en-v1.5`).
- **Considerations:** Cost, latency, dimension size, and legal domain retrieval accuracy.

### DEC-011: LLM Provider for Extraction & Analysis
- **Status:** **Not decided yet.**
- **Candidates:** Google Gemini (via official SDK / Firebase AI Logic), OpenAI GPT-4o / GPT-4o-mini, Anthropic Claude 3.5 Sonnet, or local models.
- **Considerations:** Long context window, structured JSON output enforcement, cost, and latency.

### DEC-012: Hybrid Search & Reranking Architecture
- **Status:** **Not decided yet.**
- **Candidates:** PostgreSQL `tsvector` (BM25/Full-text search) + `pgvector` cosine similarity, combined via Reciprocal Rank Fusion (RRF); optional cross-encoder reranker (e.g. Cohere rerank or `bge-reranker`).
- **Considerations:** Exact keyword matching (dates, dollar figures, specific parties) is critical in contracts where pure vector search fails.

### DEC-013: Structured Output Schema & Extraction Technique
- **Status:** **Not decided yet.**
- **Candidates:** Pydantic models with OpenAI/Gemini Structured Outputs, Instructor, JSON schema mode.
- **Considerations:** Strict type validation for clauses, obligations, renewal dates, notice periods, and liability caps.

### DEC-014: Deterministic Risk Rule Architecture
- **Status:** **Not decided yet.**
- **Candidates:** Pure code-based rule engine (Python functions / TypeScript validators), JSON-based rule definitions, or domain rule engine.
- **Design Principle:** LLM extracts structured facts (e.g., `notice_period_days: 15`); deterministic application code evaluates business rules (e.g., `if notice_period_days < 30 -> flag CRITICAL`). LLM does NOT guess risk level nondeterministically.

### DEC-015: Authentication & Multi-Tenancy Strategy
- **Status:** **Not decided yet.**
- **Candidates:** Supabase Auth, Firebase Auth, Clerk, or JWT-based custom auth with PostgreSQL row-level security (RLS).
- **Considerations:** Per-user/organization contract isolation and role-based access control (Procurement Lead, Legal, Admin).

### DEC-016: Production Deployment Architecture
- **Status:** **Not decided yet.**
- **Candidates:** Docker Compose on VPS, Vercel/Cloudflare Pages (frontend) + Cloud Run/Render (backend), Kubernetes.
- **Considerations:** Cost-effectiveness, reproducibility, simplicity for evaluation.
