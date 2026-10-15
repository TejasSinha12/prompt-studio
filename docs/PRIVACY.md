# Prompt Studio — Privacy

## What is stored, and where

| Data | Location |
|---|---|
| Projects, requirements, findings, recommendations, prompts, versions, evaluations, settings | `data/prompt_studio.db` (SQLite) — or `$PROMPT_STUDIO_DATA_DIR/prompt_studio.db` |
| Backups | `data/backups/*.sqlite3` |
| Theme preference, panel layout | Browser `localStorage` for `127.0.0.1:3000` |

`data/` is in `.gitignore`. Nothing is stored anywhere else.

## What leaves the machine

**Nothing, by default.**

* No telemetry, analytics, crash reporting or update checks. Next.js
  telemetry is disabled by the provided scripts (`NEXT_TELEMETRY_DISABLED=1`).
* The rule-based engine performs no network I/O (verified by a test that
  blocks every non-loopback socket while running the full workflow).
* Local AI requests go only to the configured Ollama endpoint, which must be a
  loopback address unless you explicitly enable a remote endpoint in Settings.
  If you do, the UI shows a warning that prompt content will be sent to that
  host.
* There is no cloud provider integration. The app never falls back to one.
* Fonts and icons are bundled at build time; the UI makes no requests to CDNs
  at runtime.

## What is sent to Ollama (when you click a local-AI action)

The project idea, configuration, requirements and/or prompt text relevant to
the action — and nothing else (no settings, no other projects). Ollama itself
is a separate program; consult its documentation for its own behaviour.

## Deleting data

* Delete a single project (with confirmation) — removes its requirements,
  findings, recommendations, prompts and versions (cascade).
* Settings → Data → **Delete all data** (type `DELETE ALL DATA` to confirm)
  removes all content tables. Backups are kept unless you delete them
  individually, so you can recover.
* To remove everything including backups, stop the app and delete the `data/`
  directory.

## Exports

Export bundles contain only project content. They never contain application
settings, API tokens or the Ollama endpoint.

## Limitations

* The database is not encrypted at rest. Use full-disk encryption.
* Other software running under your OS account can read the data directory.
