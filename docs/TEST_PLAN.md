# Prompt Studio — Test Plan

## Levels

| Level | Tool | Location | Command |
|---|---|---|---|
| Backend unit (engine, services) | pytest | `apps/api/tests/unit` | `npm run test:api` |
| API integration | pytest + FastAPI TestClient | `apps/api/tests/api` | `npm run test:api` |
| Security | pytest | `apps/api/tests/api/test_security.py`, `test_backups.py` | `npm run test:api` |
| Offline | pytest with sockets blocked | `apps/api/tests/api/test_offline.py` | `npm run test:api` |
| Frontend unit/component | Vitest + Testing Library (jsdom) | `apps/web/tests` | `npm run test:web` |
| Type check / lint | tsc, eslint | | `npm run check` |
| End-to-end | Playwright (Chromium), real servers, fresh temp DB, Ollama pointed at a closed port | `tests/e2e` | `npm run test:e2e` |

## Coverage matrix (requirement → tests)

| Requirement | Tests |
|---|---|
| Requirement analysis rules | `unit/test_analyzer.py` |
| Recommendation transitions | `unit/test_recommendations.py`, `api/test_recommendations.py` |
| Prompt generation & variants & preservation | `unit/test_builder.py` |
| Versioning & immutability & restore | `api/test_prompts.py` |
| Evaluation rules | `unit/test_evaluator.py` |
| Validation / oversized | `api/test_security.py` |
| Project CRUD, conflict, duplicate, archive, delete | `api/test_projects.py` |
| Import / export | `api/test_import_export.py` |
| Backups validate/restore/traversal | `api/test_backups.py` |
| Codebase context: exclusions, traversal, symlink escape, redaction, system dirs, read-only | `api/test_codebase.py`, `tests/e2e/codebase.spec.ts` |
| Model fit heuristic | `web/tests/models.test.ts` |
| Missing Ollama / malformed model output / cancel / concurrency / thinking flag | `api/test_ai.py` (mocked Ollama transport) |
| OpenAI-compatible runtime | `unit/test_openai_compatible.py` (mocked server) |
| Custom templates | `api/test_templates.py`, `tests/e2e/phase5.spec.ts` |
| Agent handoff (no overwrite, symlink refusal, confirmation, quoting) | `api/test_handoff.py`, `tests/e2e/phase5.spec.ts` |
| AI finding post-filter | `unit/test_recommendations.py` |
| Database failure handling | `api/test_errors.py` |
| Offline workflow, no external sockets | `api/test_offline.py` |
| Safe Markdown | `web/tests/markdown.test.tsx` |
| Recommendation controls | `web/tests/recommendation-card.test.tsx` |
| Diff viewer | `web/tests/diff-view.test.tsx` |
| Form validation | `web/tests/project-form.test.tsx` |
| API client errors | `web/tests/api.test.ts` |
| Main workflow (create → analyse → approve/reject → generate → compare → save → edit → restore → evaluate → export, reload persistence, keyboard nav, XSS) | `tests/e2e/workflow.spec.ts` |

## Offline testing honesty

* `test_offline.py` monkeypatches `socket.socket.connect` so any non-loopback
  connection raises, with Ollama URL pointed at a closed port, fresh DB, no
  env keys. This proves the *application* makes no external connections in
  that workflow; it is **not** a physically disconnected machine.
* The E2E suite runs with Ollama unavailable and a fresh database.
* A real airplane-mode run has not been performed unless recorded below.

## Evidence (2026-10-15, macOS 26.6 arm64)

| Command | Result |
|---|---|
| `npm run lint:api` | ruff check + format check pass |
| `npm run typecheck` | pass (strict) |
| `npm run test:api` | 131 passed |
| `npm run test:web` | 24 passed |
| `npm run test:e2e` | 6 passed, 1 skipped (Chromium, production build, fresh temp DB, Ollama on closed port, external requests blocked) |
| `npm run test:e2e:real-model` | 1 passed — UI against real qwen3:8b: select, analyse, refine + diff, save, cancel |
| `scripts/validate_model.py` | all 12 operations succeeded with qwen3:8b; see MODEL_VALIDATION.md |
| Manual | `npm run dev` startup, proxy health, DNS-rebinding Host rejected (400), port-conflict message, Ctrl+C leaves no listeners |

Not verified: physically disconnected machine; real LM Studio / llama.cpp
servers (OpenAI-compatible runtime is mock-tested only); Windows. Linux is
covered by CI (GitHub Actions, ubuntu-latest).
