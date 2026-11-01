"""Ajudantes para simular o mouse como o terminal real (passando pelo App.on_event)."""

from __future__ import annotations

from textual import events
from textual.app import App
from textual.pilot import Pilot


def _mouse(cls: type[events.MouseEvent], button: int, x: int, y: int) -> events.MouseEvent:
    return cls(None, x, y, 0, 0, button, False, False, False, screen_x=x, screen_y=y)


async def mouse_click(
    app: App[None], pilot: Pilot[None], button: int, x: int = 5, y: int = 5
) -> None:
    """Aperta e solta um botão do mouse na posição (x, y) da tela."""
    app.post_message(_mouse(events.MouseDown, button, x, y))
    app.post_message(_mouse(events.MouseUp, button, x, y))
    await pilot.pause()
    await pilot.pause()
