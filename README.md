# ContractIQ — Evidence-First Contract Intelligence and Risk Analysis Platform

> **Status:** Phase 20 Complete (Production Deployment, Packaging & Configuration Hardened)
> **Repository Remote:** `https://github.com/vasaakhilvignesh/ContractAi.git`

---

## 1. Project Overview

**ContractIQ** is an enterprise contract intelligence platform built on the principle that contract risk analysis must be auditable, deterministic, and traceable to exact source clauses. It moves far beyond generic "chat with your PDF" interfaces by decoupling evidence retrieval from risk evaluation.

### Core Architectural Principle

```
RAG finds evidence.
Structured extraction turns evidence into data.
Deterministic rules turn structured data into actionable risk intelligence.
```

- **Semantic understanding:** Large Language Models (LLMs) are used strictly where natural language parsing is required—extracting specific clauses, dates, values, and obligations with exact page-level citations.
- **Deterministic logic:** Application code and rule engines evaluate business and legal risk conditions (e.g. *if notice period < 30 days, trigger CRITICAL risk*). The LLM does **not** guess risk severity nondeterministically.
- **Evidence lineage:** Every risk flag, obligation, and answer traces directly to a verifiable clause and 1-indexed page number in the original contract document.
- **Unambiguous fallback:** If evidence is insufficient or absent, the system explicitly returns "not found" or unsupported claim status rather than generating speculative answers.

---

## 2. Production Architecture

| Layer | Technology | Details |
| :--- | :--- | :--- |
| **Frontend Framework** | React 19 (`react` 19.0.0, `react-dom` 19.0.0) | Functional components with hooks, strict mode, modular services |
| **Language (Frontend)** | TypeScript 5.7 (`strict: true`) | Target ES2020, bundler module resolution, path alias `@/*` |
| **Build Tooling** | Vite 8 (`@vitejs/plugin-react`) | Fast HMR in development, optimized static bundle in production |
| **Routing** | React Router v7 (`react-router-dom` 7.18.3) | Client-side `BrowserRouter` with nested `<Shell />` layout and SPA rewrite support |
| **Styling & Design System** | Tailwind CSS v4 (`@tailwindcss/vite`) | Utility-first with CSS variables (`--primary`, `--accent`, `--risk-*`), Inter typography |
| **Backend API** | Python 3.13 + FastAPI (`fastapi==0.115.5`, `uvicorn==0.32.1`) | High-performance ASGI framework with CORS, lifespan startup/shutdown, and route grouping |
| **Database ORM & Driver** | SQLAlchemy 2.0 (`sqlalchemy==2.0.36`) + `psycopg2-binary==2.9.10` | DeclarativeBase, pool pre-ping, SSL connection pooling, composite indexes |
| **Primary Database** | Neon Serverless PostgreSQL 18.6 | Cloud-managed PostgreSQL (`neondb`, branch `production`) with SSL pooling |
| **Vector Extension** | `pgvector` 0.8.6 | 768-dimensional vector embeddings with cosine similarity distance search |
| **Migration Tooling** | Alembic (`alembic==1.14.0`) | Automated database versioning; migration `f31920b7c102` applied |
| **AI / LLM Engine** | Google Gemini API via official SDK | Structured outputs with `gemini-3.8-flash`; 768-dim embeddings with `text-embedding-004` |
| **Retrieval Pipeline** | Hybrid Search (pgvector + tsvector) | Reciprocal Rank Fusion (RRF) combining semantic vector scoring and full-text keyword rank |
| **Security & Auth** | JWT (HS256) + Tenant Scoping | IDOR defense across all endpoints, strict file upload magic-byte validation, prompt injection shields |
| **Observability** | Correlation IDs & Safe Structured Logging | `RequestIDMiddleware` (`X-Request-ID`), stage timing, `SafeLoggingFilter` credential scrubbing |
| **Containerization** | Docker (Python 3.13-slim) | Non-root `appuser`, pre-flight migration entrypoint (`backend/start.sh`), automated healthcheck |
| **Cloud Hosting** | Render Blueprint / Docker Compose / Vercel | Dual-service architecture (FastAPI Web Service + React Static Site) |

---

## 3. Directory Structure

```
Contract Intelligence Dashboard/
├── AGENTS.md                  # Permanent agent operating rules & handoff protocol
├── DECISIONS.md               # Architectural Decision Records (ADRs)
├── FLOW.md                    # Current application flow & planned system architecture
├── PHASE_STATUS.md            # Progress tracker, known issues, and next phase actions
├── README.md                  # Architecture baseline and production operations guide
├── render.yaml                # Render Infrastructure-as-Code Blueprint (Dual Service)
├── docker-compose.prod.yml    # Production Docker Compose multi-container stack
├── vercel.json                # Vercel SPA client rewrite configuration
├── .env.example               # Root frontend environment template (VITE_API_BASE_URL)
├── package.json               # Frontend manifest and build scripts
├── vite.config.ts             # Vite bundler and development server configuration
├── public/                    # Static assets copied verbatim to dist/
│   ├── _redirects             # SPA fallback rewrite rule (/* /index.html 200)
│   └── robots.txt             # Search engine crawling rules
├── src/                       # React 19 Frontend Application
│   ├── App.tsx                # Client-side router configuration & protected routes
│   ├── components/            # Reusable UI components, modals, layout shells
│   ├── pages/                 # Full-page route views (Dashboard, Contracts, Analyst, etc.)
│   └── services/              # API clients with dynamic VITE_API_BASE_URL resolution
└── backend/                   # FastAPI Backend Application
    ├── Dockerfile             # Production container definition (Python 3.13-slim, non-root)
    ├── start.sh               # Production startup script (alembic upgrade head + uvicorn)
    ├── alembic/               # Migration scripts and version history
    ├── app/                   # Core application package
    │   ├── api/               # Versioned REST routers (auth, contracts, analyst, etc.)
    │   ├── core/              # Config, security, safe logging filter, secret scanner
    │   ├── db/                # Database engine session factory and pgvector registration
    │   ├── evaluation/        # Offline RAG evaluation benchmark suite & metrics
    │   ├── models/            # SQLAlchemy 2.0 ORM models
    │   ├── schemas/           # Pydantic v2 schemas and structured output models
    │   └── services/          # Business logic: ingestion, hybrid search, RAG, rules
    ├── tests/                 # Backend automated test suite (pytest)
    └── requirements.txt       # Python dependencies
```

---

## 4. Environment Variables Reference

### Frontend Configuration (`.env` in root)

| Variable | Required | Default | Description |
| :--- | :--- | :--- | :--- |
| `VITE_API_BASE_URL` | No | Empty (uses `/api/v1` relative proxy) | Target API origin in production (e.g. `https://contractiq-api.onrender.com/api/v1`) |

### Backend Configuration (`backend/.env`)

| Variable | Required in Prod | Default (Dev) | Description |
| :--- | :--- | :--- | :--- |
| `APP_ENV` | Yes | `development` | Set to `production` in live environments. Enforces security validators. |
| `APP_DEBUG` | Yes | `True` | Must be `False` in production (auto-enforced if `APP_ENV=production`). |
| `DATABASE_URL` | Yes | *None* | PostgreSQL connection string (`postgresql+psycopg2://...`). |
| `GEMINI_API_KEY` | Yes | *None* | Google Gemini API key for structured extraction and embeddings. |
| `JWT_SECRET_KEY` | Yes | *Dev placeholder* | Secret for signing auth tokens (must be $\ge 32$ chars in production). |
| `CORS_ORIGINS` | Yes | `http://localhost:5173,...` | Comma-separated list of allowed frontend origins (no wildcards in prod). |
| `GEMINI_MODEL_STRUCTURED` | No | `gemini-3.8-flash` | Gemini model name for structured JSON fact extraction. |
| `GEMINI_MODEL_EMBEDDING` | No | `text-embedding-004` | Gemini model name for 768-dim vector embeddings. |

---

## 5. Production Deployment Guide

### Option A: Render Blueprint Deployment (Recommended)

ContractIQ includes a turnkey `render.yaml` Blueprint that deploys both the backend API and frontend static site with zero manual wiring:

1. Connect your repository `vasaakhilvignesh/ContractAi` to [Render](https://render.com).
2. Create a **New Blueprint Instance** and select the repository.
3. Render automatically provisions:
   - **`contractiq-api`**: FastAPI Web Service running `backend/start.sh` with automatic database migrations and health checking against `/health/liveness`.
   - **`contractiq-web`**: Static Site building with `npm install && npm run build`, publishing `dist`, and routing all client paths via `public/_redirects`.
4. Provide the following environment variables in the Render Dashboard for `contractiq-api`:
   - `DATABASE_URL`: Your Neon PostgreSQL connection string.
   - `GEMINI_API_KEY`: Your Google Gemini API key.
   - `JWT_SECRET_KEY`: A high-entropy random string (at least 32 characters, e.g. `openssl rand -hex 32`).
   - `CORS_ORIGINS`: The URL of your `contractiq-web` instance (e.g. `https://contractiq-web.onrender.com`).

---

### Option B: Production Docker Deployment

To run the complete production backend container locally or on a cloud virtual machine:

```bash
# 1. Clone the repository
git clone https://github.com/vasaakhilvignesh/ContractAi.git
cd ContractAi

# 2. Configure backend environment
cp backend/.env.example backend/.env
# Edit backend/.env with your production credentials

# 3. Build and launch the container
docker compose -f docker-compose.prod.yml up -d --build

# 4. Verify running services and health probe
docker compose -f docker-compose.prod.yml ps
curl -i http://localhost:8000/health/liveness
curl -i http://localhost:8000/health/readiness
```

---

### Option C: Frontend Deployment on Vercel / Netlify

The frontend can be independently hosted on any edge static provider:

1. **Root Directory:** Project root (`./`).
2. **Build Command:** `npm run build`.
3. **Output Directory:** `dist`.
4. **Environment Variable:** `VITE_API_BASE_URL=https://<your-backend-api-domain>/api/v1`.
5. Client-side routing is handled automatically:
   - For **Vercel**: Handled by the included [`vercel.json`](./vercel.json).
   - For **Netlify / Render**: Handled by the included [`public/_redirects`](./public/_redirects).

---

## 6. Local Development Quickstart

### Frontend Development
```bash
# Install dependencies
npm install

# Run Vite development server (http://localhost:5173 or :8443)
npm run dev

# Verification commands
npm run build
npx tsc --noEmit
```

### Backend Development
```bash
cd backend

# Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # Windows
# source .venv/bin/activate    # Linux/macOS

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Neon DATABASE_URL and GEMINI_API_KEY

# Run database migrations
alembic upgrade head

# Run automated tests
pytest tests/ -v

# Start FastAPI development server
uvicorn app.main:app --reload --port 8000
```

---

## 7. Project Memory & Governance Documentation

ContractIQ enforces strict operational governance across all phases:

1. [**`AGENTS.md`**](./AGENTS.md): Mandatory rules of engagement, 12 development rules, and session continuation protocols.
2. [**`DECISIONS.md`**](./DECISIONS.md): Comprehensive Architectural Decision Records (ADRs DEC-001 through DEC-045).
3. [**`FLOW.md`**](./FLOW.md): Complete application flows, prompt injection defenses, observability, and production deployment topology.
4. [**`PHASE_STATUS.md`**](./PHASE_STATUS.md): Roadmap tracking all 20 phases from baseline through production delivery.
