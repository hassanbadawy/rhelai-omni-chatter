"""Dependency container passed to every worker handler."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.ai_client import AIClient
    from services.docling import DoclingClient
    from services.jobs import Jobs
    from services.object_store import ObjectStore
    from services.settings_service import SettingsService
    from services.storage import Storage


@dataclass(slots=True)
class WorkerDeps:
    storage: "Storage"
    object_store: "ObjectStore"
    docling: "DoclingClient | None"  # workers build DoclingClient at runtime from settings
    ai: "AIClient | None"           # workers build AIClient at runtime from settings
    settings: "SettingsService"
    jobs: "Jobs"
