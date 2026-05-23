"""Student card widget — one card per student on the home screen."""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

from domain.models import Student


def build(student: Student, on_click: Callable[[Student], None]) -> ft.Card:
    """Return a Card for *student*. Clicking the card calls *on_click(student)*."""
    content = ft.Container(
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.PERSON, size=32, color=ft.Colors.PRIMARY),
                        ft.Column(
                            controls=[
                                ft.Text(
                                    student.display_name,
                                    size=16,
                                    weight=ft.FontWeight.W_600,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Text(
                                    student.email or "Click to open",
                                    size=12,
                                    color=ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE),
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        ft.Icon(
                            ft.Icons.CHEVRON_RIGHT,
                            color=ft.Colors.with_opacity(0.4, ft.Colors.ON_SURFACE),
                        ),
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            spacing=0,
        ),
        padding=16,
        ink=True,
        border_radius=12,
        on_click=lambda _e: on_click(student),
    )
    return ft.Card(content=content, elevation=1)
