# Prompt Studio — Implementation Plan

Each phase ends with: tests executed, results recorded in `docs/TEST_PLAN.md`
§Evidence, and known issues listed here.

## Phase 0 — Inspection & architecture ✅
* Environment inspected (2026-10-15): macOS 26.6 arm64, 16 GB RAM, Node 24.11,
  npm 11.6, pnpm 10.28, Python 3.13.9, uv 0.12.23, Git 2.54. Repository empty.
  Ollama: initially not detected (not on PATH, port 11434 closed); later found
  as `/Applications/Ollama.app` v0.40.4, which started and installed its CLI
  at `/usr/local/bin/ollama`. **No models installed.** Ports 3000/8000 free.
* Dependency versions verified against registries: Next 16.4.1, React 19.3.1,
  Tailwind 4.3.3, TypeScript 5.9.3, Vitest 5, Playwright 1.64; FastAPI 0.143,
  Pydantic 2.14, SQLAlchemy 2.1, Alembic 1.20, uvicorn 0.54, httpx 0.28, pytest 9.
* Docs: ARCHITECTURE, REQUIREMENTS, THREAT_MODEL, PRIVACY, TEST_PLAN, this file.

## Phase 1 — Functional vertical slice
Backend: config, DB + migrations, security middleware, projects/tags/events,
requirements, rule-based analyzer, prompt builder, versions, Markdown/text export.
Frontend: shell (sidebar, status bar, theme), dashboard, projects list, project
workspace (idea, config, requirements, analysis, preview, copy/export).
Scripts: `setup`, `dev`, `test`. README.

## Phase 2 — Local AI integration
Ollama provider (status, list, show, chat with JSON schema), settings, models
page, AI job runner (semaphore, cancel, timeouts, bounded retries), AI analysis
with validation + repair, AI optimization with preservation check,
clarification questions, honest labelling.

## Phase 3 — Prompt engineering workspace
Recommendations (approve/reject/edit/defer/restore/alternatives/history),
variants side-by-side, quality evaluation + compare, prompt library, version
history + diff + restore, agent profiles and all export formats, templates.

## Phase 4 — Security & data management
Backups (create/validate/restore/delete), delete all data, import validation,
security tests, offline test, E2E tests, privacy docs.

## Phase 5 — Advanced (only after 0–4 pass)
Local codebase context (explicit directory approval, ignore rules, secret
exclusion, symlink/traversal protection, preview). Custom templates.
Additional local runtimes. **Status is tracked in the table below.**

## Status (2026-10-15)

| Phase | Status | Evidence / notes |
|---|---|---|
| 0 | Done | Environment inspected; versions verified; all docs created |
| 1 | Done | Shell, projects, SQLite + migrations, idea editor, templates, rule-based analysis, preview, copy/export, scripts, README |
| 2 | Done (mock-verified) | Ollama provider, model list/details/selection, AI jobs (cancel, timeout, bounded retry, concurrency limit, dedupe), validated structured output with one repair, AI analysis/clarify/refine/feasibility. Tested against a mocked Ollama API; real Ollama 0.40.4 verified for status/listing only (no models installed) |
| 3 | Done | Requirements editor, approval workflow with alternatives + history, variants side by side, preservation report, diagnostics + compare, library, immutable versions, diff, restore, agent profiles + 10 export formats + ZIP |
| 4 | Done | Backups (create/validate/restore/delete + CLI), delete-all, import validation, security tests, offline tests, E2E |
| 5 | Partial | **Done:** local codebase context (read-only scan, exclusions, symlink/traversal protection, preview, redaction, summary). **Not done:** custom templates, additional local runtimes, coding-agent handoff |

### Decisions made during implementation

* AI operations run as in-memory async jobs (`/api/ai/jobs`) so they are cancellable and never block HTTP requests; the UI polls job status.
* The frontend proxy is a Next.js route handler (not `rewrites`) so it can enforce the loopback Host check, inject the optional API token server-side and propagate aborts.
* Timestamps are stored as naive UTC in SQLite and returned as timezone-aware UTC (`UTCDateTime` type) — found via manual testing (relative times were off by the local UTC offset).
* `existing_codebase` accepts up to 100k characters (codebase summaries) and is treated as context, not requirements, by the analyzer.
* Recommendations whose requirement text contains a `[bracketed placeholder]` cannot be approved until edited.
