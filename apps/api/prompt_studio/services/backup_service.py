"""BackupService and PrivacyService (data deletion).

Backups are SQLite files created with the online backup API, so they are
consistent even while the app runs. Restore only accepts files that live in
the managed backups directory, match the app's naming scheme, are not
symlinks, and pass integrity + schema checks. A safety backup is always taken
before a restore or a full data deletion.
"""

from __future__ import annotations

import os
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete
from sqlalchemy.orm import Session

from .. import db as dbmod
from ..config import get_settings
from ..errors import AppError, bad_request, not_found
from ..models import (
    AnalysisRun,
    Evaluation,
    Finding,
    Project,
    ProjectEvent,
    Prompt,
    PromptVersion,
    Recommendation,
    RecommendationEvent,
    Requirement,
    Tag,
    project_tags,
    prompt_tags,
)
from ..schemas import BackupOut, BackupValidation

NAME_RE = re.compile(r"^prompt-studio-\d{8}-\d{6}-\d{6}(-[a-z][a-z-]{0,30})?\.sqlite3$")
REQUIRED_TABLES = {
    "projects",
    "requirements",
    "findings",
    "recommendations",
    "prompts",
    "prompt_versions",
    "evaluations",
    "app_settings",
    "alembic_version",
}
RESTORE_CONFIRM = "RESTORE"
DELETE_ALL_CONFIRM = "DELETE ALL DATA"


def _known_revisions() -> set[str]:
    versions = dbmod.MIGRATIONS_DIR / "versions"
    revs = set()
    for f in versions.glob("*.py"):
        m = re.search(r'^revision\s*=\s*["\']([^"\']+)["\']', f.read_text(), re.M)
        if m:
            revs.add(m.group(1))
    return revs


class BackupService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.dir = self.settings.backups_dir

    def _resolve(self, name: str) -> Path:
        if not NAME_RE.fullmatch(name):
            raise bad_request("Invalid backup name.", "invalid_backup_name")
        base = self.dir.resolve()
        path = self.dir / name
        if path.is_symlink():
            raise bad_request("Symlinked backups are not allowed.", "invalid_backup_name")
        resolved = path.resolve()
        if resolved.parent != base:
            raise bad_request("Backup path escapes the backups directory.", "invalid_backup_name")
        if not resolved.is_file():
            raise not_found("Backup")
        return resolved

    def list(self) -> list[BackupOut]:
        if not self.dir.exists():
            return []
        out = []
        for p in self.dir.iterdir():
            if NAME_RE.fullmatch(p.name) and p.is_file() and not p.is_symlink():
                st = p.stat()
                out.append(
                    BackupOut(name=p.name, size_bytes=st.st_size, created_at=datetime.fromtimestamp(st.st_mtime, UTC))
                )
        return sorted(out, key=lambda b: b.name, reverse=True)

    def create(self, label: str = "") -> BackupOut:
        self.dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
        name = f"prompt-studio-{stamp}{'-' + label if label else ''}.sqlite3"
        if not NAME_RE.fullmatch(name):
            raise bad_request("Invalid backup label.")
        target = self.dir / name
        tmp = target.with_suffix(".tmp")
        src = sqlite3.connect(self.settings.db_path)
        try:
            dst = sqlite3.connect(tmp)
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()
        os.replace(tmp, target)
        st = target.stat()
        return BackupOut(name=name, size_bytes=st.st_size, created_at=datetime.fromtimestamp(st.st_mtime, UTC))

    def validate(self, name: str) -> BackupValidation:
        return self._validate_path(name, self._resolve(name))

    def _validate_path(self, name: str, path: Path) -> BackupValidation:
        checks: list[dict[str, Any]] = []

        def check(label: str, ok: bool, detail: str = "") -> bool:
            checks.append({"name": label, "ok": ok, "detail": detail})
            return ok

        try:
            with path.open("rb") as fh:
                header = fh.read(16)
            if not check("SQLite file header", header == b"SQLite format 3\x00"):
                return BackupValidation(name=name, valid=False, checks=checks)
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            try:
                integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
                check("Integrity check", integrity == "ok", str(integrity)[:200])
                tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                missing = REQUIRED_TABLES - tables
                check("Required tables", not missing, ", ".join(sorted(missing)) or "all present")
                rev = None
                if "alembic_version" in tables:
                    row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
                    rev = row[0] if row else None
                check("Schema version known", rev in _known_revisions(), f"revision {rev}")
                if "projects" in tables:
                    n = conn.execute("SELECT count(*) FROM projects").fetchone()[0]
                    check("Readable content", True, f"{n} project(s)")
                fk = conn.execute("PRAGMA foreign_key_check").fetchall() if not missing else []
                check("Foreign keys consistent", not fk, f"{len(fk)} violation(s)")
            finally:
                conn.close()
        except sqlite3.DatabaseError as e:
            check("Open as SQLite database", False, type(e).__name__)
        return BackupValidation(name=name, valid=all(c["ok"] for c in checks), checks=checks)

    def restore(self, name: str, confirm: str) -> dict[str, Any]:
        if confirm != RESTORE_CONFIRM:
            raise bad_request(f"Type {RESTORE_CONFIRM} to confirm the restore.", "confirmation_required")
        path = self._resolve(name)
        result = self._validate_path(name, path)
        if not result.valid:
            raise AppError(
                422, "invalid_backup", "Backup failed validation; nothing was changed.", {"checks": result.checks}
            )
        safety = self.create("pre-restore")
        dbmod.dispose_engine()
        src = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            dst = sqlite3.connect(self.settings.db_path)
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()
        dbmod.init_db()  # re-open and migrate forward if the backup is older
        return {"restored": name, "safety_backup": safety.name}

    def delete(self, name: str) -> None:
        self._resolve(name).unlink()


class PrivacyService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def delete_all(self, confirm: str) -> dict[str, Any]:
        if confirm != DELETE_ALL_CONFIRM:
            raise bad_request(f"Type {DELETE_ALL_CONFIRM} to confirm.", "confirmation_required")
        safety = BackupService().create("pre-delete")
        counts = {}
        try:
            for model in (
                Evaluation,
                PromptVersion,
                RecommendationEvent,
                Recommendation,
                Finding,
                AnalysisRun,
                Requirement,
                ProjectEvent,
            ):
                counts[model.__tablename__] = self.db.execute(delete(model)).rowcount
            self.db.execute(delete(prompt_tags))
            self.db.execute(delete(project_tags))
            counts["prompts"] = self.db.execute(delete(Prompt)).rowcount
            counts["projects"] = self.db.execute(delete(Project)).rowcount
            counts["tags"] = self.db.execute(delete(Tag)).rowcount
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {
            "deleted": counts,
            "safety_backup": safety.name,
            "note": "Settings were kept. Backups were kept; delete them individually if no longer needed.",
        }
