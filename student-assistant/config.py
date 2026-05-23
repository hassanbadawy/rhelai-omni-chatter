"""Loads `.env` and exposes typed config to the rest of the app.

Only startup-time constants live here (paths, log level).
LLM and Docling URLs are runtime-editable and live in the app_settings
SQLite table — see services/settings_service.py.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

_DEFAULT_SQLITE_PATH = "~/.student-assistant/db.sqlite3"
_DEFAULT_STORAGE_ROOT = "~/.student-assistant/storage"
_DEFAULT_LOG_LEVEL = "INFO"

# Seed values for app_settings on first run (overridable in the Settings UI).
_DEFAULT_DOCLING_URL = "http://localhost:5001"
_DEFAULT_LLM_BASE_URL = "http://localhost:11434/v1"
_DEFAULT_LLM_MODEL = "ollama/qwen2.5:7b-instruct"


@dataclass(frozen=True, slots=True)
class Config:
    sqlite_path: Path
    storage_root: Path
    log_level: str
    # Initial seeds — written to app_settings once on first run, then ignored.
    initial_docling_url: str = _DEFAULT_DOCLING_URL
    initial_llm_base_url: str = _DEFAULT_LLM_BASE_URL
    initial_llm_model: str = _DEFAULT_LLM_MODEL
    initial_llm_api_key: str = ""


def _find_dotenv_path() -> Path | None:
    cwd = Path.cwd()
    candidates: list[Path] = [cwd / ".env"]
    for parent in cwd.parents:
        candidates.append(parent / ".env")
    candidates.append(Path(__file__).resolve().parent / ".env")
    for c in candidates:
        if c.is_file():
            return c
    return None


def load() -> Config:
    """Read `.env`, expand `~`, return a `Config`."""
    dotenv_path = _find_dotenv_path()
    if dotenv_path is not None:
        load_dotenv(dotenv_path=dotenv_path, override=False)
        logger.debug("Loaded .env from %s", dotenv_path)
    else:
        load_dotenv(override=False)
        logger.debug("No .env file found; relying on process environment")

    sqlite_path = Path(os.environ.get("SQLITE_PATH", _DEFAULT_SQLITE_PATH)).expanduser()
    storage_root = Path(os.environ.get("STORAGE_ROOT", _DEFAULT_STORAGE_ROOT)).expanduser()

    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    storage_root.mkdir(parents=True, exist_ok=True)

    return Config(
        sqlite_path=sqlite_path,
        storage_root=storage_root,
        log_level=os.environ.get("LOG_LEVEL", _DEFAULT_LOG_LEVEL).upper(),
        initial_docling_url=os.environ.get("DOCLING_URL", _DEFAULT_DOCLING_URL).rstrip("/"),
        initial_llm_base_url=os.environ.get("LLM_BASE_URL", _DEFAULT_LLM_BASE_URL).rstrip("/"),
        initial_llm_model=os.environ.get("LLM_MODEL", _DEFAULT_LLM_MODEL),
        initial_llm_api_key=os.environ.get("LLM_API_KEY", ""),
    )
