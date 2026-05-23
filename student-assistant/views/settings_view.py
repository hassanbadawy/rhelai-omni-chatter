"""`/settings` — application settings page.

Editable fields:
  - Docling URL      (key: docling_url)
  - LLM Base URL     (key: llm_base_url)
  - LLM Model        (key: llm_model)
  - LLM API Key      (key: llm_api_key) — rendered as password field

"Save" persists all four fields and shows a SnackBar confirmation.
"""

from __future__ import annotations

import logging

import flet as ft

from services.settings_service import KEYS, SettingsService

logger = logging.getLogger(__name__)

_FIELD_META: list[tuple[str, str, bool]] = [
    ("docling_url", "Docling URL", False),
    ("llm_base_url", "LLM Base URL", False),
    ("llm_model", "LLM Model", False),
    ("llm_api_key", "LLM API Key", True),
]


async def build(page: ft.Page) -> ft.View:
    settings: SettingsService = page.session.store.get("settings")

    # Load current values.
    try:
        current = await settings.get_all()
    except Exception:  # noqa: BLE001
        logger.exception("Failed to load settings")
        current = {}

    # Build one TextField per setting key.
    fields: dict[str, ft.TextField] = {}
    for key, label, is_password in _FIELD_META:
        fields[key] = ft.TextField(
            label=label,
            value=current.get(key, ""),
            password=is_password,
            can_reveal_password=is_password,
            width=480,
            expand=True,
        )

    save_status = ft.Text("", size=13, color=ft.Colors.GREEN_700, visible=False)

    async def on_save(_e: ft.ControlEvent) -> None:
        save_status.visible = False
        errors: list[str] = []
        for key in KEYS:
            val = (fields[key].value or "").strip()
            try:
                await settings.save(key, val)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{key}: {exc}")
        if errors:
            page.show_snack_bar(
                ft.SnackBar(
                    content=ft.Text("Errors: " + "; ".join(errors)),
                    bgcolor=ft.Colors.RED_700,
                )
            )
        else:
            page.show_snack_bar(
                ft.SnackBar(
                    content=ft.Text("Settings saved!"),
                    bgcolor=ft.Colors.GREEN_700,
                )
            )
        page.update()

    save_button = ft.FilledButton(
        content="Save",
        icon=ft.Icons.SAVE,
        on_click=on_save,
    )

    def go_back(_e: ft.ControlEvent) -> None:
        page.route = "/"
        page.update()

    appbar = ft.AppBar(
        title=ft.Text("Settings"),
        center_title=False,
        leading=ft.IconButton(icon=ft.Icons.ARROW_BACK, on_click=go_back),
    )

    form_controls: list[ft.Control] = []
    for key, label, _ in _FIELD_META:
        form_controls.append(fields[key])

    form_controls.append(ft.Container(height=8))
    form_controls.append(save_button)
    form_controls.append(save_status)

    body = ft.Container(
        content=ft.Column(
            controls=form_controls,
            spacing=16,
            scroll=ft.ScrollMode.AUTO,
        ),
        padding=24,
        expand=True,
    )

    return ft.View(
        route="/settings",
        appbar=appbar,
        controls=[body],
    )
