"""File card widget.

Shows filename, upload_type badge, status badge, and action buttons.
Action buttons appear only when the file is READY and upload_type is EXERCISE_SHEET.
"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

from domain.enums import FileStatus, UploadType
from domain.models import MaterialFile

# Status badge colours.
_STATUS_COLORS: dict[FileStatus, str] = {
    FileStatus.UPLOADING: ft.Colors.GREY_500,
    FileStatus.CONVERTING: ft.Colors.BLUE_600,
    FileStatus.CLASSIFYING: ft.Colors.INDIGO_400,
    FileStatus.EXTRACTING: ft.Colors.PURPLE_400,
    FileStatus.READY: ft.Colors.GREEN_700,
    FileStatus.FAILED: ft.Colors.RED_700,
}

# Upload-type badge colours.
_TYPE_COLORS: dict[UploadType, str] = {
    UploadType.EXERCISE_SHEET: ft.Colors.ORANGE_700,
    UploadType.MATERIAL: ft.Colors.TEAL_700,
    UploadType.ANSWER_SHEET: ft.Colors.CYAN_700,
}

_IN_PROGRESS = {FileStatus.CONVERTING, FileStatus.CLASSIFYING, FileStatus.EXTRACTING}


def _badge(label: str, color: str) -> ft.Container:
    return ft.Container(
        content=ft.Text(label, size=11, color=ft.Colors.WHITE, weight=ft.FontWeight.W_500),
        bgcolor=color,
        padding=ft.padding.symmetric(horizontal=8, vertical=4),
        border_radius=12,
    )


def build(
    mf: MaterialFile,
    on_view_questions: Callable[[], None] | None = None,
    on_start_test: Callable[[], None] | None = None,
) -> ft.Card:
    """Return a Card for *mf* with status-appropriate content."""
    status_color = _STATUS_COLORS.get(mf.status, ft.Colors.GREY_500)
    type_color = _TYPE_COLORS.get(mf.upload_type, ft.Colors.GREY_700)

    status_badge = _badge(mf.status.value.upper(), status_color)
    type_badge = _badge(mf.upload_type.value.replace("_", " ").upper(), type_color)

    header = ft.Row(
        controls=[
            ft.Icon(ft.Icons.DESCRIPTION, color=ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE)),
            ft.Text(
                mf.original_filename,
                size=14,
                weight=ft.FontWeight.W_500,
                expand=True,
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
        ],
        spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    badge_row = ft.Row(controls=[type_badge, status_badge], spacing=8)

    # Build the status-specific trailing content.
    extra_controls: list[ft.Control] = []

    if mf.status in _IN_PROGRESS:
        extra_controls.append(
            ft.Row(
                controls=[
                    ft.ProgressRing(width=16, height=16, stroke_width=2),
                    ft.Text(
                        mf.status_detail or mf.status.value.capitalize() + "…",
                        size=12,
                        color=ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE),
                        italic=True,
                    ),
                ],
                spacing=8,
            )
        )

    elif mf.status == FileStatus.FAILED:
        extra_controls.append(
            ft.Text(
                mf.status_detail or "Processing failed.",
                size=12,
                color=ft.Colors.RED_700,
                max_lines=3,
                overflow=ft.TextOverflow.ELLIPSIS,
            )
        )

    elif mf.status == FileStatus.READY and mf.upload_type == UploadType.EXERCISE_SHEET:
        action_controls: list[ft.Control] = []
        if on_view_questions is not None:
            action_controls.append(
                ft.OutlinedButton(
                    content="View Questions",
                    icon=ft.Icons.LIST_ALT,
                    on_click=lambda _e: on_view_questions(),
                )
            )
        if on_start_test is not None:
            action_controls.append(
                ft.FilledButton(
                    content="Start Test",
                    icon=ft.Icons.PLAY_ARROW,
                    on_click=lambda _e: on_start_test(),
                )
            )
        if action_controls:
            extra_controls.append(ft.Row(controls=action_controls, spacing=8))

    elif mf.status == FileStatus.READY:
        extra_controls.append(
            ft.Text(
                "Ready",
                size=12,
                color=ft.Colors.GREEN_700,
                italic=True,
            )
        )

    body = ft.Column(
        controls=[header, badge_row, *extra_controls],
        spacing=8,
    )

    return ft.Card(
        content=ft.Container(content=body, padding=14, border_radius=12),
        elevation=1,
    )
