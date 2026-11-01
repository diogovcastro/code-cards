from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import TextArea

from code_cards.errors import ValidationError
from code_cards.services.container import Services
from code_cards.tui.app import CodeCardsApp
from code_cards.tui.screens.card_editor import CardEditorScreen
from code_cards.tui.screens.deck_manager import DeckManagerScreen
from code_cards.tui.screens.main import MainScreen
from code_cards.tui.screens.study import StudyScreen
from code_cards.tui.widgets.confirm_modal import ConfirmModal
from code_cards.tui.widgets.help_bar import HelpBar
from tests.factories import make_services
from tests.tui_helpers import mouse_click

BACK_BUTTON = 8


@pytest.fixture
def svc(tmp_path: Path) -> Services:
    svc = make_services(tmp_path)
    svc.importer.import_batch(
        {
            "deck": "Python",
            "create_deck_if_missing": True,
            "cards": [{"code": f"x = {i}", "description": f"atribui {i}"} for i in range(3)],
        }
    )
    return svc


def deck_id(svc: Services) -> str:
    return svc.decks.get("Python").id


async def test_botao_lateral_volta_do_estudo(svc: Services) -> None:
    svc.settings.set_mouse_button("back", "button8")
    app = CodeCardsApp(svc)
    async with app.run_test() as pilot:
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, StudyScreen)
        await mouse_click(app, pilot, BACK_BUTTON)
        assert isinstance(app.screen, MainScreen)


async def test_sem_configuracao_o_botao_lateral_nao_faz_nada(svc: Services) -> None:
    app = CodeCardsApp(svc)
    async with app.run_test() as pilot:
        await pilot.press("enter")
        await pilot.pause()
        await mouse_click(app, pilot, BACK_BUTTON)
        assert isinstance(app.screen, StudyScreen)


async def test_notas_e_revelar_pelo_mouse(svc: Services) -> None:
    svc.settings.set_mouse_button("reveal", "right")
    svc.settings.set_mouse_button("great", "middle")
    app = CodeCardsApp(svc)
    async with app.run_test() as pilot:
        await pilot.press("enter")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, StudyScreen)
        await mouse_click(app, pilot, 2)  # nota antes de revelar: ignorada
        assert svc.store.read_events(deck_id(svc)) == []
        await mouse_click(app, pilot, 3)
        assert screen.revealed
        await mouse_click(app, pilot, 2)
        # A tecla continua funcionando junto com o mouse.
        await pilot.press("space", "a")
        await pilot.pause()
    assert [e["grade"] for e in svc.store.read_events(deck_id(svc))] == ["great", "great"]


async def test_botao_configurado_nao_chega_ao_widget(svc: Services) -> None:
    svc.settings.set_mouse_button("great", "middle")
    app = CodeCardsApp(svc)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Clique do meio sobre a lista de decks: consumido, não abre o deck.
        await mouse_click(app, pilot, 2, x=3, y=4)
        assert isinstance(app.screen, MainScreen)


async def test_tecla_de_voltar_trocada(svc: Services) -> None:
    svc.settings.set_key("back", "b")
    app = CodeCardsApp(svc)
    async with app.run_test() as pilot:
        await pilot.press("g")
        await pilot.pause()
        manager = app.screen
        assert isinstance(manager, DeckManagerScreen)
        assert "B voltar" in str(manager.query_one(HelpBar).render())
        await pilot.press("b")
        await pilot.pause()
        assert isinstance(app.screen, MainScreen)

        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, StudyScreen)
        await pilot.press("b")
        await pilot.pause()
        assert isinstance(app.screen, MainScreen)

        # O Esc continua voltando.
        await pilot.press("g")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, MainScreen)


async def test_tecla_de_voltar_nao_vale_no_editor(svc: Services) -> None:
    svc.settings.set_key("back", "b")
    app = CodeCardsApp(svc)
    async with app.run_test() as pilot:
        await pilot.press("g")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        editor = app.screen
        assert isinstance(editor, CardEditorScreen)
        await pilot.press("end", "b")
        await pilot.pause()
        assert app.screen is editor
        assert editor.query_one("#code-editor", TextArea).text.endswith("b")


async def test_mouse_de_voltar_no_editor_e_no_dialogo(svc: Services) -> None:
    svc.settings.set_mouse_button("back", "button8")
    app = CodeCardsApp(svc)
    async with app.run_test() as pilot:
        await pilot.press("g")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        editor = app.screen
        assert isinstance(editor, CardEditorScreen)
        editor.query_one("#code-editor", TextArea).load_text("mudou")
        # Com alteração, voltar pede confirmação; o mesmo botão cancela o diálogo.
        await mouse_click(app, pilot, BACK_BUTTON)
        assert isinstance(app.screen, ConfirmModal)
        await mouse_click(app, pilot, BACK_BUTTON)
        assert app.screen is editor
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert isinstance(app.screen, DeckManagerScreen)
        await mouse_click(app, pilot, BACK_BUTTON)
        assert isinstance(app.screen, MainScreen)


@pytest.mark.parametrize("key", ["r", "x", "n", "g", "delete", "enter"])
def test_voltar_nao_aceita_atalhos_do_app(svc: Services, key: str) -> None:
    with pytest.raises(ValidationError, match="atalho"):
        svc.settings.set_key("back", key)
