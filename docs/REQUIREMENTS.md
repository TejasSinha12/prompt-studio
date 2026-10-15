# Prompt Studio — Requirements

IDs are referenced from tests (`tests/` docstrings) and the test plan.

## Non-negotiable (NN)

| ID | Requirement | Acceptance criterion |
|---|---|---|
| NN-1 | Runs locally on localhost | `npm run dev` serves UI at 127.0.0.1:3000, API at 127.0.0.1:8000 |
| NN-2 | No cloud AI / API key / subscription | No code path calls a non-loopback host by default; `.env.example` has no keys |
| NN-3 | Ollama primary local LLM | Models listed, selected, used for AI analysis/optimization |
| NN-4 | Rule-based analysis always available | Analysis works with Ollama unreachable (test `test_offline_workflow`) |
| NN-5 | Offline after install | Offline test blocks all non-loopback sockets |
| NN-6 | Local persistence | SQLite under data dir; survives restart (E2E reload test) |
| NN-7 | No telemetry | No analytics deps; Next telemetry disabled in scripts |
| NN-8 | No silent cloud fallback | No cloud provider exists in registry |
| NN-9 | No shell execution / repo modification | No `subprocess`/`os.system` in app code (security test greps) |
| NN-10 | Honest labelling | Every finding/version/evaluation stores and displays `engine` |

## Functional (F)

| ID | Area | Requirement |
|---|---|---|
| F-PRJ-1 | Projects | Create, rename, edit description, duplicate, archive, restore, delete (confirm) |
| F-PRJ-2 | Projects | Search (name/description/idea), filter by tag and archive status |
| F-PRJ-3 | Projects | Tags; export project bundle (JSON); import bundle with validation |
| F-PRJ-4 | Projects | History of project events; optimistic concurrency with visible save state |
| F-REQ-1 | Requirements | CRUD typed requirements (goal, functional, non-functional, security, constraint, acceptance, assumption, out-of-scope) with status |
| F-CFG-1 | Prompt config | Target agent, category, language, framework, codebase info, size, detail, tone, output format, testing, security, performance, hardware, budget, architecture, restrictions — all optional |
| F-ANA-1 | Analyzer | Deterministic rules for the 16 listed categories where deterministic detection is feasible; each finding has the 12 required fields |
| F-ANA-2 | Analyzer | Findings keep stable IDs across runs; user status preserved |
| F-ANA-3 | Analyzer | Local-AI analysis optional, validated, labelled |
| F-REC-1 | Recommendations | Generated for significant findings with the 9 required fields |
| F-REC-2 | Recommendations | Approve / reject / edit / defer / restore; compare alternatives |
| F-REC-3 | Recommendations | Only approval modifies spec; rejected never re-proposed silently; history kept |
| F-GEN-1 | Generation | Build structured prompt from partial input; omit empty sections; label assumptions |
| F-GEN-2 | Variants | Concise / balanced / detailed side-by-side; preservation report |
| F-GEN-3 | Optimization | Optional local-AI refinement with preservation check and visible diff |
| F-GEN-4 | Editing | Manual edit mode; regeneration never loses versions |
| F-PRF-1 | Profiles | Versioned profiles: Claude Code, Codex, Cursor, generic coding, generic LLM |
| F-EXP-1 | Export | Markdown, plain text, CLAUDE.md, AGENTS.md, Cursor `.mdc`, implementation plan, task breakdown, testing instructions, project spec, reusable template, JSON bundle, ZIP of agent files |
| F-LIB-1 | Library | Search, tags, category filter, favorites, duplicate, archive |
| F-VER-1 | Versions | Immutable versions; restore creates new version; line diff; change summary |
| F-EVL-1 | Evaluation | 11 dimensions; evidence per finding; documented heuristic score; compare versions |
| F-MOD-1 | Models | Ollama status, list, select, metadata, install guidance, no auto-download |
| F-SET-1 | Settings | Endpoint, timeouts, retries, model, theme; separate from content |
| F-BAK-1 | Backups | Create, list, validate, restore (confirm + safety backup), delete |
| F-DEL-1 | Data | Delete all data with typed confirmation |
| F-TPL-1 | Templates | Built-in task templates that create a pre-filled project |
| F-CTX-1 | Codebase context | Read-only scan of an explicitly chosen directory with exclusions, preview, redaction and summary |

## Non-functional (NF)

| ID | Requirement | Acceptance criterion |
|---|---|---|
| NF-SEC-1 | Loopback binding | Default host 127.0.0.1 in config and scripts |
| NF-SEC-2 | Request limits | >2 MiB body → 413 (test) |
| NF-SEC-3 | Input validation | Overlong fields → 422 (test) |
| NF-SEC-4 | CSRF/DNS rebinding | Missing header → 403; bad Host → 400 (tests) |
| NF-SEC-5 | Safe Markdown | `<script>`, `javascript:` not rendered (frontend test) |
| NF-SEC-6 | No secrets in logs/exports | Export bundle contains no settings/keys (test) |
| NF-A11Y-1 | Keyboard accessible | All controls reachable by Tab; visible focus ring; dialogs trap focus via native `<dialog>` |
| NF-A11Y-2 | Contrast | Theme tokens meet WCAG AA for body text |
| NF-PERF-1 | Pagination | List endpoints paginate (limit ≤ 200) |
| NF-PERF-2 | Non-blocking AI | AI calls run as cancellable async jobs; concurrency ≤ configured limit |
| NF-MAINT-1 | Strict typing | `tsc --noEmit` strict passes; Pydantic models for all I/O |

## Out of scope for the MVP

* Multi-user accounts, remote access, sync.
* Executing coding agents or sending prompts anywhere.
* Cloud providers of any kind.
* Custom templates, additional local runtimes, coding-agent handoff (Phase 5 remainder).
