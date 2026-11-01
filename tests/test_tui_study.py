from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import Static, TextArea

from code_cards.services.container import Services
from code_cards.tui.app import CodeCardsApp
from code_cards.tui.screens.main import MainScreen
from code_cards.tui.screens.study import StudyScreen
from code_cards.tui.widgets.help_bar import HelpBar
from tests.factories import make_services


@pytest.fixture
def svc(tmp_path: Path) -> Services:
    return make_services(tmp_path)


def seed(svc: Services, n: int = 3, name: str = "Python async") -> str:
    result = svc.importer.import_batch(
        {
            "deck": name,
            "create_deck_if_missing": True,
            "cards": [
                {"code": f"async def f{i}():\n    await g({i})", "description": f"Chama g({i})."}
                for i in range(n)
            ],
        }
    )
    return result.deck_id


def help_text(app: CodeCardsApp) -> str:
    return str(app.screen.query_one(HelpBar).render())


async def test_estudar_um_card_com_a_s_d(svc: Services) -> None:
    deck_id = seed(svc, 3)
    app = CodeCardsApp(svc)
    async with app.run_test() as pilot:
        await pilot.press("enter")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, StudyScreen)
        assert screen.item is not None
        first_id = screen.item.card.id
        code = screen.query_one("#code", TextArea)
        assert code.read_only
        assert code.text.startswith("async def f0")
        assert screen.query_one("#description-box").display is False
        assert "mostrar descrição" in help_text(app)

        # Nota antes de revelar é ignorada.
        await pilot.press("a")
        assert screen.item.card.id == first_id

        await pilot.press("space")
        assert screen.revealed
        assert screen.query_one("#description-box").display is True
        assert "Chama g(0)." in str(screen.query_one("#description", Static).render())
        assert "Ótimo · 10min" in help_text(app)
        assert "Não lembro · 1min" in help_text(app)

        await pilot.press("a")
        await pilot.pause()
        assert screen.item.card.id != first_id
        await pilot.press("space", "s")
        await pilot.press("space", "d")
        await pilot.pause()

    deck = svc.store.load_deck(deck_id)
    assert all(not c.is_new for c in deck.cards)
    grades = [e["grade"] for e in svc.store.read_events(deck_id)]
    assert grades == ["great", "partial", "forgot"]


async def test_desfazer_volta_o_card(svc: Services) -> None:
    deck_id = seed(svc, 2)
    app = CodeCardsApp(svc)
    async with app.run_test() as pilot:
        await pilot.press("enter")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, StudyScreen)
        assert screen.item is not None
        first_id = screen.item.card.id
        await pilot.press("space", "a")
        assert screen.item.card.id != first_id
        await pilot.press("u")
        await pilot.pause()
        assert screen.item.card.id == first_id
        assert not screen.revealed
    assert svc.store.load_deck(deck_id).cards[0].is_new
    assert svc.store.read_events(deck_id)[-1]["type"] == "undo"


async def test_deck_concluido(svc: Services) -> None:
    seed(svc, 1)
    svc.settings.update(new_cards_per_day=1)
    app = CodeCardsApp(svc)
    async with app.run_test() as pilot:
        await pilot.press("enter")
        await pilot.pause()
        # Ótimo duas vezes: sai do aprendizado (a segunda via "aprender adiantado").
        await pilot.press("space", "a", "space", "a")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, StudyScreen)
        assert screen.item is None
        done = str(screen.query_one("#done", Static).render())
        assert "Deck concluído por hoje" in done
        assert "Próxima revisão" in done
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, MainScreen)


async def test_ajuda_desligada_esconde_barra_mas_teclas_funcionam(svc: Services) -> None:
    deck_id = seed(svc, 2)
    svc.settings.update(show_help=False)
    app = CodeCardsApp(svc)
    async with app.run_test() as pilot:
        await pilot.press("enter")
        await pilot.pause()
        assert app.screen.query_one(HelpBar).display is False
        await pilot.press("space", "a")
        await pilot.pause()
    assert len(svc.store.read_events(deck_id)) == 1
