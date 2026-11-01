from __future__ import annotations

import pytest
from textual import events
from textual._xterm_parser import XTermParser

from code_cards.tui.mouse import button_name, install_extra_button_support


def parse(sequence: str) -> list[events.Message]:
    install_extra_button_support()
    return list(XTermParser().feed(sequence))


@pytest.mark.parametrize(("code", "button"), [(128, 8), (129, 9), (130, 10), (131, 11)])
def test_botoes_extras(code: int, button: int) -> None:
    [down] = parse(f"\x1b[<{code};10;5M")
    assert isinstance(down, events.MouseDown)
    assert down.button == button
    assert (down.x, down.y) == (9, 4)
    [up] = parse(f"\x1b[<{code};10;5m")
    assert isinstance(up, events.MouseUp)
    assert up.button == button


@pytest.mark.parametrize(("code", "button"), [(0, 1), (1, 2), (2, 3)])
def test_botoes_comuns_continuam_iguais(code: int, button: int) -> None:
    [down] = parse(f"\x1b[<{code};3;3M")
    assert isinstance(down, events.MouseDown)
    assert down.button == button


def test_roda_e_movimento_continuam_iguais() -> None:
    [scroll] = parse("\x1b[<64;3;3M")
    assert isinstance(scroll, events.MouseScrollUp)
    [move] = parse("\x1b[<35;3;3M")
    assert isinstance(move, events.MouseMove)


def test_instalar_duas_vezes_nao_empilha() -> None:
    install_extra_button_support()
    install_extra_button_support()
    [down] = parse("\x1b[<128;1;1M")
    assert down.button == 8


def test_nomes_dos_botoes() -> None:
    assert button_name(8) == "button8"
    assert button_name(2) == "middle"
    assert button_name(1) is None
