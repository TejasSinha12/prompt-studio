"""Validate local-AI features against a real Ollama model.

Usage (from apps/api):
    uv run python scripts/validate_model.py --model qwen3:8b [--thinking] [--runs 2]

Uses a throwaway database in a temp directory; your data is never touched.
Prints a Markdown report of what actually happened (timings, schema validity,
repairs, evidence verification, requirement preservation). Nothing is sent
anywhere except the configured local Ollama endpoint.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import platform
import sys
import tempfile
import time

TMP = tempfile.mkdtemp(prefix="ps-validate-")
os.environ["PROMPT_STUDIO_DATA_DIR"] = TMP

from prompt_studio import schemas  # noqa: E402
from prompt_studio.db import init_db, session_scope  # noqa: E402
from prompt_studio.engine.optimizer.builder import build_prompt  # noqa: E402
from prompt_studio.providers.base import ProviderError  # noqa: E402
from prompt_studio.services.ai_service import LocalModelService, default_provider_factory  # noqa: E402
from prompt_studio.services.analysis_service import AnalysisService  # noqa: E402
from prompt_studio.services.project_service import ProjectService  # noqa: E402
from prompt_studio.services.prompt_service import PromptService  # noqa: E402

IDEA = (
    "Build a REST API for a team task tracker. Users sign in, create tasks, assign them to teammates and "
    "comment on them. It should be fast and scale well. Use the latest versions of everything."
)
REQS = [
    ("functional", "Users can create, edit and delete tasks", "confirmed"),
    ("functional", "Tasks can be assigned to one teammate", "confirmed"),
    ("security", "Passwords are hashed with a modern password-hashing algorithm", "confirmed"),
    ("acceptance", "Every endpoint is covered by an integration test", "confirmed"),
    ("functional", "Send email notifications for every comment", "rejected"),
]


def setup() -> tuple[str, str]:
    init_db()
    with session_scope() as db:
        ps = ProjectService(db)
        p = ps.create(
            schemas.ProjectCreate(
                name="Validation project",
                original_idea=IDEA,
                tech_stack="Python, FastAPI",
                config=schemas.ConfigIn(task_category="new_application"),
            )
        )
        for kind, text, status in REQS:
            ps.add_requirement(p.id, schemas.RequirementCreate(kind=kind, text=text, status=status))
        AnalysisService(db).run_rule_based(p.id)
        spec = ps.to_spec(ps.get(p.id))
        pr = PromptService(db).create(
            schemas.PromptCreate(project_id=p.id, title="v", content=build_prompt(spec, "balanced").content)
        )
        return p.id, pr.current_version_id or ""


async def timed(label: str, coro):
    t0 = time.perf_counter()
    try:
        res = await coro
        return label, time.perf_counter() - t0, res, None
    except ProviderError as e:
        return label, time.perf_counter() - t0, None, f"{e.code}: {e.message}"


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--thinking", action="store_true")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--endpoint", default="http://127.0.0.1:11434")
    ap.add_argument("--timeout", type=int, default=600)
    args = ap.parse_args()

    settings = schemas.AppSettings(
        ollama_url=args.endpoint,
        model=args.model,
        thinking=args.thinking,
        timeout_seconds=args.timeout,
        temperature=0.2,
        num_ctx=8192,
    )
    svc = LocalModelService(default_provider_factory)
    provider = default_provider_factory(settings)
    status = await provider.status()
    if not status.available:
        print(f"Ollama not reachable at {args.endpoint}: {status.error}")
        return 2
    details = await provider.show(args.model)
    project_id, version_id = setup()

    rows = []
    for run in range(1, args.runs + 1):
        for label, coro in [
            ("analysis", svc.analyze(project_id, settings)),
            ("clarify", svc.clarify(project_id, settings)),
            ("optimize", svc.optimize(project_id, "balanced", None, None, settings)),
            ("evaluate", svc.evaluate(version_id, settings)),
        ]:
            name, secs, res, err = await timed(label, coro)
            note = ""
            if res is not None:
                if name == "analysis":
                    with session_scope() as db:
                        ai = [
                            f
                            for f in AnalysisService(db).list_findings(project_id)
                            if f.engine == "local_ai" and f.run_id == res["run_id"]
                        ]
                    verified = sum(1 for f in ai if "not found verbatim" not in f.explanation)
                    note = (
                        f"{res['findings']} findings ({verified}/{len(ai)} with verified evidence), "
                        f"{res['new_recommendations']} suggestions, repaired={res['repaired']}, "
                        f"filtered out: {', '.join(f'{k}={v}' for k, v in res['dropped'].items() if v) or 'none'}"
                    )
                elif name == "clarify":
                    note = f"{len(res['questions'])} questions, repaired={res['repaired']}"
                elif name == "optimize":
                    kept = sum(1 for p in res["preservation"] if p["preserved"])
                    note = (
                        f"{kept}/{len(res['preservation'])} requirements preserved verbatim, "
                        f"rejected reintroduced={len(res['rejected_reintroduced'])}, {len(res['content'])} chars"
                    )
                elif name == "evaluate":
                    note = f"feasibility score {res['score']}"
            rows.append((run, name, f"{secs:.1f}s", "ok" if err is None else "FAILED", err or note))

    print(f"## Real-model validation: `{args.model}`\n")
    print(f"- Ollama {status.version}, endpoint {args.endpoint}, {platform.platform()}, {platform.machine()}")
    print(
        f"- Model: {details.parameter_size or '?'} params, {details.quantization or '?'}, context {details.context_length}, "
        f"capabilities: {', '.join(details.capabilities) or 'n/a'}"
    )
    print(f"- Settings: thinking={'on' if args.thinking else 'off'}, temperature 0.2, num_ctx 8192, runs={args.runs}\n")
    print("| Run | Operation | Time | Result | Details |\n|---|---|---|---|---|")
    for r in rows:
        print("| " + " | ".join(str(x) for x in r) + " |")
    return 0 if all(r[3] == "ok" for r in rows) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
