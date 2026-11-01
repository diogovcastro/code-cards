from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import TextArea

from code_cards.services.container import Services
from code_cards.tui.app import CodeCardsApp
from code_cards.tui.screens.study import StudyScreen
from tests.factories import make_services

LONG_CODE = "\n".join(f"linha_{i} = {i}" for i in range(80))
LONG_DESCRIPTION = " ".join(f"Frase número {i} da descrição." for i in range(80))


@pytest.fixture
def svc(tmp_path: Path) -> Services:
    svc = make_services(tmp_path)
    svc.importer.import_batch(
        {
            "deck": "Longo",
            "create_deck_if_missing": True,
            "cards": [{"code": LONG_CODE, "description": LONG_DESCRIPTION}],
        }
    )
    return svc


async def open_study(app: CodeCardsApp, pilot) -> StudyScreen:  # type: ignore[no-untyped-def]
    await pilot.press("enter")
    await pilot.pause()
    assert isinstance(app.screen, StudyScreen)
    return app.screen


async def test_antes_de_revelar_rola_o_codigo(svc: Services) -> None:
    app = CodeCardsApp(svc)
    async with app.run_test(size=(80, 24)) as pilot:
        screen = await open_study(app, pilot)
        code = screen.query_one("#code", TextArea)
        assert screen.focused is code
        await pilot.press("down", "down", "down")
        assert code.scroll_y == 3
        await pilot.press("up")
        assert code.scroll_y == 2
        await pilot.press("w")  # rolar para cima (padrão)
        assert code.scroll_y == 1
        # As setas rolam de verdade, sem mover cursor.
        assert code.cursor_location == (0, 0)


async def test_revelar_move_o_foco_para_a_descricao(svc: Services) -> None:
    app = CodeCardsApp(svc)
    async with app.run_test(size=(80, 24)) as pilot:
        screen = await open_study(app, pilot)
        code = screen.query_one("#code", TextArea)
        desc = screen.query_one("#description-box")
        await pilot.press("space")
        await pilot.pause()
        assert screen.focused is desc
        await pilot.press("down", "down")
        assert desc.scroll_y == 2
        assert code.scroll_y == 0


async def test_clique_esquerdo_troca_a_secao(svc: Services) -> None:
    app = CodeCardsApp(svc)
    async with app.run_test(size=(80, 24)) as pilot:
        screen = await open_study(app, pilot)
        code = screen.query_one("#code", TextArea)
        desc = screen.query_one("#description-box")
        await pilot.press("space")
        await pilot.pause()

        await pilot.click("#code", offset=(10, 3))
        await pilot.pause()
        assert screen.focused is code
        assert code.selection.is_empty
        assert code.cursor_location == (0, 0)
        await pilot.press("down")
        assert code.scroll_y == 1
        assert desc.scroll_y == 0

        await pilot.click("#description-box", offset=(5, 1))
        await pilot.pause()
        assert screen.focused is desc
        await pilot.press("down")
        assert desc.scroll_y == 1
        assert code.scroll_y == 1


async def test_trocar_o_foco_nao_muda_nada_na_tela(svc: Services) -> None:
    app = CodeCardsApp(svc)
    async with app.run_test(size=(80, 24)) as pilot:
        screen = await open_study(app, pilot)
        await pilot.press("space")
        await pilot.pause()
        with_description_focus = app.export_screenshot()
        await pilot.click("#code", offset=(10, 3))
        await pilot.pause()
        assert screen.focused is screen.query_one("#code")
        assert app.export_screenshot() == with_description_focus


async def test_proximo_card_volta_o_foco_para_o_codigo(svc: Services) -> None:
    svc.importer.import_batch({"deck": "Longo", "cards": [{"code": "x = 1", "description": "um"}]})
    app = CodeCardsApp(svc)
    async with app.run_test(size=(80, 24)) as pilot:
        screen = await open_study(app, pilot)
        await pilot.press("space", "a")
        await pilot.pause()
        assert screen.revealed is False
        assert screen.focused is screen.query_one("#code")


async def test_tecla_de_rolar_para_baixo_configurada(svc: Services) -> None:
    svc.settings.set_key("partial", "f")
    svc.settings.set_key("scroll_down", "s")
    app = CodeCardsApp(svc)
    async with app.run_test(size=(80, 24)) as pilot:
        screen = await open_study(app, pilot)
        await pilot.press("space", "s", "s")
        assert screen.query_one("#description-box").scroll_y == 2
        assert svc.store.read_events(screen.deck_id) == []
