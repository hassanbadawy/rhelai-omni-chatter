"""`/` — home screen: list of all students.

Layout:
    AppBar: "Students" title + Settings icon button
    Body:   one StudentCard per student, sorted by created_at DESC
    FAB:    "Add Student"
    Empty:  centred icon + prompt text
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

import flet as ft

from domain.models import Student
from services.storage import Storage
from widgets import student_card

logger = logging.getLogger(__name__)


async def build(page: ft.Page) -> ft.View:
    storage: Storage = page.session.store.get("storage")

    # ── Card list ──────────────────────────────────────────────────────────────
    cards_column = ft.Column(
        controls=[],
        spacing=8,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    empty_state = ft.Column(
        controls=[
            ft.Icon(ft.Icons.PERSON_ADD_ALT_1, size=64, color=ft.Colors.GREY_400),
            ft.Text(
                "No students yet.",
                size=16,
                color=ft.Colors.GREY_600,
                weight=ft.FontWeight.W_500,
            ),
            ft.Text(
                'Tap "Add Student" to get started.',
                size=13,
                color=ft.Colors.GREY_500,
            ),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=8,
        expand=True,
    )

    def go_to_student(student: Student) -> None:
        page.route = f"/student/{student.id}"
        page.update()

    async def refresh() -> None:
        try:
            students = await storage.list_students()
        except Exception:  # noqa: BLE001
            logger.exception("Failed to list students")
            return
        cards_column.controls.clear()
        if not students:
            cards_column.controls.append(empty_state)
        else:
            for s in students:
                cards_column.controls.append(student_card.build(s, go_to_student))
        page.update()

    # ── Add Student dialog ─────────────────────────────────────────────────────
    def open_add_dialog(_e: ft.ControlEvent) -> None:
        name_field = ft.TextField(
            label="Student name",
            autofocus=True,
            width=360,
            on_submit=lambda e: asyncio.create_task(_do_add(e)),
        )
        error_text = ft.Text("", color=ft.Colors.RED_700, size=12, visible=False)

        async def _do_add(_e: ft.ControlEvent) -> None:
            name = (name_field.value or "").strip()
            if not name:
                error_text.value = "Name cannot be empty."
                error_text.visible = True
                page.update()
                return
            now = datetime.now(timezone.utc)
            student = Student(
                id=uuid.uuid4().hex,
                display_name=name,
                created_at=now,
            )
            try:
                await storage.insert_student(student)
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
            title=ft.Text("Add Student"),
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

    # ── AppBar ─────────────────────────────────────────────────────────────────
    def go_to_settings(_e: ft.ControlEvent) -> None:
        page.route = "/settings"
        page.update()

    appbar = ft.AppBar(
        title=ft.Text("Students"),
        center_title=False,
        actions=[
            ft.IconButton(
                icon=ft.Icons.SETTINGS,
                tooltip="Settings",
                on_click=go_to_settings,
            ),
        ],
    )

    # ── FAB ───────────────────────────────────────────────────────────────────
    fab = ft.FloatingActionButton(
        icon=ft.Icons.PERSON_ADD,
        tooltip="Add Student",
        on_click=open_add_dialog,
    )

    # ── Body ──────────────────────────────────────────────────────────────────
    body = ft.Container(
        content=cards_column,
        padding=20,
        expand=True,
    )

    view = ft.View(
        route="/",
        appbar=appbar,
        controls=[body],
        floating_action_button=fab,
        floating_action_button_location=ft.FloatingActionButtonLocation.END_FLOAT,
    )

    await refresh()
    return view
