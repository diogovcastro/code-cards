"""Suporte aos botões extras do mouse (8 a 11) no terminal.

No protocolo SGR, os botões extras chegam com os códigos 128 a 131. O parser
do Textual calcula o botão com ``(código + 1) & 3``, então o lateral "voltar"
(128) vira um clique esquerdo e o "avançar" (129) vira o botão do meio.
``install_extra_button_support`` corrige isso trocando
``XTermParser.parse_mouse_code`` por uma versão que reconhece esses códigos.

Depende de uma parte interna do Textual; ``tests/test_mouse.py`` avisa se uma
atualização quebrar a correção.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from textual import events
from textual._xterm_parser import XTermParser

from code_cards.models import MOUSE_BUTTON_BY_NUMBER

EXTRA_BUTTONS_FLAG = 128
_MOTION_FLAG = 32
_WHEEL_FLAG = 64

_installed = False


def button_name(button: int) -> str | None:
    """Nome usado nas configurações (``"button8"``...) ou ``None`` se não configurável."""
    return MOUSE_BUTTON_BY_NUMBER.get(button)


def _fix_extra_button(original: Callable[[Any, str], Any]) -> Callable[[Any, str], Any]:
    def parse_mouse_code(self: XTermParser, code: str) -> events.Message | None:
        event = original(self, code)
        match = self._re_sgr_mouse.match(code)
        if event is None or match is None:
            return event
        buttons = int(match.group(1))
        if not buttons & EXTRA_BUTTONS_FLAG or buttons & (_WHEEL_FLAG | _MOTION_FLAG):
            return event
        assert isinstance(event, events.MouseEvent)
        event_class = events.MouseDown if match.group(4) == "M" else events.MouseUp
        return event_class(
            None,
            event.x,
            event.y,
            event.delta_x,
            event.delta_y,
            8 + (buttons & 3),
            event.shift,
            event.meta,
            event.ctrl,
            screen_x=event.screen_x,
            screen_y=event.screen_y,
        )

    parse_mouse_code.__wrapped__ = original  # type: ignore[attr-defined]
    return parse_mouse_code


def install_extra_button_support() -> None:
    """Aplica a correção ao parser do Textual (idempotente)."""
    global _installed
    if _installed:
        return
    XTermParser.parse_mouse_code = _fix_extra_button(  # type: ignore[method-assign,assignment]
        XTermParser.parse_mouse_code
    )
    _installed = True
