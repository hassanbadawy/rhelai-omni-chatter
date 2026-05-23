"""Flet entry point.

Routes:
  /                                                    → student_list (home)
  /student/{id}                                        → grade_list
  /student/{id}/grade/{gid}                            → material_list
  /student/{id}/grade/{gid}/material/{mid}             → file_list
  /student/{id}/grade/{gid}/material/{mid}/questions/{fid} → question_bank_view
  /student/{id}/grade/{gid}/material/{mid}/test/{fid}  → test_runner_view
  /settings                                            → settings_view

Background: JobWorker asyncio task — claims jobs from job_queue, runs pipeline.
"""

from __future__ import annotations

import logging
from pathlib import Path

import flet as ft

from config import load as load_config
from services.ingest import Ingest
from services.jobs import JobWorker, Jobs
from services.object_store import ObjectStore
from services.settings_service import SettingsService
from services.storage import Storage
from views import (
    file_list,
    grade_list,
    material_list,
    question_bank_view,
    settings_view,
    student_list,
    test_runner_view,
)
from workers._deps import WorkerDeps
from workers.registry import REGISTRY

logger = logging.getLogger(__name__)

APP_TITLE = "Student Assistant"


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )


async def main(page: ft.Page) -> None:
    cfg = load_config()
    _setup_logging(cfg.log_level)
    logger.info("Starting %s", APP_TITLE)

    page.title = APP_TITLE
    page.theme_mode = ft.ThemeMode.SYSTEM
    page.padding = 0
    page.window.min_width = 800
    page.window.min_height = 600

    # Run migrations (idempotent).
    storage = Storage(cfg.sqlite_path)
    await storage.connect()
    await storage.migrate(Path(__file__).parent / "migrations")

    # Seed app_settings from config initial values (only writes missing keys).
    await storage.seed_settings_if_empty({
        "docling_url": cfg.initial_docling_url,
        "llm_base_url": cfg.initial_llm_base_url,
        "llm_model": cfg.initial_llm_model,
        "llm_api_key": cfg.initial_llm_api_key,
    })

    object_store = ObjectStore(cfg.storage_root)
    settings_svc = SettingsService(storage)
    jobs = Jobs(storage)
    ingest = Ingest(storage, object_store, jobs)

    deps = WorkerDeps(
        storage=storage,
        object_store=object_store,
        docling=None,   # workers build DoclingClient at runtime using settings URL
        ai=None,        # workers build AIClient at runtime using settings config
        settings=settings_svc,
        jobs=jobs,
    )

    page.session.store.set("storage", storage)
    page.session.store.set("object_store", object_store)
    page.session.store.set("jobs", jobs)
    page.session.store.set("ingest", ingest)
    page.session.store.set("settings", settings_svc)

    worker = JobWorker(jobs, REGISTRY, deps)
    page.session.store.set("worker", worker)
    worker.start()

    async def _on_disconnect(_evt: ft.ControlEvent) -> None:
        logger.info("Disconnecting — stopping worker and closing storage")
        worker.stop()
        try:
            await storage.close()
        except Exception:  # noqa: BLE001
            pass

    page.on_disconnect = _on_disconnect

    async def _on_route_change(_evt: ft.RouteChangeEvent) -> None:
        await _render_route(page)

    page.on_route_change = _on_route_change

    if not page.route or page.route == "/":
        page.route = "/"
    await _render_route(page)


async def _render_route(page: ft.Page) -> None:
    route = page.route or "/"
    page.views.clear()
    view = await _match_route(page, route)
    page.views.append(view)
    page.update()


async def _match_route(page: ft.Page, route: str) -> ft.View:  # noqa: PLR0911
    if route == "/settings":
        return await settings_view.build(page)

    segs = route.strip("/").split("/")

    def seg(i: int) -> str:
        return segs[i] if i < len(segs) else ""

    # /student/{id}/grade/{gid}/material/{mid}/test/{fid}
    if seg(0) == "student" and seg(2) == "grade" and seg(4) == "material" and seg(6) == "test":
        return await test_runner_view.build(page, segs[1], segs[3], segs[5], segs[7])

    # /student/{id}/grade/{gid}/material/{mid}/questions/{fid}
    if seg(0) == "student" and seg(2) == "grade" and seg(4) == "material" and seg(6) == "questions":
        return await question_bank_view.build(page, segs[1], segs[3], segs[5], segs[7])

    # /student/{id}/grade/{gid}/material/{mid}
    if seg(0) == "student" and seg(2) == "grade" and seg(4) == "material":
        return await file_list.build(page, segs[1], segs[3], segs[5])

    # /student/{id}/grade/{gid}
    if seg(0) == "student" and seg(2) == "grade":
        return await material_list.build(page, segs[1], segs[3])

    # /student/{id}
    if seg(0) == "student":
        return await grade_list.build(page, segs[1])

    # / — home
    return await student_list.build(page)


def _run() -> None:
    ft.run(main, view=ft.AppView.WEB_BROWSER, port=8080)


if __name__ == "__main__":
    _run()
