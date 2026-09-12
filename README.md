# ContractIQ — Evidence-First Contract Intelligence and Risk Analysis Platform

> **Status:** Phase 0 (Baseline Audit & Project Memory Established)  
> **Repository Remote:** `https://github.com/vasaakhilvignesh/ContractAi.git`

---

## 1. Project Overview

**ContractIQ** is an evidence-first contract intelligence platform designed to move far beyond generic "chat with your PDF" interfaces. It provides auditable, deterministic, and verifiable intelligence across enterprise contract portfolios.

### Core Architectural Principle

```
RAG finds evidence.
Structured extraction turns evidence into data.
Deterministic rules turn structured data into actionable intelligence.
```

- **Semantic understanding:** Large Language Models (LLMs) are used strictly where natural language parsing is required—extracting specific clauses, dates, values, and obligations with exact page-level citations.
- **Deterministic logic:** Application code and rule engines evaluate business and legal risk conditions (e.g. *if notice period < 30 days, trigger CRITICAL risk*). The LLM does **not** guess risk severity nondeterministically.
- **Evidence lineage:** Every risk flag, obligation, and answer must trace directly to a verifiable clause and page number in the original contract document.
- **Unambiguous fallback:** If evidence is insufficient or absent, the system explicitly returns "not found" rather than generating speculative answers.

---

## 2. Architecture Baseline

### Current Implemented Architecture (Frontend Baseline)

| Layer | Technology | Details |
| :--- | :--- | :--- |
| **Frontend Framework** | React 19 (`react` 19.0.0, `react-dom` 19.0.0) | StrictMode enabled, functional components with hooks |
| **Language** | TypeScript 5.7 (`strict: true`) | Target ES2020, bundler module resolution, path alias `@/*` |
| **Build Tooling** | Vite 8 (`@vitejs/plugin-react`) | Development server and production bundler (`port: 8443`, `host: 0.0.0.0`) |
| **Routing** | React Router v7 (`react-router-dom` 7.18.3) | Client-side `BrowserRouter` with nested `<Shell />` layout and route-driven navigation |
| **Styling & Design System** | Tailwind CSS v4 (`@tailwindcss/vite`) | Utility-first with CSS variables in `src/index.css` (`--primary`, `--accent`, `--risk-*`), Inter and JetBrains Mono typography |
| **Mock Data Layer** | In-memory TypeScript definitions (`src/data/mock.ts`) | Strongly typed models for `Contract`, `Risk`, `Obligation`, `AuditEvent`, and status enums |

### Planned Target Architecture *(PLANNED — Not Yet Implemented)*

| Component | Planned Technology / Strategy | Status |
| :--- | :--- | :--- |
| **Backend API** | Python (FastAPI) or Node.js REST API | *PLANNED* |
| **Primary Database** | PostgreSQL | *PLANNED* |
| **Vector Database** | `pgvector` extension for PostgreSQL | *PLANNED* |
| **Document Processing** | PDF text extraction preserving page boundaries & tables | *PLANNED* |
| **Chunking Engine** | Clause-aware semantic chunking with page metadata | *PLANNED* |
| **Retrieval Pipeline** | Hybrid Search (pgvector semantic similarity + PostgreSQL tsvector keyword search) + Reranking | *PLANNED* |
| **LLM Orchestration** | Gemini / OpenAI with strict Structured Outputs (JSON Schema / Pydantic) | *PLANNED* |
| **Risk Rules Engine** | Deterministic business rules evaluating extracted structured facts | *PLANNED* |
| **Authentication & RBAC** | Per-user document isolation and role-based permissions | *PLANNED* |

---

## 3. Directory Structure

```
Contract Intelligence Dashboard/
├── AGENTS.md                  # Permanent agent operating rules & handoff protocol
├── DECISIONS.md               # Architectural Decision Records (ADRs)
├── FLOW.md                    # Current application flow & planned system architecture
├── PHASE_STATUS.md            # Progress tracker, known issues, and next phase actions
├── README.md                  # This architecture baseline and setup guide
├── index.html                 # HTML entry point
├── package.json               # Project manifest and scripts
├── tsconfig.json              # TypeScript configuration
├── vite.config.ts             # Vite bundler and dev server configuration
└── src/
    ├── App.tsx                # Client-side router configuration
    ├── index.css              # Global styles, fonts, and Tailwind v4 theme variables
    ├── main.tsx               # Application root mount point
    ├── vite-env.d.ts          # Vite client types
    ├── components/
    │   ├── layout/
    │   │   ├── Header.tsx     # Breadcrumbs, search bar, notifications popover, upload button
    │   │   ├── Shell.tsx      # Persistent layout shell (Sidebar + Header + Outlet)
    │   │   └── Sidebar.tsx    # Workspace navigation links, branding, user profile
    │   └── ui/
    │       └── Badge.tsx      # RiskBadge, StatusBadge, PriorityBadge reusable components
    ├── data/
    │   └── mock.ts            # Centralized TypeScript mock domain entities
    └── pages/
        ├── Compare.tsx        # Cross-contract comparison matrix with diff highlighting
        ├── ContractOverview.tsx # Detailed contract view (Overview, Clauses, Obligations, Risks)
        ├── Contracts.tsx      # Contract library with search, filtering, and sorting
        ├── Dashboard.tsx      # Executive overview with KPIs, renewals, and risk signals
        ├── Obligations.tsx    # Obligation tracking center with filtering and detail drawer
        ├── RiskMonitor.tsx    # Deterministic risk monitor with severity cards and evidence drawer
        └── UploadContract.tsx # 4-stage contract upload and processing pipeline simulation
```

---

## 4. Getting Started

### Prerequisites
- Node.js (v18.x, v20.x, or later recommended)
- npm (v9.x or later)

### Installation
```bash
npm install
```

### Running the Development Server
```bash
npm run dev
```
The application will start on `http://localhost:8443`.

### Production Build & Type Checking
```bash
# Verify TypeScript types
npx tsc

# Create production build
npm run build

# Preview production build locally
npm run preview
```

---

## 5. Project Memory Documentation

The repository maintains strict operational documentation to ensure consistency across sessions and AI agent handoffs:

1. [**`AGENTS.md`**](./AGENTS.md): Mandatory rules of engagement, 12 development rules, and session continuation order.
2. [**`DECISIONS.md`**](./DECISIONS.md): Architectural decision records documenting what was decided, alternatives rejected, and undecided items.
3. [**`FLOW.md`**](./FLOW.md): Step-by-step application flows and planned production data pipelines.
4. [**`PHASE_STATUS.md`**](./PHASE_STATUS.md): Real-time phase status, verification log, and immediate next action.