"""`/student/{student_id}/grade/{grade_id}/material/{material_id}/test/{file_id}`

Quiz UI. One question per screen. Navigation: Previous / Next / Submit.
Scoring: is_correct = True if answer (stripped, lowercased) == student_answer (stripped, lowercased).
Shows a summary screen at the end with score and a "Back to Files" button.
"""

from __future__ import annotations

import json
import logging

import flet as ft

from domain.enums import QuestionType
from domain.models import Question
from services.storage import Storage

logger = logging.getLogger(__name__)


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
    route = f"{base_route}/test/{file_id}"

    def go_back(_e: ft.ControlEvent) -> None:
        page.route = base_route
        page.update()

    appbar = ft.AppBar(
        title=ft.Text("Test"),
        center_title=False,
        leading=ft.IconButton(icon=ft.Icons.ARROW_BACK, on_click=go_back),
    )

    # ── No questions guard ─────────────────────────────────────────────────────
    if not questions:
        return ft.View(
            route=route,
            appbar=appbar,
            controls=[
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.QUIZ, size=64, color=ft.Colors.GREY_400),
                            ft.Text(
                                "No questions available.",
                                size=16,
                                color=ft.Colors.GREY_600,
                            ),
                            ft.Text(
                                "The file may still be processing.",
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
            ],
        )

    # ── State ─────────────────────────────────────────────────────────────────
    n = len(questions)
    # student_answers[i] stores what the student answered for question i (str)
    student_answers: list[str] = [""] * n
    state = {"idx": 0, "submitted": False}

    # Mutable container for the question area — swapped on navigation.
    question_area = ft.Column(controls=[], spacing=12, expand=True)

    progress_text = ft.Text("", size=13, color=ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE))
    prev_button = ft.OutlinedButton(content="Previous", icon=ft.Icons.ARROW_BACK_IOS, disabled=True)
    next_button = ft.FilledButton(content="Next", icon=ft.Icons.ARROW_FORWARD_IOS)
    submit_button = ft.FilledButton(
        content="Submit",
        icon=ft.Icons.CHECK_CIRCLE,
        visible=False,
        style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_700),
    )

    nav_row = ft.Row(
        controls=[prev_button, ft.Container(expand=True), progress_text, ft.Container(expand=True), next_button, submit_button],
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    # ── Question renderer ──────────────────────────────────────────────────────
    def _render_q(q: Question, i: int) -> None:
        """Rebuild question_area for question at index i."""
        question_area.controls.clear()

        header = ft.Text(
            f"Q{i + 1} / {n}:  {q.question_text}",
            size=15,
            weight=ft.FontWeight.W_500,
        )
        question_area.controls.append(header)

        if q.q_type == QuestionType.MCQ:
            options: list[str] = []
            if q.options_json:
                try:
                    options = json.loads(q.options_json)
                except json.JSONDecodeError:
                    options = []

            def on_radio_change(e: ft.ControlEvent, idx: int = i) -> None:
                student_answers[idx] = e.control.value or ""

            radio_controls = [ft.Radio(value=opt, label=opt) for opt in options]
            rg = ft.RadioGroup(
                content=ft.Column(controls=radio_controls, spacing=4),
                value=student_answers[i] or None,
                on_change=on_radio_change,
            )
            question_area.controls.append(rg)

        elif q.q_type == QuestionType.TRUE_OR_FALSE:
            current = student_answers[i]

            def _pick_true(_e: ft.ControlEvent, idx: int = i) -> None:
                student_answers[idx] = "true"
                _render_q(questions[idx], idx)
                _sync_nav()
                page.update()

            def _pick_false(_e: ft.ControlEvent, idx: int = i) -> None:
                student_answers[idx] = "false"
                _render_q(questions[idx], idx)
                _sync_nav()
                page.update()

            true_btn = ft.ElevatedButton(
                content="True",
                bgcolor=ft.Colors.GREEN_100 if current == "true" else None,
                on_click=_pick_true,
            )
            false_btn = ft.ElevatedButton(
                content="False",
                bgcolor=ft.Colors.RED_100 if current == "false" else None,
                on_click=_pick_false,
            )
            question_area.controls.append(
                ft.Row(controls=[true_btn, false_btn], spacing=16)
            )

        elif q.q_type in (QuestionType.TEXT_QNA, QuestionType.IMAGE_QNA):
            if q.q_type == QuestionType.IMAGE_QNA and q.image_path:
                question_area.controls.append(
                    ft.Image(
                        src=q.image_path,
                        width=380,
                        fit=ft.ImageFit.CONTAIN,
                        error_content=ft.Text(
                            f"[Image: {q.image_path}]",
                            size=12,
                            color=ft.Colors.RED_400,
                        ),
                    )
                )

            def on_text_change(e: ft.ControlEvent, idx: int = i) -> None:
                student_answers[idx] = e.control.value or ""

            tf = ft.TextField(
                label="Your answer",
                multiline=True,
                min_lines=3,
                max_lines=6,
                value=student_answers[i],
                on_change=on_text_change,
                expand=True,
            )
            question_area.controls.append(tf)

        elif q.q_type == QuestionType.TABLE_COMPARISON:
            table_data: list[list[str]] = []
            if q.table_json:
                try:
                    table_data = json.loads(q.table_json)
                except json.JSONDecodeError:
                    table_data = []
            if table_data and len(table_data) > 0:
                header_row = table_data[0] if isinstance(table_data[0], list) else []
                data_rows = table_data[1:]
                columns = [ft.DataColumn(ft.Text(str(h), weight=ft.FontWeight.W_600)) for h in header_row]
                rows = [
                    ft.DataRow(cells=[ft.DataCell(ft.Text(str(cell))) for cell in row])
                    for row in data_rows
                    if isinstance(row, list)
                ]
                if columns:
                    question_area.controls.append(ft.DataTable(columns=columns, rows=rows))

            def on_table_text_change(e: ft.ControlEvent, idx: int = i) -> None:
                student_answers[idx] = e.control.value or ""

            tf = ft.TextField(
                label="Your answer",
                multiline=True,
                min_lines=2,
                max_lines=4,
                value=student_answers[i],
                on_change=on_table_text_change,
                expand=True,
            )
            question_area.controls.append(tf)

    def _sync_nav() -> None:
        idx = state["idx"]
        progress_text.value = f"{idx + 1} / {n}"
        prev_button.disabled = idx == 0
        is_last = idx == n - 1
        next_button.visible = not is_last
        submit_button.visible = is_last

    # ── Navigation callbacks ───────────────────────────────────────────────────
    def on_prev(_e: ft.ControlEvent) -> None:
        if state["idx"] > 0:
            state["idx"] -= 1
            _render_q(questions[state["idx"]], state["idx"])
            _sync_nav()
            page.update()

    def on_next(_e: ft.ControlEvent) -> None:
        if state["idx"] < n - 1:
            state["idx"] += 1
            _render_q(questions[state["idx"]], state["idx"])
            _sync_nav()
            page.update()

    def on_submit(_e: ft.ControlEvent) -> None:
        """Score answers and show summary."""
        correct = 0
        for qi, q in enumerate(questions):
            expected = (q.answer or "").strip().lower()
            given = student_answers[qi].strip().lower()
            if expected and given == expected:
                correct += 1

        _show_summary(correct, n)

    prev_button.on_click = on_prev
    next_button.on_click = on_next
    submit_button.on_click = on_submit

    # ── Summary screen ─────────────────────────────────────────────────────────
    summary_container = ft.Container(visible=False, expand=True)
    quiz_container = ft.Container(
        content=ft.Column(
            controls=[
                ft.Container(content=question_area, expand=True, padding=ft.padding.only(bottom=16)),
                nav_row,
            ],
            expand=True,
            spacing=0,
        ),
        padding=20,
        expand=True,
    )

    def _show_summary(correct: int, total: int) -> None:
        pct = int(correct / total * 100) if total else 0
        if pct >= 80:
            icon = ft.Icons.EMOJI_EVENTS
            icon_color = ft.Colors.AMBER_700
            msg = "Excellent work!"
        elif pct >= 60:
            icon = ft.Icons.THUMB_UP
            icon_color = ft.Colors.GREEN_700
            msg = "Good job!"
        else:
            icon = ft.Icons.SCHOOL
            icon_color = ft.Colors.BLUE_700
            msg = "Keep practising!"

        summary_container.content = ft.Column(
            controls=[
                ft.Icon(icon, size=80, color=icon_color),
                ft.Text(
                    f"You got {correct} / {total} correct!",
                    size=24,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Text(f"{pct}%  —  {msg}", size=16, color=ft.Colors.with_opacity(0.7, ft.Colors.ON_SURFACE)),
                ft.Container(height=24),
                ft.ElevatedButton(
                    content="Back to Files",
                    icon=ft.Icons.FOLDER_OPEN,
                    on_click=go_back,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=12,
            expand=True,
        )
        summary_container.visible = True
        quiz_container.visible = False
        state["submitted"] = True
        page.update()

    # ── Initial render ─────────────────────────────────────────────────────────
    _render_q(questions[0], 0)
    _sync_nav()

    body = ft.Stack(
        controls=[quiz_container, summary_container],
        expand=True,
    )

    return ft.View(
        route=route,
        appbar=appbar,
        controls=[body],
    )
