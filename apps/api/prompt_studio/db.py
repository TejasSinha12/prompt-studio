"""SQLite engine, sessions and migrations."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"

_lock = threading.Lock()
_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _on_connect(dbapi_conn, _record) -> None:
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.execute("PRAGMA busy_timeout=5000")
    cur.close()


def make_engine(db_path: Path) -> Engine:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    event.listen(engine, "connect", _on_connect)
    return engine


def run_migrations(db_path: Path) -> None:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")


def init_db() -> Engine:
    """Create the data dir, run migrations and (re)create the engine."""
    global _engine, _session_factory
    settings = get_settings()
    with _lock:
        if _engine is not None:
            _engine.dispose()
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        settings.backups_dir.mkdir(parents=True, exist_ok=True)
        run_migrations(settings.db_path)
        _engine = make_engine(settings.db_path)
        _session_factory = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
        return _engine


def dispose_engine() -> None:
    global _engine, _session_factory
    with _lock:
        if _engine is not None:
            _engine.dispose()
        _engine = None
        _session_factory = None


def get_engine() -> Engine:
    if _engine is None:
        init_db()
    assert _engine is not None
    return _engine


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request, committed by services."""
    if _session_factory is None:
        init_db()
    assert _session_factory is not None
    session = _session_factory()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    gen = get_session()
    session = next(gen)
    try:
        yield session
    finally:
        gen.close()
