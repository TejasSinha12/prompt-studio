"""Application configuration loaded from environment variables.

Only process-level configuration lives here. User-editable settings (model,
timeouts, theme, ...) are stored in the `app_settings` table, see
`services/settings_service.py`.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PROMPT_STUDIO_", env_file=None, extra="ignore")

    data_dir: Path = Field(default=REPO_ROOT / "data")
    host: str = "127.0.0.1"
    port: int = 8000
    # Origins allowed to send mutating requests (the Next.js frontend).
    allowed_origins: list[str] = Field(default_factory=lambda: ["http://127.0.0.1:3000", "http://localhost:3000"])
    # Optional shared secret. When set, every /api request except /api/health
    # must carry `Authorization: Bearer <token>`. The Next.js proxy injects it.
    api_token: str | None = None
    max_body_bytes: int = 2 * 1024 * 1024
    max_import_bytes: int = 10 * 1024 * 1024
    # Default Ollama endpoint; can be overridden in the settings UI.
    ollama_url: str = "http://127.0.0.1:11434"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "prompt_studio.db"

    @property
    def backups_dir(self) -> Path:
        return self.data_dir / "backups"


@lru_cache
def get_settings() -> Settings:
    return Settings()
