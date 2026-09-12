# AGENTS.md — Agent & Developer Operational Protocol

Welcome to **ContractIQ** (Evidence-First Contract Intelligence and Risk Analysis Platform).
This document establishes the mandatory operational rules, verification procedures, and handoff protocols for any AI agent or human developer working on this codebase.

---

## 1. Handoff & Session Continuation Protocol

When an AI session begins or switches (e.g., due to token limits or context resets), the agent **MUST** execute the following sequence before proposing or modifying any code:

1. **Read `AGENTS.md`** (this document) to review operating rules and constraints.
2. **Read `README.md`** for project context and architecture baseline.
3. **Read `DECISIONS.md`** to know what has been decided, what was rejected, and what is still undecided.
4. **Read `FLOW.md`** to understand both the current application flow and the planned system flow.
5. **Read `PHASE_STATUS.md`** to find the exact phase, progress, and immediate next task.
6. **Inspect Git status and branches** (`git status`, `git branch -a`, `git remote -v`).
7. **Inspect recent Git commits** (`git log --oneline -n 10`).
8. **Inspect relevant source files** directly before editing them.
9. **Verify the current implementation** (`npm run build` or appropriate test command).
10. **Only then continue development** according to the next action defined in `PHASE_STATUS.md`.

> [!IMPORTANT]
> Never assume previous chat history is available.
> Never ask the user to explain previous implementation if the information can be recovered from the repository.

---

## 2. The 12 Mandatory Development Rules

All agents and contributors must strictly adhere to these 12 core rules:

* **RULE 1:** Never rebuild working functionality without an explicit, documented technical reason.
* **RULE 2:** Never introduce a library when the existing stack or standard library can reasonably solve the problem.
* **RULE 3:** Do not fabricate functionality or pretend an unimplemented backend or AI feature is functioning. Clearly label mock data and simulated pipelines as such.
* **RULE 4:** Every phase must end in a verified working state (builds without error, tests pass, clean git diff).
* **RULE 5:** Every meaningful architectural decision must be recorded in `DECISIONS.md`.
* **RULE 6:** Every meaningful system-flow change must be recorded in `FLOW.md`.
* **RULE 7:** `PHASE_STATUS.md` must always identify the exact current project state, completed tasks, blockers, and next steps.
* **RULE 8:** Never silently change architectural decisions from previous phases.
* **RULE 9:** If a previous decision must be changed, document:
  - Old decision
  - Reason for change
  - New decision
  - Consequences and trade-offs
* **RULE 10:** Prefer simple, explainable architecture over unnecessary enterprise complexity.
* **RULE 11:** The final system must be understandable and defensible by a B.Tech student in an engineering interview.
* **RULE 12:** Do not turn ContractIQ into a generic chatbot. The core design principle is:
  - **RAG finds evidence.**
  - **Structured extraction turns evidence into data.**
  - **Deterministic rules turn structured data into actionable risk intelligence.**
  - Answers must always link to verifiable, page-level clause citations.

---

## 3. Git Safety Rules

* **Never force push** (`git push --force` or `-f`).
* **Never perform a hard reset** (`git reset --hard`) on tracked commits unless explicitly requested by the user.
* **Never delete or modify the Git remote** (`origin`).
* **Always run `git status`** before touching files.
* **Always review `git diff`** before staging or committing changes.
* Keep commits focused, descriptive, and atomic per phase.

---

## 4. Verification and Build Standards

Before marking any task or phase complete:
1. Run the project build:
   ```bash
   npm run build
   ```
2. Run TypeScript checks:
   ```bash
   npx tsc
   ```
3. If unit or integration tests exist, execute them and ensure 100% pass.
4. Verify there are no console errors, dead links, or unresolved imports.
