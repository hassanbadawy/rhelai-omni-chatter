"""`/student/{student_id}/grade/{grade_id}/material/{material_id}` — files for a material.

Layout:
    AppBar: "{student} > {grade} > {material}" breadcrumb + back arrow
    Body:   one FileCard per MaterialFile, status badges, action buttons
    FAB:    "Upload File"
    Empty:  centred icon + prompt

Polls every 2 s while any file is in CONVERTING / CLASSIFYING / EXTRACTING.
Poll task is cancelled when the route changes (stored in session under a unique key).
"""

from __future__ import annotations

import asyncio
import logging
import mimetypes
from pathlib import Path

import flet as ft

from domain.enums import FileStatus, UploadType
from domain.models import MaterialFile
from services.ingest import Ingest
from services.storage import Storage
from widgets import file_card

logger = logging.getLogger(__name__)

_POLL_KEY = "file_list_poll_task"
_IN_PROGRESS = {FileStatus.UPLOADING, FileStatus.CONVERTING, FileStatus.CLASSIFYING, FileStatus.EXTRACTING}
_POLL_INTERVAL = 2.0
_ALLOWED_EXTS = ["pdf"]


async def build(
    page: ft.Page,
    student_id: str,
    grade_id: str,
    material_id: str,
) -> ft.View:
    storage: Storage = page.session.store.get("storage")
    ingest: Ingest = page.session.store.get("ingest")

    student = await storage.get_student(student_id)
    grade = await storage.get_grade(grade_id)
    material = await storage.get_material(material_id)

    student_name = student.display_name if student else "?"
    grade_name = grade.name if grade else "?"
    material_title = material.title if material else "?"
    breadcrumb = f"{student_name} > {grade_name} > {material_title}"

    base_route = f"/student/{student_id}/grade/{grade_id}/material/{material_id}"

    # ── Card list ──────────────────────────────────────────────────────────────
    cards_column = ft.Column(
        controls=[],
        spacing=8,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    empty_state = ft.Column(
        controls=[
            ft.Icon(ft.Icons.UPLOAD_FILE, size=64, color=ft.Colors.GREY_400),
            ft.Text(
                "No files yet.",
                size=16,
                color=ft.Colors.GREY_600,
                weight=ft.FontWeight.W_500,
            ),
            ft.Text(
                'Tap "Upload File" to add an exercise sheet.',
                size=13,
                color=ft.Colors.GREY_500,
            ),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=8,
        expand=True,
    )

    def _on_view_questions(mf: MaterialFile) -> None:
        page.route = f"{base_route}/questions/{mf.id}"
        page.update()

    def _on_start_test(mf: MaterialFile) -> None:
        page.route = f"{base_route}/test/{mf.id}"
        page.update()

    async def refresh() -> None:
        try:
            files = await storage.list_files(material_id)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to list files for material %s", material_id)
            return
        cards_column.controls.clear()
        if not files:
            cards_column.controls.append(empty_state)
        else:
            for mf in files:
                cards_column.controls.append(
                    file_card.build(
                        mf,
                        on_view_questions=lambda f=mf: _on_view_questions(f),
                        on_start_test=lambda f=mf: _on_start_test(f),
                    )
                )
        page.update()
        # Restart poll if any file is still in progress.
        _maybe_restart_poll(files)

    # ── Poll ───────────────────────────────────────────────────────────────────
    def _maybe_restart_poll(files: list[MaterialFile]) -> None:
        has_in_progress = any(f.status in _IN_PROGRESS for f in files)
        prev = page.session.store.get(_POLL_KEY)
        if isinstance(prev, asyncio.Task) and not prev.done():
            if not has_in_progress:
                prev.cancel()
            return  # Already running — let it loop.
        if has_in_progress:
            page.session.store.set(
                _POLL_KEY,
                asyncio.create_task(_poll_loop(), name="file-list-poll"),
            )

    async def _poll_loop() -> None:
        try:
            while True:
                await asyncio.sleep(_POLL_INTERVAL)
                try:
                    files = await storage.list_files(material_id)
                except Exception:  # noqa: BLE001
                    return
                cards_column.controls.clear()
                if not files:
                    cards_column.controls.append(empty_state)
                else:
                    for mf in files:
                        cards_column.controls.append(
                            file_card.build(
                                mf,
                                on_view_questions=lambda f=mf: _on_view_questions(f),
                                on_start_test=lambda f=mf: _on_start_test(f),
                            )
                        )
                page.update()
                if not any(f.status in _IN_PROGRESS for f in files):
                    return
        except asyncio.CancelledError:
            return

    # Cancel previous poll task when navigating into this view.
    prev = page.session.store.get(_POLL_KEY)
    if isinstance(prev, asyncio.Task) and not prev.done():
        prev.cancel()

    # ── Upload dialog ──────────────────────────────────────────────────────────
    def open_upload_dialog(_e: ft.ControlEvent) -> None:
        selected_file: dict[str, ft.FilePickerFile | None] = {"file": None}

        status_text = ft.Text("", size=12, color=ft.Colors.GREY_600)
        pick_button = ft.OutlinedButton(content="Choose PDF…", icon=ft.Icons.ATTACH_FILE)
        submit_button = ft.FilledButton(
            content="Upload", icon=ft.Icons.CLOUD_UPLOAD, disabled=True
        )
        cancel_button = ft.TextButton(content="Cancel")
        upload_type_dropdown = ft.Dropdown(
            label="Upload type",
            width=360,
            value=UploadType.EXERCISE_SHEET.value,
            options=[
                ft.dropdown.Option(UploadType.EXERCISE_SHEET.value, "Exercise Sheet"),
                ft.dropdown.Option(UploadType.MATERIAL.value, "Material / Notes"),
                ft.dropdown.Option(UploadType.ANSWER_SHEET.value, "Answer Sheet"),
            ],
        )

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Upload File"),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row(controls=[pick_button, status_text], spacing=12),
                        upload_type_dropdown,
                        ft.Text(
                            "PDF only. Processing starts automatically after upload.",
                            size=11,
                            color=ft.Colors.GREY_500,
                        ),
                    ],
                    tight=True,
                    spacing=10,
                ),
                width=440,
            ),
            actions=[cancel_button, submit_button],
        )

        # Reuse a cached FilePicker service to avoid re-registering on every open.
        file_picker = page.session.store.get("file_picker")
        if file_picker is None:
            file_picker = ft.FilePicker()
            page.services.append(file_picker)
            page.session.store.set("file_picker", file_picker)

        async def on_pick_click(_e: ft.ControlEvent) -> None:
            files = await file_picker.pick_files(
                dialog_title="Pick a PDF",
                allowed_extensions=_ALLOWED_EXTS,
                allow_multiple=False,
                with_data=True,
            )
            if not files:
                return
            picked = files[0]
            selected_file["file"] = picked
            status_text.value = picked.name
            submit_button.disabled = False
            page.update()

        pick_button.on_click = on_pick_click

        async def on_submit(_e: ft.ControlEvent) -> None:
            f = selected_file["file"]
            if not f:
                return
            submit_button.disabled = True
            status_text.value = "Uploading…"
            page.update()

            if f.bytes:
                file_bytes = f.bytes
            elif f.path:
                file_bytes = await asyncio.to_thread(Path(f.path).read_bytes)
            else:
                status_text.value = "Could not read file bytes."
                submit_button.disabled = False
                page.update()
                return

            mime, _ = mimetypes.guess_type(f.name)
            upload_type = UploadType(upload_type_dropdown.value or UploadType.EXERCISE_SHEET.value)
            try:
                await ingest.submit_upload(
                    material_id=material_id,
                    student_id=student_id,
                    original_filename=f.name,
                    mime_type=mime or "application/pdf",
                    file_bytes=file_bytes,
                    upload_type=upload_type,
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Upload failed")
                status_text.value = f"Failed: {exc}"
                submit_button.disabled = False
                page.update()
                return

            page.pop_dialog()
            await refresh()

        def on_cancel(_e: ft.ControlEvent) -> None:
            page.pop_dialog()

        submit_button.on_click = on_submit
        cancel_button.on_click = on_cancel

        page.show_dialog(dialog)

    # ── Navigation ─────────────────────────────────────────────────────────────
    def go_back(_e: ft.ControlEvent) -> None:
        page.route = f"/student/{student_id}/grade/{grade_id}"
        page.update()

    appbar = ft.AppBar(
        title=ft.Text(breadcrumb),
        center_title=False,
        leading=ft.IconButton(icon=ft.Icons.ARROW_BACK, on_click=go_back),
    )

    fab = ft.FloatingActionButton(
        icon=ft.Icons.UPLOAD_FILE,
        tooltip="Upload File",
        on_click=open_upload_dialog,
    )

    body = ft.Container(
        content=cards_column,
        padding=20,
        expand=True,
    )

    view = ft.View(
        route=base_route,
        appbar=appbar,
        controls=[body],
        floating_action_button=fab,
        floating_action_button_location=ft.FloatingActionButtonLocation.END_FLOAT,
    )

    await refresh()
    return view
