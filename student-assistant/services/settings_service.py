"""App settings backed by the app_settings SQLite table.

Values are editable at runtime via the Settings UI and take effect immediately —
no restart needed. The table is seeded from Config initial_* values on first run.
"""

from __future__ import annotations

import logging

from services.storage import Storage

logger = logging.getLogger(__name__)

KEYS = ("docling_url", "llm_base_url", "llm_model", "llm_api_key")


class SettingsService:
    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    async def get_docling_url(self) -> str:
        return (await self._storage.get_setting("docling_url")) or "http://localhost:5001"

    async def get_llm_config(self) -> tuple[str, str, str]:
        """Returns (base_url, model, api_key)."""
        base_url = (await self._storage.get_setting("llm_base_url")) or "http://localhost:11434/v1"
        model = (await self._storage.get_setting("llm_model")) or "ollama/qwen2.5:7b-instruct"
        api_key = (await self._storage.get_setting("llm_api_key")) or ""
        return base_url, model, api_key

    async def save(self, key: str, value: str) -> None:
        if key not in KEYS:
            raise ValueError(f"Unknown setting key: {key!r}")
        await self._storage.set_setting(key, value)

    async def get_all(self) -> dict[str, str]:
        return await self._storage.get_all_settings()
