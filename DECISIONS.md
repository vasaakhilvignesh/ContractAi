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

## 2. Implemented & Confirmed Decisions (Phase 1)

### DEC-006: Backend Language & Framework
- **Decision:** Python with FastAPI (`fastapi==0.115.5`, `uvicorn[standard]==0.32.1`).
- **Context:** Phase 1 requires a backend REST API server that can eventually serve as the foundation for a document processing, RAG retrieval, and structured extraction pipeline.
- **Why this decision was made:** Python has the dominant ecosystem for all downstream Phase 2–4 requirements: `pdfplumber`/`PyMuPDF` for extraction, `sentence-transformers` / Gemini/OpenAI SDK for embeddings, `LangChain`/`LlamaIndex` for orchestration. FastAPI provides automatic OpenAPI documentation, Pydantic validation, async support, and is the standard choice for Python AI/ML backends. It avoids introducing a second language when Node.js would not benefit the backend at all.
- **Alternatives considered:** Node.js + Express / Fastify / NestJS.
- **Why alternatives were rejected:** Node.js would add zero value for the backend. All heavy-lifting in Phase 2–4 (PDF extraction, embeddings, RAG) requires Python libraries. Unifying backend in Python is simpler and more maintainable (Rule 2, Rule 10, Rule 11).
- **Consequences / Trade-offs:** Backend is a separate process from the Vite SPA. In development, CORS is configured to allow all origins (restricted in Phase 5 production hardening).
- **Phase:** Phase 1
- **Date:** 2026-09-12

### DEC-007: Primary Database & Vector Store
- **Decision:** Neon PostgreSQL (cloud-managed, serverless) with `pgvector` extension (version 0.8.6 already installed on Neon `production` branch).
- **Context:** ContractIQ requires ACID-compliant relational storage for contract metadata, clauses, obligations, and risk signals, plus vector similarity search for RAG retrieval (Phase 3).
- **Why this decision was made:** PostgreSQL provides transactional guarantees across all relational tables. `pgvector` enables unified relational + vector storage without a separate vector database (Pinecone/Milvus), reducing operational complexity. Neon provides serverless autoscaling, branching for development isolation, and a managed production deployment. pgvector 0.8.6 supports HNSW and IVFFlat indexing required for Phase 3.
- **Alternatives considered:** Supabase (PostgreSQL + pgvector), PlanetScale (MySQL — no pgvector), local Docker PostgreSQL, Pinecone (vector-only, no relational), Weaviate.
- **Why alternatives were rejected:** Supabase was viable but Neon was already provisioned and verified. MySQL/PlanetScale has no native pgvector support. Pinecone would require a separate relational database for contract metadata. Local Docker adds operational dependency that violates Rule 10 (prefer simple architecture).
- **Consequences / Trade-offs:** Application is cloud-dependent (Neon). Local development requires `DATABASE_URL` from Neon in a gitignored `.env` file. Connection pooling uses `pool_size=5, max_overflow=10` with `pool_pre_ping=True` for Neon's serverless connection behavior.
- **Phase:** Phase 1
- **Date:** 2026-09-12

### DEC-017: ORM & Migration Tooling
- **Decision:** SQLAlchemy 2.0 (mapped columns + DeclarativeBase) with Alembic for schema migrations.
- **Context:** Phase 1 needs an ORM layer for all 7 database entities and a migration system to track schema changes across development, staging, and production.
- **Why this decision was made:** SQLAlchemy 2.0's new mapped-column style provides full type inference in Python and strict typing compatible with `strict: true` style Python typing. Alembic is SQLAlchemy's native migration tool with autogenerate capability. Together they form the de-facto standard for Python/PostgreSQL backends.
- **Alternatives considered:** Tortoise ORM (async-first), SQLModel (Pydantic + SQLAlchemy hybrid), Prisma (TypeScript-native), raw psycopg2.
- **Why alternatives were rejected:** Tortoise ORM / SQLModel are less mature than SQLAlchemy 2.0. Prisma is TypeScript-first and conflicts with the Python backend decision (DEC-006). Raw psycopg2 would require hand-writing all migration SQL, which is error-prone.
- **Consequences / Trade-offs:** Alembic is the sole schema migration authority. Tables must never be created by means other than Alembic migrations (e.g., no `Base.metadata.create_all()` in production).
- **Phase:** Phase 1
- **Date:** 2026-09-12

### DEC-018: PostgreSQL Python Driver
- **Decision:** `psycopg2-binary==2.9.10` (binary wheel, no build dependencies).
- **Context:** SQLAlchemy requires a PostgreSQL driver. The binary wheel avoids needing `libpq-dev` or a C compiler in CI environments.
- **Alternatives considered:** `psycopg` (psycopg3 — async-native), `asyncpg` (async-only), `pg8000` (pure Python).
- **Why alternatives were rejected:** `psycopg2-binary` is the most battle-tested, widely documented driver with broad SQLAlchemy support. `psycopg3` (psycopg) is newer and the async model introduces unnecessary complexity in Phase 1. `asyncpg` requires a different connection string format and does not work with the sync SQLAlchemy engine used in Phase 1.
- **Consequences / Trade-offs:** `psycopg2-binary` is not recommended for production distribution packages (the maintainer recommends `psycopg2` with build deps for production). For Phase 5/6 production hardening, this can be revisited.
- **Phase:** Phase 1
- **Date:** 2026-09-12

### DEC-019: Environment Configuration Strategy
- **Decision:** `pydantic-settings==2.6.1` with a gitignored `backend/.env` file (populated from `backend/.env.example`).
- **Context:** The application must read `DATABASE_URL` and other secrets from the environment without hardcoding them. The `.env` file must never be committed.
- **Why this decision was made:** `pydantic-settings` integrates natively with FastAPI/Pydantic and provides type-validated, self-documenting settings. The `.gitignore` already excludes `.env*` patterns; `!.env.example` negation allows the template to be committed safely.
- **Alternatives considered:** `python-decouple`, `dynaconf`, raw `os.environ`.
- **Why alternatives were rejected:** `pydantic-settings` is already a dependency (via Pydantic) and provides the cleanest integration with FastAPI. Raw `os.environ` provides no type validation or default management.
- **Consequences / Trade-offs:** Developers must copy `backend/.env.example` to `backend/.env` and set `DATABASE_URL` before the server can connect to Neon.
- **Phase:** Phase 1
- **Date:** 2026-09-12

### DEC-020: Contract Entity REST API Design & Pagination
- **Decision:** FastAPI router with separate service layer (`backend/app/services/contract_service.py`), Pydantic v2 schemas (`backend/app/schemas/contract.py`), dual route mounting (`/contracts` and `/api/v1/contracts`), and stable offset/limit pagination with deterministic tie-breaking (`created_at.desc(), id.asc()`).
- **Context:** Phase 2A requires Contract CRUD and listing operations ahead of document file ingestion and extraction.
- **Why this decision was made:** Isolating data access in a service layer keeps route handlers clean and simplifies testing. Deterministic sorting guarantees consistent pagination across pages. Dual route mounting preserves backwards compatibility for direct path access and versioned prefixes.
- **Alternatives considered:** Putting SQL queries directly in route handlers; cursor-based pagination.
- **Why alternatives were rejected:** Raw queries in handlers violate separation of concerns. Cursor-based pagination adds unnecessary complexity at this scale (Rule 10).
- **Consequences / Trade-offs:** Offset pagination can be slow on very large tables (millions of records), but is optimal for enterprise contract portfolio sizes (<100k contracts).
- **Phase:** Phase 2A
- **Date:** 2026-09-12

### DEC-021: PDF Document Storage, Validation & Re-upload Strategy
- **Decision:** Local filesystem storage under `backend/storage/contracts/` using generated UUID filenames (`{contract_id}_{token}.pdf`), strict `%PDF-` signature and size limit enforcement, atomic file cleanup on failure, and deterministic re-upload replacement (updating contract record and safely unlinking old file).
- **Context:** Phase 2B requires storing uploaded PDF files safely, validating their authenticity, preventing path traversal, and avoiding orphaned storage files.
- **Why this decision was made:** Separating the client-provided filename from the physical filesystem path prevents path traversal attacks (`../../`). Checking `%PDF-` magic bytes prevents file spoofing. Atomic unlinking on DB commit failure prevents disk bloat. Replacing the previous file on re-upload keeps storage aligned with the single-document-per-contract model in Phase 1 without premature versioning complexity.
- **Alternatives considered:** Database BLOB/BYTEA storage; cloud object storage (S3/GCS) in local development; multi-version document tables.
- **Why alternatives were rejected:** Storing PDFs as database BLOBs causes database bloat and connection transfer overhead. Cloud object storage adds unnecessary external credentials and operational dependencies for local development. Multi-version tables would require database schema changes and migrations that exceed Phase 2B scope.
- **Consequences / Trade-offs:** Development storage relies on local filesystem (`backend/storage/contracts/`, ignored by Git). Production deployment (Phase 6) can swap the physical storage backend for S3/GCS using the same relative storage key interface.
- **Phase:** Phase 2B
- **Date:** 2026-09-12

### DEC-022: Contract Document Processing State Machine & Lifecycle
- **Decision:** Application-layer deterministic finite state machine (FSM) managing processing status transitions (`pending` -> `uploaded` -> `queued` -> `processing` -> `completed` / `failed`, with `failed` -> `queued` retry) backed by the existing `processing_status` and `processing_error` columns.
- **Context:** Phase 2C requires an auditable, controlled processing lifecycle to coordinate downstream extraction (Phase 3) and analysis without premature background queue dependencies.
- **Why this decision was made:** Centralizing transition rules in the service layer prevents illegal state jumps (such as `uploaded` directly to `completed` or transitioning contracts that have no uploaded file). Reusing existing database columns maintains zero-migration safety. Avoiding external queue brokers (Celery, Redis, RabbitMQ) adheres to Rule 2 and Rule 10 until background processing is actually implemented.
- **Alternatives considered:** Database-level ENUM or check constraint; Celery/Redis workflow state; workflow engine (Temporal/Airflow).
- **Why alternatives were rejected:** Altering Neon PostgreSQL with an ENUM type would require schema migrations. Heavy distributed queues add operational dependencies that violate Rule 10 (prefer simple, explainable architecture).
- **Consequences / Trade-offs:** State transitions are managed synchronously through the API layer; Phase 3 will drive these transitions as part of the extraction pipeline.
- **Phase:** Phase 2C
- **Date:** 2026-09-12



### DEC-008: PDF Text Extraction Engine & Scanned Document Handling
- **Decision:** PyMuPDF (`pymupdf==1.28.2`) for high-performance native text extraction with structural block layout and bounding box preservation, accompanied by explicit scanned/image-only document detection without OCR.
- **Context:** Phase 3A requires extracting raw text from uploaded contract PDFs, preserving 1-indexed page boundaries, character/word metrics, and structural heading candidates to enable accurate citation lineage in downstream chunking (Phase 3B) and retrieval (Phase 3C).
- **Why this decision was made:** PyMuPDF is 15–30x faster than pdfminer/pdfplumber, provides robust C-based MuPDF parsing that handles malformed enterprise contracts, accurately extracts text blocks (`page.get_text("blocks")`), and cleanly identifies raster images for scanned document detection. Scanned documents are explicitly flagged (`is_scanned: True`, `extraction_status: "scanned_requires_ocr"`) rather than pretending text extraction succeeded. Heavy external OCR dependencies (Tesseract) were excluded to adhere to Rule 2 and Rule 10.
- **Alternatives considered:** `pypdf`, `pdfplumber`, `pytesseract` / `EasyOCR`.
- **Why alternatives were rejected:** `pypdf` loses layout blocks, merges multi-column contract text, and has weak table handling. `pdfplumber` is CPU-intensive and slow on large multi-page legal documents. Tesseract/EasyOCR requires external binary system packages (`tesseract.exe`), adds multi-gigabyte models, and introduces brittle cross-platform dependencies unsuitable for standard digital-native enterprise contracts.
- **Consequences / Trade-offs:** Pure image-only contracts cannot extract text until an OCR fallback worker is added in a future phase. Native digital PDFs extract with sub-100ms latency and high layout fidelity.
- **Phase:** Phase 3A
- **Date:** 2026-09-12

### DEC-009: Text Normalization & Clause-Aware Document Chunking Strategy
- **Decision:** Conservative non-destructive text normalization and clause-aware document chunking with structural heading propagation, page-bounded segmentation, character offsets relative to normalized page text, and atomic idempotent persistence into `DocumentChunk` (with `embedding=None`).
- **Context:** Phase 3B requires transforming raw extraction text into discrete, semantically coherent evidence chunks for downstream embedding and vector search without splitting legal clauses arbitrarily across sentences.
- **Why this decision was made:** Legal contracts are structured by Sections, Articles, and numbered clauses. Chunking within 1-indexed page boundaries guarantees deterministic page citations. Propagating the nearest enclosing section header (`section_header`) preserves legal context when clauses span page breaks. Conservative normalization (NFKC, CRLF/CR to LF, horizontal whitespace and blank line collapse, soft-hyphen healing) preserves exact casing, currency figures ($), percentages (%), and punctuation without altering legal meaning. Atomic deletion and replacement within a single transaction ensures idempotency without orphaned records.
- **Alternatives considered:** Generic recursive character splitter (LangChain); Markdown conversion; naive sliding character windows.
- **Why alternatives were rejected:** Generic character splitters slice clauses blindly across sentences and legal terms, losing structural provenance and producing unreliable page citations. Markdown conversion adds parsing dependencies and risks formatting artifacts.
- **Consequences / Trade-offs:** Character offsets (`char_start`, `char_end`) refer to normalized page text rather than raw PDF coordinates. Chunks remain bounded to individual pages; oversized clauses (> 2,000 chars) are partitioned at sentence boundaries with a rolling 150-char overlap.
- **Phase:** Phase 3B
- **Date:** 2026-09-12

### DEC-010: Embedding Model & Provider Abstraction
- **Decision:** Google Gemini `gemini-embedding-2` with 768 output dimensions, cosine similarity, task types `RETRIEVAL_DOCUMENT` (document chunks) and `RETRIEVAL_QUERY` (search queries), accessed via official `google-genai==2.23.0` through an `EmbeddingProvider` abstraction with guaranteed $N \to N$ ordering and safe batching.
- **Context:** Phase 4A requires selecting and integrating an embedding model to compute dense vector representations for contract document chunks and future search queries.
- **Why this decision was made:** `gemini-embedding-2` provides state-of-the-art semantic representation, natively supports flexible output dimensionality (configured to 768 dimensions), and supports specialized task types (`RETRIEVAL_DOCUMENT` for chunk indexing, `RETRIEVAL_QUERY` for search queries) optimizing cosine distance retrieval. Using the official `google-genai` SDK unifies upstream Google AI tools and avoids obsolete embedding models like `text-embedding-004`. The `EmbeddingProvider` abstraction decouples business logic from upstream provider details and strictly preserves $N \to N$ input-to-output ordering.
- **Alternatives considered:** OpenAI `text-embedding-3-small`, Google `text-embedding-004` (obsolete), local HuggingFace `sentence-transformers` (e.g. `bge-small-en-v1.5`).
- **Why alternatives were rejected:** `text-embedding-004` is obsolete. Local sentence-transformers require PyTorch/transformers dependencies (~2GB+ wheels) that violate Rule 2 and Rule 10 for serverless deployments. OpenAI adds an additional vendor dependency when Gemini is the target AI platform.
- **Consequences / Trade-offs:** Requires `GEMINI_API_KEY` for live production embedding. Local unit tests use 100% mocked SDK calls to allow CI/offline execution. Chunks are embedded in batches of 100 to avoid API rate limits while strictly preserving sequential order. Schema migration for vector dimension constraint is deferred to database migration phase per Phase 4A scope constraints.
- **Phase:** Phase 4A
- **Date:** 2026-09-12

### DEC-023: Contract Chunk Vector Embedding Generation & Persistence
- **Decision:** Standalone service (`backend/app/services/embedding_generation_service.py`) with `generate_contract_embeddings()`, idempotent chunk filtering (`embedding IS NULL` skipped unless `force_reembed=True`), 768-dimensional validation, atomic per-contract commit with rollback on failure, and REST endpoints `POST /contracts/{contract_id}/embed` and `/api/v1/contracts/{contract_id}/embed`.
- **Context:** Phase 4B requires generating dense vector representations for persisted `DocumentChunk` records and persisting them into `document_chunks.embedding` in PostgreSQL.
- **Why this decision was made:** Loading chunks deterministically ordered by `chunk_index.asc()` preserves exact document lineage. Using `EmbeddingProvider.embed_texts()` reuses the Phase 4A batching infrastructure (batches $\le 100$) and enforces `RETRIEVAL_DOCUMENT` task type. Idempotency guarantees zero redundant Gemini API calls on rerun. Single atomic commit per contract guarantees all-or-nothing persistence: if upstream fails, `db.rollback()` leaves the database in a clean, fully retryable state.
- **Alternatives considered:** Per-batch commit; Celery/Redis background worker; converting entire backend to async SQLAlchemy.
- **Why alternatives were rejected:** Per-batch commit leaves contracts in a half-embedded, corrupt evidence state. Distributed workers violate Rule 2 and Rule 10 before scale demands it. Converting backend to async SQLAlchemy just for Phase 4B would require rewriting all existing working database services (violating Rule 1).
- **Consequences / Trade-offs:** Chunks are embedded synchronously during the request; contracts with >500 chunks may take a few seconds. Column remains untyped `Vector(None)` until Phase 4C applies the `Vector(768)` migration.
- **Phase:** Phase 4B
- **Date:** 2026-09-12

### DEC-024: Typed Vector(768) Schema Migration and HNSW Indexing for Contract Chunks
- **Decision:** Enforce `Vector(768)` on `document_chunks.embedding` via Alembic migration (`18338ecd31a9`), preserve `nullable=True`, configure the SQLAlchemy model via `settings.embedding_dimension`, and create an HNSW index `idx_document_chunks_embedding_hnsw` using `vector_cosine_ops`.
- **Context:** Following Phase 4B embedding persistence, Phase 4C finalizes database schema typing and index infrastructure in preparation for semantic vector retrieval.
- **Why this decision was made:** Google Gemini embedding model is `gemini-embedding-2`, and embeddings are 768-dimensional dense vectors. PostgreSQL stores them as `Vector(768)`. Enforcing `Vector(768)` at the PostgreSQL engine level prevents dimensionality mismatch errors and guarantees data integrity. Cosine similarity is the target similarity metric for unit-normalized retrieval vectors. HNSW with `vector_cosine_ops` is used for approximate nearest-neighbor retrieval preparation because it is an appropriate pgvector index for cosine similarity and does not require training data or pre-existing rows (unlike IVFFlat which requires existing centroid data). Using pgvector defaults (`m=16, ef_construction=64`) avoids speculative tuning and maintains architectural simplicity (Rules 10 & 11).
- **Alternatives considered:** Untyped `Vector(None)`; IVFFlat index; postponing index creation to retrieval phase.
- **Why alternatives were rejected:** Untyped vectors permit silent dimensionality corruption. IVFFlat cannot be properly built on an empty or sparsely populated table without subsequent re-indexing. Creating the index in Phase 4C completes storage and indexing infrastructure, establishing a clear phase boundary before Phase 5A.
- **Consequences / Trade-offs:** Vector inserts with dimensions other than 768 are rejected by both SQLAlchemy/pgvector and PostgreSQL. Index graph updates incrementally on new chunk insertions. Query retrieval, similarity scoring, and top-k filtering belong strictly to Phase 5A (retrieval is NOT implemented in Phase 4C).
- **Phase:** Phase 4C
- **Date:** 2026-09-12

### DEC-025: Semantic Vector Retrieval Engine (pgvector Cosine Similarity Search)
- **Decision:** Implement contract-scoped semantic vector retrieval (`retrieval_service.py`) using existing `EmbeddingProvider.embed_query()` (`gemini-embedding-2`, `RETRIEVAL_QUERY`, 768 dimensions), executing pgvector cosine distance queries (`<=>`, `order_by(distance.asc()).limit(top_k)`), mapping raw cosine distance to exact similarity score (`similarity_score = 1.0 - distance`), supporting optional `min_similarity` filtering, and exposing REST endpoints `POST /contracts/{contract_id}/query` and `/api/v1/contracts/{contract_id}/query`.
- **Context:** Phase 5A requires implementing semantic vector retrieval against indexed contract chunks ahead of keyword retrieval (Phase 5B) and hybrid RRF fusion (Phase 5C).
- **Why this decision was made:** Reusing the Phase 4A `EmbeddingProvider` abstraction guarantees identical vector spaces and avoids duplicating Gemini SDK clients. Utilizing pgvector's `<=>` operator leverages the Phase 4C HNSW index (`vector_cosine_ops`). Bounding `top_k` to `[1, 20]` with default `5` protects memory while supplying sufficient chunk evidence for downstream review. Filtering `DocumentChunk.embedding.is_not(None)` prevents NULL distance evaluation errors. Strict contract scoping (`DocumentChunk.contract_id == contract_id`) prevents cross-tenant or cross-contract evidence leakage.
- **Alternatives considered:** Keyword-only search; client-side embedding generation; premature RAG/LLM synthesis in Phase 5A.
- **Why alternatives were rejected:** Keyword search fails on semantic paraphrasing (addressed in Phase 5B). Client-side embeddings leak API keys to browsers. Generating answers or citations violates Phase 5A scope boundaries (Rule 12: RAG finds evidence; synthesis is deferred to Phase 5C).
- **Consequences / Trade-offs:** Pure vector retrieval can miss exact keyword codes or acronyms; this is an accepted intermediate state resolved by hybrid search and RRF in Phase 5B.
- **Phase:** Phase 5A
- **Date:** 2026-09-12

### DEC-026: Keyword Retrieval Engine via PostgreSQL Full-Text Search
- **Decision:** Implement contract-scoped keyword retrieval (`keyword_retrieval_service.py`) using PostgreSQL native Full-Text Search. Add a stored generated `search_vector` column to `document_chunks` (`GENERATED ALWAYS AS (to_tsvector('english', text)) STORED`), indexed with a PostgreSQL GIN index (`idx_document_chunks_search_vector_gin`). Use `websearch_to_tsquery('english', query)` for safe query construction and Cover Density ranking (`ts_rank_cd`) for relevance scoring. Expose REST endpoints `POST /contracts/{contract_id}/keyword-query` and `/api/v1/contracts/{contract_id}/keyword-query`.
- **Context:** Phase 5 requires a second independent retrieval mechanism over chunk text alongside Phase 5A semantic vector retrieval, prior to hybrid fusion (Phase 5C).
- **Technical Distinction:** PostgreSQL native Full-Text Search utilizes `tsvector`, `tsquery`, and `ts_rank` / `ts_rank_cd`. It is **not** BM25 and must not be described as BM25. Cover Density ranking (`ts_rank_cd`) calculates relevance based on matching lexeme frequency and phrase proximity within the chunk text.
- **Why this decision was made:** Storing `search_vector` as a PostgreSQL generated column ensures automatic database-level synchronization whenever chunks are inserted or modified. The GIN index provides logarithmic inverted-index lookup. Using `websearch_to_tsquery` provides modern search bar query semantics (quoted phrases, negation, AND/OR logic) without throwing syntax exceptions on punctuation or arbitrary user inputs. Bounding `top_k` to `[1, 20]` with default `5` protects memory and adheres to platform conventions. Exposing `keyword_rank` separately from semantic similarity preserves transparent metric provenance. Strict contract scoping (`DocumentChunk.contract_id == contract_id`) ensures complete tenant and contract isolation.
- **Alternatives considered:** On-the-fly `to_tsvector` without a persistent column or GIN index; external search engine (Elasticsearch, OpenSearch); combined vector + keyword retrieval (deferred to Phase 5C).
- **Why alternatives were rejected:** On-the-fly `to_tsvector` requires sequential table scans for every search, degrading at scale. External search engines introduce operational complexity and break Rule 2 / Rule 10 (prefer simple, explainable architecture). Combining retrieval paths prematurely violates phase decoupling.
- **Consequences / Trade-offs:** Pure keyword search requires lexical overlap and does not capture semantic paraphrasing (which is covered by Phase 5A). Reciprocal Rank Fusion in Phase 5C will combine both complementary retrieval paths.
- **Phase:** Phase 5B
- **Date:** 2026-09-12

### DEC-027: Hybrid Retrieval Fusion via Reciprocal Rank Fusion (RRF)
- **Decision:** Combine Phase 5A semantic vector retrieval (pgvector cosine similarity) and Phase 5B keyword retrieval (PostgreSQL native Full-Text Search with `ts_rank_cd`) in a dedicated service layer (`hybrid_retrieval_service.py`) using Reciprocal Rank Fusion (RRF). Apply standard RRF formula `score = sum(1.0 / (k + rank))` with fixed smoothing constant `k = 60`. Deduplicate chunks that appear in both retrieval result sets while preserving chunk metadata, return unified `hybrid_score` and `rrf_score`, and expose transparent rank and score provenance (`semantic_rank`, `semantic_similarity`, `keyword_rank`, `keyword_score`). Support strict contract scoping, bounded `top_k` (1–20, default 5), clean handling of empty result sets, and zero vector embedding leakage. Expose REST endpoints `POST /contracts/{contract_id}/hybrid-query` and `/api/v1/contracts/{contract_id}/hybrid-query`.
- **Context:** Phase 5C requires merging dense semantic similarity (which excels at conceptual questions) and sparse lexical search (which excels at exact names, dates, numbers, and codes) into a single unified retrieval ranking ahead of Phase 5D evaluation and downstream RAG.
- **Why this decision was made:** RRF is scale-invariant and distribution-agnostic: unlike linear score combination (`alpha * sim + (1 - alpha) * kw_rank`), RRF does not require normalizing or calibrating incompatible score distributions (cosine similarity in [0, 1] vs unbounded cover density `ts_rank_cd`). The empirical constant `k = 60` (Cormack et al., 2009) is the established standard in modern search systems. Preserving each component's individual rank and score ensures transparent auditability. Deduplication guarantees chunks appearing in both candidate pools receive fused score boosts without duplicate context windows.
- **Alternatives considered:** Linear score weighting (`alpha * vector_score + (1 - alpha) * keyword_score`); vector-only retrieval; keyword-only retrieval; external cross-encoder reranker.
- **Why alternatives were rejected:** Linear weighting fails without dynamic calibration across diverse query types and violates explainability. Vector-only misses exact contractual terms and legal citations. Keyword-only fails on conceptual queries. Cross-encoder reranking introduces heavy model dependencies and inference latency (deferred as an optional post-processor in later phases).
- **Consequences / Trade-offs:** Chunks fetched from both sub-retrievers are fused in-memory; retrieval latency equals the sum (or concurrent execution) of pgvector and PostgreSQL FTS queries. Zero database schema migrations required.
- **Phase:** Phase 5C
- **Date:** 2026-09-12

### DEC-028: Deterministic Retrieval Evaluation Framework & Benchmarking Methodology
- **Decision:** Implement an offline, deterministic retrieval evaluation framework (`app.evaluation`) calculating standard Information Retrieval metrics (Precision@K, Recall@K, and MRR@K) across all three retrieval methods (semantic, keyword, and hybrid). Store a version-controlled benchmark dataset in JSON (`retrieval_eval_dataset.json`) containing realistic enterprise contract chunks, multi-class queries (semantic, keyword, hybrid), and ground-truth relevant chunk IDs. Execute evaluation using fixed orthogonal unit vectors via `MockEvalEmbeddingProvider`, guaranteeing 100% deterministic, zero-cost, zero-API-dependency test execution in CI/CD.
- **Context:** Phase 5 requires empirical verification and measurable quality metrics comparing semantic, keyword, and hybrid retrieval before proceeding to downstream RAG and structured extraction.
- **Why this decision was made:** Precision@K, Recall@K, and MRR@K are the established standards in information retrieval science. Evaluating all three methods on the same query set demonstrates the clear superiority of hybrid retrieval over standalone keyword or semantic approaches on diverse query distributions. Using deterministic orthogonal vectors isolates the retrieval logic from LLM embedding API variance and guarantees reproducible CI/CD verification.
- **Alternatives considered:** Live LLM-as-a-judge evaluation (RAGAS / TruLens); manual ad-hoc query testing; vector-only benchmarking.
- **Why alternatives were rejected:** LLM-as-a-judge introduces nondeterministic scoring, API rate limit exposure, and high token costs. Ad-hoc testing lacks regression protection and quantitative metrics.
- **Consequences / Trade-offs:** Evaluation assesses the ranking and fusion pipeline; updating the benchmark requires curating ground-truth query-chunk references in the version-controlled JSON dataset.
- **Phase:** Phase 5D
- **Date:** 2026-09-12

### DEC-029: Structured Output Infrastructure & Gemini Provider Abstraction
- **Decision:** Implement a vendor-independent structured output validation layer (`structured_output_validator.py`) and provider abstraction (`StructuredLLMProvider`) backed by Google Gemini (`GeminiStructuredOutputProvider`) via the official `google-genai` SDK. Enforce strict Pydantic v2 model validation, handle markdown code fence stripping (````json ... ````), and provide explicit custom exception hierarchies (`StructuredOutputParseError`, `StructuredOutputValidationError`, `StructuredOutputProviderError`, `StructuredOutputConfigurationError`).
- **Context:** Phase 6A requires a reusable, reliable foundation for structured LLM responses prior to implementing business schemas (clauses, obligations, facts, risk analysis).
- **Why this decision was made:** Google Gemini natively supports structured outputs (`GenerateContentConfig(response_mime_type="application/json", response_schema=schema)`), aligning with our existing Gemini embedding infrastructure (DEC-010) and avoiding secondary vendor dependencies (Rule 2). Isolating provider-specific logic behind `StructuredLLMProvider` decouples domain schemas from Gemini APIs and allows swapping providers or injecting mock clients for zero-cost, 100% deterministic test execution. A defensive post-processing validator ensures robustness against edge cases such as markdown fences, unclosed brackets, or type mismatches.
- **Alternatives considered:** Instructor library; raw unconstrained JSON prompt generation with manual regex; OpenAI Structured Outputs.
- **Why alternatives were rejected:** The Instructor library adds an external dependency that wraps SDK clients opacity and violates Rule 2 when Pydantic v2 + `google-genai` native JSON schema achieves the same goal with full transparency and zero extra weight. Unconstrained prompt parsing frequently hallucinates malformed JSON. OpenAI adds an unnecessary multi-vendor billing dependency when Gemini is already the primary AI provider.
- **Consequences / Trade-offs:** Upstream LLM responses must strictly conform to target Pydantic schemas; failures raise explicit typed exceptions that callers must handle or retry. Domain-specific schemas remain separate from the provider infrastructure.
- **Phase:** Phase 6A
- **Date:** 2026-09-13

### DEC-030: Clause Extraction Architecture & Deterministic Processing
- **Decision:** Extract contractual clauses from `DocumentChunk` records deterministically ordered by `chunk_index.asc()` using `StructuredLLMProvider` (`gemini-2.5-flash` with `ChunkClauseExtractionResult` Pydantic schema). Persist extracted clauses directly into the existing `clauses` database table preserving strict evidence lineage (`clause → chunk → page → contract`). Implement idempotent execution where rerun returns existing clauses without making redundant LLM calls unless `force_reextract=True`.
- **Context:** Phase 6B requires extracting structured legal clauses (clause type, verbatim text, section/label, page number) from document chunks ahead of downstream obligation extraction and risk analysis.
- **Why this decision was made:** Bounding clause extraction to chunk boundaries preserves 1-indexed source page provenance and chunk references. Ordering by `chunk_index.asc()` ensures deterministic document traversal. Using the Phase 6A validation layer protects the extraction pipeline against malformed JSON or schema violations. Reusing the initial database `clauses` table avoids premature migrations (Rule 1, Rule 2, Rule 10). Atomic transaction commit per contract guarantees all-or-nothing persistence with automatic rollback on error.
- **Alternatives considered:** Full-document whole-text extraction in a single prompt; regex-only clause extraction; creating new clause tables.
- **Why alternatives were rejected:** Whole-document extraction exceeds prompt context reliability on large enterprise contracts and loses granular page/chunk lineage. Regex-only extraction fails on diverse legal phrasing and boilerplate variants. Modifying or adding new clause tables is unnecessary when the existing `clauses` table schema already supports all required fields.
- **Consequences / Trade-offs:** Chunks are processed sequentially; very large contracts (e.g. 100+ chunks) take time proportional to chunk count. Future optimization could batch chunks concurrently within safe rate limits.
### DEC-031: Obligation Extraction Architecture, Schema Migration & Evidence Lineage
- **Decision:** Extract structured contractual obligations from previously extracted `Clause` records using `StructuredLLMProvider` (`gemini-2.5-flash` with `ClauseObligationExtractionResult` Pydantic schema). Apply Alembic migration (`c82e75f1b94a`) to extend `obligations` with `obligation_type` (VARCHAR(100), indexed), `deadline_info` (VARCHAR(500)), and `extraction_confidence` (FLOAT). Preserve strict 5-tier source evidence traceability (`obligation → clause → chunk → page → contract`). Implement idempotent execution where rerun returns existing obligations without invoking the LLM unless `force_reextract=True`. Expose REST endpoints `POST /contracts/{contract_id}/extract-obligations` and `GET /contracts/{contract_id}/obligations` (with versioned `/api/v1` aliases).
- **Context:** Phase 6C requires identifying, categorizing, and tracking actionable contractual obligations (title, description, responsible party, category/type, relative or absolute deadlines, frequency, and verbatim evidence text) from clauses extracted in Phase 6B.
- **Why this decision was made:** Extracting obligations from discrete, classified clauses provides focused semantic context and avoids token-window degradation. Preserving direct foreign keys to both `source_clause_id` and `source_chunk_id`, along with `page_number`, provides transparent auditability and enables the UI to deep-link directly to the exact source clause and PDF page. Adding `deadline_info` accommodates flexible relative deadlines (e.g., "within 30 days of invoice receipt", "at least 60 days prior to expiration") that cannot be coerced into a rigid calendar Date. Migration `c82e75f1b94a` was applied and verified for full downgrade reversibility on Neon PostgreSQL.
- **Alternatives considered:** Extracting obligations directly from raw document chunks; whole-document extraction; storing deadline info solely in `description`.
- **Why alternatives were rejected:** Raw chunk extraction duplicates clause parsing and risks inconsistent clause-obligation mapping. Whole-document extraction suffers from context loss and hallucination. Storing deadline text solely in description prevents programmatic filtering and deadline tracking.
- **Consequences / Trade-offs:** Obligation extraction requires clauses to exist; attempting extraction on a contract without clauses returns 400 Bad Request.
- **Phase:** Phase 6C
- **Date:** 2026-09-13

### DEC-032: Contract Fact Extraction Architecture, Schema & Evidence Lineage
- **Decision:** Extract structured contract-level facts (effective date, expiration date, contract value, payment terms, currency, parties, governing law, notice period, renewal term, termination notice period, liability cap, dispute forum, etc.) from previously extracted `Clause` records using `StructuredLLMProvider` (`gemini-2.5-flash` with `ClauseFactExtractionResult` Pydantic schema). Apply Alembic migration (`e41a982f63cb`) creating the dedicated `contract_facts` table with columns `contract_id`, `source_clause_id`, `source_chunk_id`, `fact_key`, `fact_value`, `fact_value_json`, `verbatim_evidence`, `page_number`, and `confidence`. Preserve strict 5-tier evidence lineage (`fact → source clause → chunk → page → contract`). Implement idempotent execution where rerun returns existing facts without calling the LLM unless `force_reextract=True`. Expose REST endpoints `POST /contracts/{contract_id}/extract-facts` and `GET /contracts/{contract_id}/facts` (with versioned `/api/v1` aliases).
- **Context:** Phase 6D requires extracting reliable, auditable contract-level facts to serve as input data for downstream deterministic risk rule evaluation (Phase 6E) and contract comparison.
- **Why this decision was made:** Extracting facts from classified clauses bounds the context window, produces precise clause and page citations, and prevents context dilution. Persisting facts in a dedicated `contract_facts` table with explicit foreign keys to `contracts`, `clauses`, and `document_chunks` guarantees referential integrity and transparent citation drill-down. Providing both textual `fact_value` and optional `fact_value_json` supports both scalar facts (dates, periods) and compound facts (party rosters, tiered payment terms). Strict validation prevents the LLM from hallucinating values when a fact is absent from the contract text.
- **Alternatives considered:** Whole-document fact extraction prompt; extracting facts from raw unchunked PDF text; embedding facts into `contracts` table columns.
- **Why alternatives were rejected:** Whole-document prompts lose page-level evidence lineage and suffer from context degradation on large contracts. Extracting from raw PDF bypasses clause classification. Storing facts as ad-hoc columns on `contracts` lacks flexibility for variable contractual structures and prevents 1-to-many evidence citations.
- **Consequences / Trade-offs:** Fact extraction requires clauses to exist; attempting extraction on a contract without clauses returns 400 Bad Request.
- **Phase:** Phase 6D
- **Date:** 2026-09-13

---

## 3. Pending & Undecided Decisions (To Be Documented in Future Phases)

The following architectural decisions have **not yet been made** or are partially resolved:

### DEC-011: LLM Provider for Extraction & Analysis
- **Status:** **Resolved in Phase 6A (DEC-029):** Google Gemini (`gemini-2.5-flash` via official `google-genai` SDK) selected as the primary provider with `StructuredLLMProvider` abstraction.
- **Remaining Open Question:** Secondary fallback provider (e.g. Claude 3.5 Sonnet or OpenAI GPT-4o-mini) if Gemini rate limits or availability requires redundancy.

### DEC-012: Post-Retrieval Reranking Architecture
- **Status:** **Not decided yet.**
- **Resolved in Phase 5C:** Hybrid retrieval fusion decided via Reciprocal Rank Fusion (DEC-027).
- **Remaining Open Question:** Optional secondary cross-encoder reranker (e.g. Cohere rerank or `bge-reranker`) prior to context window injection.
- **Considerations:** Latency budget vs marginal MRR/NDCG gain.

### DEC-013: Structured Output Schema & Extraction Technique
- **Status:** **Resolved across Phases 6A–6D (DEC-029, DEC-030, DEC-031, DEC-032):** Pydantic v2 schemas (`ChunkClauseExtractionResult`, `ClauseObligationExtractionResult`, `ClauseFactExtractionResult`) validated with Phase 6A infrastructure and Gemini JSON schema enforcement.

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
