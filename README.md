# Prompt Studio

A local-first workbench that turns rough ideas into structured project specifications and optimized prompts for AI coding agents (Claude Code, OpenAI Codex, Cursor) and other LLM workflows.

It runs entirely on your machine at `http://127.0.0.1:3000`. No cloud APIs, no API keys, no accounts, no telemetry. A deterministic rule-based engine provides every core feature offline; [Ollama](https://ollama.com) adds optional local-AI analysis when you ask for it.

---

## Features

| Area | What you get |
|---|---|
| **Projects** | Create, rename, edit, duplicate, archive/restore, delete (typed confirmation), search, tag filters, JSON export/import, per-project history. Explicit save with ⌘/Ctrl+S, unsaved-change guards, and conflict detection between tabs. |
| **Specification** | Rough idea (Markdown), 16 optional prompt settings (target agent, category, stack, testing, security, performance, hardware, budget, architecture, restrictions…), typed requirements (goal, functional, non-functional, security, constraint, acceptance, assumption, out-of-scope) with confirmed/proposed/unresolved/rejected status. |
| **Rule-based analysis** | 22 deterministic rules covering missing requirements, acceptance criteria, tests, security, error handling, ambiguous wording, unresolved placeholders, unstated assumptions, duplicates, contradictions (negation pairs and keyword indicators), performance and scalability risks, unpinned versions, large stacks, heavyweight architecture, and excessive scope. Each finding has a stable ID, evidence quotes, severity, confidence, impact, solution, alternative, and verification method. |
| **Recommendations** | Generated for significant findings, with problem, rationale, proposal, benefits, trade-offs, complexity, dependencies, disadvantages, and verification. You can approve (optionally editing the text or choosing an alternative), reject, defer, restore, and see the full history. Only approved items change the spec, and rejected ones are never re-proposed. |
| **Clarification** | Focused questions derived from open findings (plus optional local-AI questions). Each answer becomes a confirmed requirement. |
| **Prompt generation** | Concise / balanced / detailed variants side by side, built from a 24-section schema. Empty sections are omitted, your text is kept verbatim, template guidance is labelled, and unconfirmed assumptions are flagged. A preservation report checks that every confirmed requirement is present. |
| **Local AI (optional)** | Ollama (primary) or any OpenAI-compatible local server (LM Studio, llama.cpp `llama-server`, vLLM). Status, model list, details (context window, capabilities), selection, a memory-fit heuristic, and optional reasoning (“thinking”) for models such as qwen3. AI analysis, clarification, prompt refinement (shown as a diff, with preservation and rejected-item checks), and feasibility evaluation. Runs as cancellable background jobs with timeouts, bounded retries, schema validation, and one bounded repair attempt. |
| **Versions & library** | Immutable versions (enforced by a DB trigger). Restoring creates a new version. Line diff (unified or side-by-side), change summaries, favorites, tags, categories, duplication, content search, Markdown import. |
| **Quality diagnostics** | 10 rule-based dimensions with evidence and suggested fixes, plus a documented heuristic aggregate. Feasibility is judged only by local AI. You can compare any two evaluations. |
| **Exports** | Markdown, plain text, `CLAUDE.md`, `AGENTS.md`, Cursor `.mdc`, implementation plan, task breakdown, testing instructions, project spec, reusable template, or a ZIP of agent files. All work offline. |
| **Templates** | 8 built-in task templates plus your own: create, edit, duplicate a built-in, or save a project as a template. Template requirements always arrive as “proposed”. |
| **Agent handoff** | Writes the agent’s instruction file (`CLAUDE.md`, `AGENTS.md` or `.cursor/rules/*.mdc`) plus `.prompt-studio/PROMPT.md` and `TASKS.md` into a folder you choose. You see a preview first and must authorize it; existing files are kept unless you tick overwrite (backup first). It shows the command to start the agent for you to copy — it never runs anything. |
| **Codebase context** | Read-only scan of a directory you choose. It excludes secrets, dependency/build dirs, binaries, large files, and `.gitignore` entries, never follows symlinks, shows a preview, redacts likely secrets, and inserts a summary into the project. |
| **Data management** | Backups (SQLite online backup), validation (integrity, schema, foreign keys), and restore with a confirmation step and an automatic safety backup. Delete-all-data and a CLI. |

Everything AI-generated is labelled **Local AI · model**. Deterministic output is labelled **Rule-based**, and your edits **Manual**.

## Architecture

```
Browser ──► Next.js 16 (127.0.0.1:3000) ──/api/* proxy──► FastAPI (127.0.0.1:8000) ──► SQLite (data/)
                                                              └─ on request ─► Ollama (127.0.0.1:11434)
```

- `apps/api`: Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, SQLite. Business logic lives in `services/`. Pure deterministic logic lives in `engine/` (analyzer, recommendations, optimizer, evaluator, templates, export). Model access sits behind `providers/`.
- `apps/web`: Next.js App Router, React 19, TypeScript (strict), Tailwind CSS 4. It is a presentation layer only; a same-origin route handler proxies `/api/*` to the backend.
- `tests/e2e`: Playwright tests against real servers.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the design, data model, and trade-offs.

## Prerequisites

| Tool | Version tested | Notes |
|---|---|---|
| Node.js | 24.11 (≥ 20.9 required) | npm 11 |
| Python | 3.13.9 (≥ 3.12 required) | |
| [uv](https://docs.astral.sh/uv/) | 0.12 | Python package manager (`brew install uv`) |
| Ollama | 0.40.4 | **Optional**, for local AI |

**Supported OS:** developed and tested on macOS 26 (Apple Silicon). The code is cross-platform (Linux and Windows should work), but **only macOS has been tested**.

Docker is not required.

## Installation

```bash
npm run setup
```

This runs `uv sync` (backend), `npm ci` (frontend and test runner), and initialises the database. It does not install system tools or download models.

<details><summary>Manual setup without the script</summary>

```bash
cd apps/api && uv sync && uv run python -m prompt_studio.cli init-db
cd ../web && npm ci
```

Without uv: `cd apps/api && python3 -m venv .venv && .venv/bin/pip install -e .`, then run uvicorn from `.venv/bin`.
</details>

## Starting and stopping

```bash
npm run dev
```

This starts the backend and frontend together, checks ports first, and prints the URL: **http://127.0.0.1:3000**. Press **Ctrl+C** to stop both.

```bash
npm start
```

This is production mode: it builds the frontend first.

To run the pieces separately:

```bash
cd apps/api && uv run uvicorn prompt_studio.main:app --host 127.0.0.1 --port 8000
```

```bash
cd apps/web && PROMPT_STUDIO_API_URL=http://127.0.0.1:8000 npx next dev --hostname 127.0.0.1 --port 3000
```

Configuration is read from environment variables or a `.env` file (copy [.env.example](.env.example)). No API keys exist or are needed.

## Ollama setup (optional)

1. Install Ollama from https://ollama.com/download, or run `brew install ollama`.
2. Start it: open the Ollama app, or run `ollama serve`.
3. Download a model yourself. Prompt Studio never downloads models. For example:
   - `ollama pull qwen3:8b` (about 5.2 GB, validated)
   - `ollama pull qwen3:4b` (about 2.5 GB, smaller and faster, not validated)
4. In Prompt Studio, open **Local Models**, click **Re-check**, then **Select** a model.

**Validated model:** `qwen3:8b` (Ollama, Q4_K_M, ≈5.2 GB) was run through every local-AI feature on a 16 GB Apple Silicon Mac. See [docs/MODEL_VALIDATION.md](docs/MODEL_VALIDATION.md) for measured timings and observed quality. Other models have not been validated.

**Other local runtimes:** in Settings → Local AI runtime, choose “OpenAI-compatible local server” and enter its URL (LM Studio default `http://127.0.0.1:1234`, llama.cpp `llama-server` default `http://127.0.0.1:8080`). No API key is ever sent. This runtime is tested against a mock server only.

**Model selection:** the Local Models page suggests a model for a speed/balanced/quality preference. It compares download size + 20% against total memory. That is a rough heuristic, not a benchmark. Real memory use depends on quantization, context length (`num_ctx`, see Settings), and architecture. Not every model follows JSON schemas reliably; invalid output is detected, repaired once, and otherwise reported. Nothing invalid is stored.

## Running tests

```bash
npm run test:api       # backend: pytest
npm run test:web       # frontend: Vitest + Testing Library
npx playwright install chromium   # once, for E2E
npm run test:e2e       # Playwright E2E against real servers on ports 8100/3100
npm run check          # lint + typecheck + all of the above
npm run test:e2e:real-model   # opt-in: drives the local-AI UI against a real Ollama model (default qwen3:8b)
```

Validate local-AI features against a real model (uses a throwaway database):

```bash
cd apps/api && uv run python scripts/validate_model.py --model qwen3:8b
```

## Data location, backup and restore

- The database lives at `data/prompt_studio.db` (override with `PROMPT_STUDIO_DATA_DIR`). Backups go in `data/backups/`.
- **In the UI:** Settings → Backups → Create / Validate / Restore (type `RESTORE`) / Delete.
- **On the CLI** (stop the app before restoring):
  ```bash
  cd apps/api && uv run python -m prompt_studio.cli backup
  ```
  ```bash
  cd apps/api && uv run python -m prompt_studio.cli list-backups
  ```
  ```bash
  cd apps/api && uv run python -m prompt_studio.cli validate-backup <name>
  ```
  ```bash
  cd apps/api && uv run python -m prompt_studio.cli restore-backup <name>
  ```
- Restore and delete-all-data both create a safety backup first. For off-machine safety, copy `data/backups/` elsewhere.
- **Recovery:** if the database is corrupt, stop the app and restore a validated backup with the CLI. If no backup exists, move the broken `prompt_studio.db` aside; a fresh one is created on the next start.

## Offline usage

After `npm run setup` (and any model downloads), the app needs no network access. The rule-based engine makes no network calls, and the UI's Content-Security-Policy only allows its own origin. See [Test evidence](#status-and-test-evidence) for what was verified and how.

## Privacy and security

See [docs/PRIVACY.md](docs/PRIVACY.md) and [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md). In short:

- Both servers bind to `127.0.0.1`. There is no telemetry and no cloud provider, and the app never falls back to one.
- The API rejects non-loopback `Host` headers (DNS-rebinding defence, applied at both the proxy and the API). Mutating requests need a custom header, and any `Origin` must be allowed (CSRF defence). The API emits no CORS headers.
- Optional `PROMPT_STUDIO_API_TOKEN` blocks other local processes. The proxy injects it server-side.
- Request size limits, strict input validation, and generic error messages. Logs never contain prompt content.
- Markdown is sanitized (no raw HTML, safe URLs only, images not loaded).
- **Limitations:** localhost is not a complete security boundary. Other software running as your user can read the unencrypted database file, so use full-disk encryption. Local model output can be wrong or influenced by injected text, which is why it is always a suggestion requiring approval.

## Troubleshooting

| Problem | Fix |
|---|---|
| `port 8000/3000 is already in use` | Run `lsof -iTCP:8000 -sTCP:LISTEN` to find the process, or use `PROMPT_STUDIO_API_PORT=8001 PROMPT_STUDIO_WEB_PORT=3001 npm run dev` |
| `Another next dev server is already running` | Stop the other `next dev` started from `apps/web` |
| UI says "Backend unreachable" | Check the `[api]` output. Run `npm run setup` if dependencies are missing |
| "Ollama is not reachable" | Start the Ollama app or run `ollama serve`. Check the endpoint in Settings |
| "Selected model is not installed" | Run `ollama pull <model>`, or select another model |
| Local AI is slow or times out | Use a smaller model, lower `num_ctx`, or raise the timeout in Settings. Cancel any running job |
| "Requests must use a loopback host name" | Open `http://127.0.0.1:3000`, not a LAN IP or custom hostname |
| `uv: command not found` | Run `brew install uv` or see https://docs.astral.sh/uv/ |

## Development workflow

- Backend code goes in `services/` (I/O) and `engine/` (pure, deterministic). Keep the routers thin.
- Schema changes go through `apps/api/models.py`. Generate a migration with `cd apps/api && uv run alembic revision --autogenerate -m "..."`, review it, and commit it.
- Frontend types in `apps/web/src/lib/types.ts` mirror `apps/api/prompt_studio/schemas.py`.
- Run `npm run check` before committing.

## Status and test evidence

Last full run: 2026-10-15, macOS 26.6 arm64.

| Check | Result |
|---|---|
| `npm run lint:api` (ruff check + format) | pass |
| `npm run typecheck` (tsc strict) | pass |
| `npm run test:api` | **131 passed** |
| `npm run test:web` | **24 passed** |
| `npm run test:e2e` | **6 passed**, 1 opt-in skipped (Chromium, production build) |
| `npm run test:e2e:real-model` | **1 passed** against real `qwen3:8b` (opt-in; needs the model) |
| `next build` | pass |

**Offline evidence:**
- `apps/api/tests/api/test_offline.py` runs the full workflow (fresh DB, no API keys, Ollama on a closed port) with every non-loopback socket connection and DNS lookup blocked, and asserts zero external attempts.
- The Playwright suite aborts and records every non-loopback browser request, and asserts there were none.

These checks prove the app makes no external connections in those workflows. **The app was not tested on a physically disconnected machine** (airplane mode).

**Local AI evidence:** automated tests run against a programmable mock of the Ollama API and of an OpenAI-compatible server (valid output, malformed output plus repair, double failure, transient 503 retry, connection loss, cancellation, duplicate-job prevention, thinking flag). Real-model behaviour was measured separately with `apps/api/scripts/validate_model.py` against `qwen3:8b` on Ollama 0.40.4; results are in [docs/MODEL_VALIDATION.md](docs/MODEL_VALIDATION.md). The OpenAI-compatible runtime has **not** been tested against a real LM Studio or llama.cpp server.

## Known limitations

- Rule-based analysis is heuristic (keyword and structure checks). It misses issues and produces false positives. Contradiction detection is limited to negation pairs and a few keyword pairs.
- Token counts are estimates, not tokenizer output.
- Local-AI jobs live in memory and are lost if the backend restarts.
- Codebase scanning supports only the root `.gitignore`, and only plain glob patterns (no negation, no nested files).
- Single user. No auth beyond the optional token. The database is not encrypted.
- Agent instruction-file conventions were verified against official docs on 2026-10-15 and may change. Profiles are versioned in `engine/templates/profiles.py`.
- Local-AI analysis quality depends heavily on the model. With `qwen3:8b` it tends to report few findings and to over-rate severity (see docs/MODEL_VALIDATION.md); treat it as a second opinion next to the rule-based checks.
- Only macOS has been tested locally; CI runs the test suites on Ubuntu.

## Roadmap

- Validate more local models (e.g. `qwen3:4b`, coder-tuned models) with `scripts/validate_model.py` and publish the results.
- Editable agent export profiles.
- Nested `.gitignore` and negation support for codebase scans.
- Streaming progress for long local-AI jobs.
