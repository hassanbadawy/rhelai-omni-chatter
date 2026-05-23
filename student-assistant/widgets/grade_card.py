"""Grade card widget — one card per grade under a student."""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

from domain.models import Grade


def build(grade: Grade, material_count: int, on_click: Callable[[Grade], None]) -> ft.Card:
    """Return a Card for *grade*. Shows material count as a subtitle."""
    subtitle = (
        f"{material_count} subject{'s' if material_count != 1 else ''}"
        if material_count > 0
        else "No subjects yet"
    )

    content = ft.Container(
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.SCHOOL, size=32, color=ft.Colors.SECONDARY),
                        ft.Column(
                            controls=[
                                ft.Text(
                                    grade.name,
                                    size=16,
                                    weight=ft.FontWeight.W_600,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Text(
                                    subtitle,
                                    size=12,
                                    color=ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE),
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
        on_click=lambda _e: on_click(grade),
    )
    return ft.Card(content=content, elevation=1)
