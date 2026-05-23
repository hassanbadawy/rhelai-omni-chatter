"""Flet pages. Each module exposes `build(page, ...)` returning a Control tree.

Routes are mapped in `app.py` `on_route_change`. Views consume `services/`
through a small dependency container set on `page.session`.
"""
