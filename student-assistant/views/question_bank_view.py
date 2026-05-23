"""`/student/{student_id}/grade/{grade_id}/material/{material_id}/questions/{file_id}`

Displays all extracted questions for a file in read-only mode.
Question types rendered:
  - MCQ            → question text + labelled options (read-only RadioGroup)
  - TRUE_OR_FALSE  → question text + "True / False" labels
  - TEXT_QNA       → question text + grey answer box
  - IMAGE_QNA      → question text + ft.Image if image_path set
  - TABLE_COMPARISON → question text + ft.DataTable

A "Start Test" button at the top links to the test route.
"""

from __future__ import annotations

import json
import logging

import flet as ft

from domain.enums import QuestionType
from domain.models import Question
from services.storage import Storage

logger = logging.getLogger(__name__)


def _render_question(q: Question, index: int) -> ft.Control:
    """Build a read-only card for a single question."""
    header = ft.Text(
        f"Q{index + 1}. {q.question_text}",
        size=14,
        weight=ft.FontWeight.W_500,
    )

    body_controls: list[ft.Control] = [header]

    if q.q_type == QuestionType.MCQ:
        options: list[str] = []
        if q.options_json:
            try:
                options = json.loads(q.options_json)
            except json.JSONDecodeError:
                options = []
        if options:
            radio_controls = [
                ft.Radio(value=opt, label=opt)
                for opt in options
            ]
            body_controls.append(
                ft.RadioGroup(
                    content=ft.Column(controls=radio_controls, spacing=4),
                    value=None,  # read-only — no pre-selection
                )
            )

    elif q.q_type == QuestionType.TRUE_OR_FALSE:
        body_controls.append(
            ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Text("True", size=13, color=ft.Colors.GREEN_700),
                        border=ft.border.all(1, ft.Colors.GREEN_700),
                        border_radius=8,
                        padding=ft.padding.symmetric(horizontal=16, vertical=6),
                    ),
                    ft.Container(
                        content=ft.Text("False", size=13, color=ft.Colors.RED_700),
                        border=ft.border.all(1, ft.Colors.RED_700),
                        border_radius=8,
                        padding=ft.padding.symmetric(horizontal=16, vertical=6),
                    ),
                ],
                spacing=12,
            )
        )

    elif q.q_type == QuestionType.TEXT_QNA:
        body_controls.append(
            ft.Container(
                content=ft.Text(
                    "Answer here…",
                    size=13,
                    color=ft.Colors.with_opacity(0.4, ft.Colors.ON_SURFACE),
                    italic=True,
                ),
                bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                border_radius=8,
                padding=14,
                width=float("inf"),
                min_height=60,
            )
        )

    elif q.q_type == QuestionType.IMAGE_QNA:
        if q.image_path:
            body_controls.append(
                ft.Image(
                    src=q.image_path,
                    width=400,
                    fit=ft.ImageFit.CONTAIN,
                    error_content=ft.Text(
                        f"[Image not found: {q.image_path}]",
                        size=12,
                        color=ft.Colors.RED_400,
                    ),
                )
            )
        body_controls.append(
            ft.Container(
                content=ft.Text(
                    "Answer here…",
                    size=13,
                    color=ft.Colors.with_opacity(0.4, ft.Colors.ON_SURFACE),
                    italic=True,
                ),
                bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                border_radius=8,
                padding=14,
                width=float("inf"),
                min_height=60,
            )
        )

    elif q.q_type == QuestionType.TABLE_COMPARISON:
        table_data: list[list[str]] = []
        if q.table_json:
            try:
                table_data = json.loads(q.table_json)
            except json.JSONDecodeError:
                table_data = []
        if table_data and isinstance(table_data, list) and len(table_data) > 0:
            header_row = table_data[0] if isinstance(table_data[0], list) else []
            data_rows = table_data[1:] if len(table_data) > 1 else []
            columns = [ft.DataColumn(ft.Text(str(h), weight=ft.FontWeight.W_600)) for h in header_row]
            rows = [
                ft.DataRow(cells=[ft.DataCell(ft.Text(str(cell))) for cell in row])
                for row in data_rows
                if isinstance(row, list)
            ]
            if columns:
                body_controls.append(ft.DataTable(columns=columns, rows=rows))

    return ft.Card(
        content=ft.Container(
            content=ft.Column(controls=body_controls, spacing=10),
            padding=16,
        ),
        elevation=1,
    )


async def build(
    page: ft.Page,
    student_id: str,
    grade_id: str,
    material_id: str,
    file_id: str,
) -> ft.View:
    storage: Storage = page.session.store.get("storage")

    questions = await storage.list_questions_for_file(file_id)

    base_route = f"/student/{student_id}/grade/{grade_id}/material/{material_id}"
    route = f"{base_route}/questions/{file_id}"

    def go_back(_e: ft.ControlEvent) -> None:
        page.route = base_route
        page.update()

    def go_to_test(_e: ft.ControlEvent) -> None:
        page.route = f"{base_route}/test/{file_id}"
        page.update()

    appbar = ft.AppBar(
        title=ft.Text("Question Bank"),
        center_title=False,
        leading=ft.IconButton(icon=ft.Icons.ARROW_BACK, on_click=go_back),
        actions=[
            ft.Container(
                content=ft.FilledButton(
                    content="Start Test",
                    icon=ft.Icons.PLAY_ARROW,
                    on_click=go_to_test,
                    disabled=len(questions) == 0,
                ),
                padding=ft.padding.only(right=8),
            )
        ],
    )

    if not questions:
        body = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.QUIZ, size=64, color=ft.Colors.GREY_400),
                    ft.Text(
                        "No questions extracted yet.",
                        size=16,
                        color=ft.Colors.GREY_600,
                        weight=ft.FontWeight.W_500,
                    ),
                    ft.Text(
                        "Processing may still be in progress.",
                        size=13,
                        color=ft.Colors.GREY_500,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=8,
                expand=True,
            ),
            alignment=ft.alignment.center,
            expand=True,
            padding=40,
        )
    else:
        question_cards = [_render_question(q, i) for i, q in enumerate(questions)]
        summary = ft.Text(
            f"{len(questions)} question{'s' if len(questions) != 1 else ''}",
            size=12,
            color=ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE),
        )
        body = ft.Container(
            content=ft.Column(
                controls=[summary, *question_cards],
                spacing=12,
                scroll=ft.ScrollMode.AUTO,
            ),
            padding=20,
            expand=True,
        )

    return ft.View(
        route=route,
        appbar=appbar,
        controls=[body],
    )
