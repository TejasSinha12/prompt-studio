# Prompt Studio — Threat Model

Method: STRIDE-style review of a single-user local web application.
Last reviewed 2026-10-15.

## Assets

1. Project content: ideas, specifications, prompts (may contain proprietary plans).
2. The local SQLite database and backups.
3. The user's filesystem (the app must not read or write outside its data dir).
4. The user's machine (no code execution).

## Trust boundaries

```
[Other websites in the user's browser] ─X─► [Next.js 127.0.0.1:3000] ──► [API 127.0.0.1:8000] ──► [SQLite]
[Other local processes / users]        ─?─►                               └──► [Ollama, loopback]
[Imported files / backups]  ── untrusted data ──► API validation
[Model output]              ── untrusted data ──► schema validation
```

**Localhost is not a security boundary on its own.** Any process running as
any user on the machine can connect to loopback ports, and web pages in the
user's browser can attempt requests to localhost.

## Threats and mitigations

| # | Threat | STRIDE | Mitigation | Verified by |
|---|---|---|---|---|
| T1 | Malicious website sends cross-site POST/DELETE to API (CSRF) | T, E | Mutations require custom header `X-Prompt-Studio: 1` (cannot be sent cross-origin without CORS preflight, which the API never approves); `Origin` checked against allowlist when present; no CORS headers emitted | `test_security.py::test_mutation_requires_header`, `::test_foreign_origin_rejected` |
| T2 | DNS rebinding: attacker domain resolves to 127.0.0.1 and reads API | I | `Host` header must be `127.0.0.1`, `localhost` or `[::1]` (+ configured port) | `test_security.py::test_untrusted_host_rejected` |
| T3 | Other local users/processes reach API on loopback | I, T | Documented limitation. Optional `PROMPT_STUDIO_API_TOKEN` env var: when set, API requires `Authorization: Bearer` (Next.js proxy injects it server-side, never exposed to browser) | `test_security.py::test_api_token_enforced` |
| T4 | Stored XSS via prompt/Markdown content | T, E | React escapes text; Markdown via `react-markdown` without raw HTML + `rehype-sanitize`; unsafe URL schemes stripped; CSP headers in production | `markdown.test.tsx` |
| T5 | Path traversal in backup restore/delete | T, I | Filenames matched by strict regex; resolved path must be inside backups dir; symlinks rejected | `test_backups.py::test_traversal_rejected` |
| T6 | Malicious import (huge, deeply nested, wrong types) | D, T | 10 MiB body cap; Pydantic schema with list/length limits; all IDs re-generated on import; transaction rollback on failure | `test_import_export.py` |
| T7 | Malicious backup file restored | T | Only files created by the app in the backups dir can be restored; `PRAGMA integrity_check`, required-tables and alembic-revision check before restore; safety backup taken first | `test_backups.py` |
| T8 | Prompt injection via project content into local model | T | Content placed in delimited user message; system prompt declares it untrusted data; model output is schema-validated, never executed, and stored as labelled suggestions requiring user approval | `test_ai.py` (malformed + injected output stays a suggestion) |
| T9 | SSRF via configurable Ollama endpoint | I | Endpoint must be http(s) with loopback host unless `allow_remote_ollama` explicitly enabled with a UI warning; no redirects followed | `test_models.py::test_non_loopback_endpoint_rejected` |
| T10 | Secrets leaking into logs | I | Access log only logs method/path/status; no request bodies logged; exception handler returns generic messages | `test_security.py::test_error_does_not_leak` |
| T11 | Resource exhaustion (huge input, AI flood) | D | Body limit, field limits, pagination caps, AI semaphore + duplicate-job rejection, request timeouts | `test_security.py::test_oversized_body`, `test_ai.py::test_concurrency_limit` |
| T12 | Accidental destructive actions | T | Delete project / delete all data / restore require explicit confirmation (UI dialog + API confirm field) | `test_projects.py`, `test_backups.py` |
| T13 | Silent data loss through concurrent edits (two tabs) | T | Optimistic concurrency `revision`; 409 on stale write; UI shows conflict and offers reload | `test_projects.py::test_stale_revision_conflict` |
| T14 | Unexpected outbound network from offline engine | I | Engine has no network code; test runs whole workflow with non-loopback sockets blocked | `test_offline.py` |
| T15 | Arbitrary code / shell execution | E | No `subprocess`, `os.system`, `eval`, `exec` in app code | `test_security.py::test_no_shell_execution_in_source` |
| T17 | Codebase scan reads secrets or escapes the chosen directory (symlinks, `..`) | I | Explicit absolute path; system dirs/home refused; no symlink following; secret/binary/size exclusions; per-file containment re-check; secret-line redaction; read-only | `test_codebase.py` |
| T16 | Supply chain (malicious dependency) | E | Minimal deps; lockfiles committed (`uv.lock`, `package-lock.json`); no postinstall scripts of our own | Manual review; residual risk |

## Residual risks / limitations

* Any process running as the same OS user can read the SQLite file directly.
  Data is **not encrypted at rest**; rely on OS disk encryption (FileVault).
* Without `PROMPT_STUDIO_API_TOKEN`, other local OS users can call the API.
* Local model output may be wrong or manipulated by injected content; it is
  always presented as a suggestion requiring approval.
* Browser extensions with page access can read the UI.
* Dependency vulnerabilities: run `npm audit` / `uv pip audit`-equivalents
  periodically; no automatic updates.
* Codebase-scan secret detection is pattern-based; unusual secret formats in
  selected files may not be redacted. Review the summary before inserting it.
