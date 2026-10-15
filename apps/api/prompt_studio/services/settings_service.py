"""Application settings (separate from project content)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..config import get_settings
from ..errors import bad_request
from ..models import AppSetting, utcnow
from ..providers.base import ProviderError, validate_endpoint
from ..schemas import AppSettings

KEY = "app_settings"


class SettingsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self) -> AppSettings:
        row = self.db.get(AppSetting, KEY)
        defaults = AppSettings(ollama_url=get_settings().ollama_url)
        if row is None or not isinstance(row.value, dict):
            return defaults
        merged = defaults.model_dump() | row.value
        try:
            return AppSettings(**merged)
        except ValueError:
            return defaults  # corrupted settings never block the app

    def update(self, data: AppSettings) -> AppSettings:
        try:
            data.ollama_url = validate_endpoint(data.ollama_url, data.allow_remote_ollama)
            data.openai_compatible_url = validate_endpoint(data.openai_compatible_url, data.allow_remote_ollama)
        except ProviderError as e:
            raise bad_request(e.message, "bad_endpoint") from None
        row = self.db.get(AppSetting, KEY)
        if row is None:
            row = AppSetting(key=KEY)
            self.db.add(row)
        row.value = data.model_dump()
        row.updated_at = utcnow()
        self.db.commit()
        return data
