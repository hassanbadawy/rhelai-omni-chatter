"""`/student/{student_id}/grade/{grade_id}` — list of materials (subjects) for a grade.

Layout:
    AppBar: "{student_name} > {grade_name}" + back arrow to grade list
    Body:   one MaterialCard per material, showing file count
    FAB:    "Add Material"
    Empty:  centred icon + prompt text
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

import flet as ft

from domain.models import Material
from services.storage import Storage
from widgets import material_card

logger = logging.getLogger(__name__)


async def build(page: ft.Page, student_id: str, grade_id: str) -> ft.View:
    storage: Storage = page.session.store.get("storage")

    student = await storage.get_student(student_id)
    grade = await storage.get_grade(grade_id)

    student_name = student.display_name if student else "Unknown Student"
    grade_name = grade.name if grade else "Unknown Grade"
    breadcrumb = f"{student_name} > {grade_name}"

    # ── Card list ──────────────────────────────────────────────────────────────
    cards_column = ft.Column(
        controls=[],
        spacing=8,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    empty_state = ft.Column(
        controls=[
            ft.Icon(ft.Icons.MENU_BOOK, size=64, color=ft.Colors.GREY_400),
            ft.Text(
                "No subjects yet.",
                size=16,
                color=ft.Colors.GREY_600,
                weight=ft.FontWeight.W_500,
            ),
            ft.Text(
                'Tap "Add Material" to create one (e.g. "Biology").',
                size=13,
                color=ft.Colors.GREY_500,
            ),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=8,
        expand=True,
    )

    def go_to_material(mat: Material) -> None:
        page.route = f"/student/{student_id}/grade/{grade_id}/material/{mat.id}"
        page.update()

    async def refresh() -> None:
        try:
            materials = await storage.list_materials(grade_id)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to list materials for grade %s", grade_id)
            return
        cards_column.controls.clear()
        if not materials:
            cards_column.controls.append(empty_state)
        else:
            for m in materials:
                try:
                    files = await storage.list_files(m.id)
                    count = len(files)
                except Exception:  # noqa: BLE001
                    count = 0
                cards_column.controls.append(material_card.build(m, count, go_to_material))
        page.update()

    # ── Add Material dialog ────────────────────────────────────────────────────
    def open_add_dialog(_e: ft.ControlEvent) -> None:
        title_field = ft.TextField(
            label='Subject name (e.g. "Biology")',
            autofocus=True,
            width=360,
            on_submit=lambda e: asyncio.create_task(_do_add(e)),
        )
        error_text = ft.Text("", color=ft.Colors.RED_700, size=12, visible=False)

        async def _do_add(_e: ft.ControlEvent) -> None:
            title = (title_field.value or "").strip()
            if not title:
                error_text.value = "Subject name cannot be empty."
                error_text.visible = True
                page.update()
                return
            mat = Material(
                id=uuid.uuid4().hex,
                student_id=student_id,
                grade_id=grade_id,
                title=title,
                created_at=datetime.now(timezone.utc),
            )
            try:
                await storage.insert_material(mat)
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
            title=ft.Text("Add Material"),
            content=ft.Container(
                content=ft.Column(
                    controls=[title_field, error_text],
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
        page.route = f"/student/{student_id}"
        page.update()

    appbar = ft.AppBar(
        title=ft.Text(breadcrumb),
        center_title=False,
        leading=ft.IconButton(icon=ft.Icons.ARROW_BACK, on_click=go_back),
    )

    fab = ft.FloatingActionButton(
        icon=ft.Icons.ADD,
        tooltip="Add Material",
        on_click=open_add_dialog,
    )

    body = ft.Container(
        content=cards_column,
        padding=20,
        expand=True,
    )

    view = ft.View(
        route=f"/student/{student_id}/grade/{grade_id}",
        appbar=appbar,
        controls=[body],
        floating_action_button=fab,
        floating_action_button_location=ft.FloatingActionButtonLocation.END_FLOAT,
    )

    await refresh()
    return view
