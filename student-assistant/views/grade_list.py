"""`/student/{student_id}` — list of grades for a student.

Layout:
    AppBar: student display_name + back arrow to "/"
    Body:   one GradeCard per grade, showing material count
    FAB:    "Add Grade"
    Empty:  centred icon + prompt text
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

import flet as ft

from domain.models import Grade
from services.storage import Storage
from widgets import grade_card

logger = logging.getLogger(__name__)


async def build(page: ft.Page, student_id: str) -> ft.View:
    storage: Storage = page.session.store.get("storage")
    student = await storage.get_student(student_id)

    student_name = student.display_name if student else "Unknown Student"

    # ── Card list ──────────────────────────────────────────────────────────────
    cards_column = ft.Column(
        controls=[],
        spacing=8,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    empty_state = ft.Column(
        controls=[
            ft.Icon(ft.Icons.SCHOOL, size=64, color=ft.Colors.GREY_400),
            ft.Text(
                "No grades yet.",
                size=16,
                color=ft.Colors.GREY_600,
                weight=ft.FontWeight.W_500,
            ),
            ft.Text(
                'Tap "Add Grade" to create one (e.g. "Grade 6").',
                size=13,
                color=ft.Colors.GREY_500,
            ),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=8,
        expand=True,
    )

    def go_to_grade(grade: Grade) -> None:
        page.route = f"/student/{student_id}/grade/{grade.id}"
        page.update()

    async def refresh() -> None:
        try:
            grades = await storage.list_grades(student_id)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to list grades for student %s", student_id)
            return
        cards_column.controls.clear()
        if not grades:
            cards_column.controls.append(empty_state)
        else:
            for g in grades:
                try:
                    materials = await storage.list_materials(g.id)
                    count = len(materials)
                except Exception:  # noqa: BLE001
                    count = 0
                cards_column.controls.append(grade_card.build(g, count, go_to_grade))
        page.update()

    # ── Add Grade dialog ───────────────────────────────────────────────────────
    def open_add_dialog(_e: ft.ControlEvent) -> None:
        name_field = ft.TextField(
            label='Grade name (e.g. "Grade 6")',
            autofocus=True,
            width=360,
            on_submit=lambda e: asyncio.create_task(_do_add(e)),
        )
        error_text = ft.Text("", color=ft.Colors.RED_700, size=12, visible=False)

        async def _do_add(_e: ft.ControlEvent) -> None:
            name = (name_field.value or "").strip()
            if not name:
                error_text.value = "Grade name cannot be empty."
                error_text.visible = True
                page.update()
                return
            grade = Grade(
                id=uuid.uuid4().hex,
                student_id=student_id,
                name=name,
                created_at=datetime.now(timezone.utc),
            )
            try:
                await storage.insert_grade(grade)
            except Exception as exc:  # noqa: BLE001
                error_text.value = f"Failed to save: {exc}"
                error_text.visible = True
                page.update()
                return
            page.pop_dialog()
            await refresh()

        def _cancel(_e: ft.ControlEvent) -> None:
            page.pop_dialog()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Add Grade"),
            content=ft.Container(
                content=ft.Column(
                    controls=[name_field, error_text],
                    tight=True,
                    spacing=6,
                ),
                width=400,
            ),
            actions=[
                ft.TextButton(content="Cancel", on_click=_cancel),
                ft.FilledButton(
                    content="Add",
                    on_click=lambda e: asyncio.create_task(_do_add(e)),
                ),
            ],
        )
        page.show_dialog(dialog)

    # ── Navigation ─────────────────────────────────────────────────────────────
    def go_back(_e: ft.ControlEvent) -> None:
        page.route = "/"
        page.update()

    appbar = ft.AppBar(
        title=ft.Text(student_name),
        center_title=False,
        leading=ft.IconButton(icon=ft.Icons.ARROW_BACK, on_click=go_back),
    )

    fab = ft.FloatingActionButton(
        icon=ft.Icons.ADD,
        tooltip="Add Grade",
        on_click=open_add_dialog,
    )

    body = ft.Container(
        content=cards_column,
        padding=20,
        expand=True,
    )

    view = ft.View(
        route=f"/student/{student_id}",
        appbar=appbar,
        controls=[body],
        floating_action_button=fab,
        floating_action_button_location=ft.FloatingActionButtonLocation.END_FLOAT,
    )

    await refresh()
    return view
