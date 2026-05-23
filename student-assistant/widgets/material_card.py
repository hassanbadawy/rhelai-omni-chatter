"""Material card widget — one card per subject/material under a grade."""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

from domain.models import Material


def build(material: Material, file_count: int, on_click: Callable[[Material], None]) -> ft.Card:
    """Return a Card for *material*. Shows file count as a subtitle."""
    subtitle = (
        f"{file_count} file{'s' if file_count != 1 else ''}"
        if file_count > 0
        else "No files yet"
    )

    content = ft.Container(
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.MENU_BOOK, size=32, color=ft.Colors.TERTIARY),
                        ft.Column(
                            controls=[
                                ft.Text(
                                    material.title,
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
        on_click=lambda _e: on_click(material),
    )
    return ft.Card(content=content, elevation=1)
