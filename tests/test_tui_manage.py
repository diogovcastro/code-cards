from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import DataTable, Input, Select, TextArea

from code_cards.services.container import Services
from code_cards.tui.app import CodeCardsApp
from code_cards.tui.screens.card_editor import CardEditorScreen
from code_cards.tui.screens.deck_manager import DeckManagerScreen
from code_cards.tui.screens.main import ADD_CARD, CREATE_DECK, MainScreen
from code_cards.tui.screens.study import StudyScreen
from code_cards.tui.widgets.confirm_modal import ConfirmModal, TextPromptModal
from code_cards.tui.widgets.deck_table import DeckTable
from tests.factories import make_services


@pytest.fixture
def svc(tmp_path: Path) -> Services:
    return make_services(tmp_path)


def seed(svc: Services, n: int, name: str = "Python") -> str:
    return svc.importer.import_batch(
        {
            "deck": name,
            "create_deck_if_missing": True,
            "cards": [{"code": f"x = {i}", "description": f"atribui {i}"} for i in range(n)],
        }
    ).deck_id


async def test_ciclo_completo_sem_cli(svc: Services) -> None:
    app = CodeCardsApp(svc)
    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause()
        main = app.screen
        assert isinstance(main, MainScreen)
        table = main.query_one(DeckTable)
        # Sem decks, o cursor começa em "Criar deck".
        assert table.highlighted_option is not None
        assert table.highlighted_option.id == CREATE_DECK

        # Criar deck.
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, TextPromptModal)
        app.screen.query_one(Input).value = "Python async"
        await pilot.press("enter")
        await pilot.pause()
        [deck] = svc.decks.list()
        assert deck.name == "Python async"
        assert table.highlighted_deck_id == deck.id

        # Adicionar card pelo menu.
        table.highlight_id(ADD_CARD)
        await pilot.press("enter")
        await pilot.pause()
        editor = app.screen
        assert isinstance(editor, CardEditorScreen)
        assert editor.query_one("#deck-select", Select).value == deck.id
        editor.query_one("#code-editor", TextArea).load_text("print('oi')")
        editor.query_one("#description-editor", TextArea).load_text("Imprime oi.")
        editor.query_one("#tags-input", Input).value = "básico, io"
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert isinstance(app.screen, MainScreen)
        [card] = svc.decks.get(deck.id).cards
        assert card.code == "print('oi')"
        assert card.tags == ["básico", "io"]
        assert "1/100" in str(table.get_option_at_index(1).prompt)

        # Gerenciar → editar.
        table.highlight_id(f"deck:{deck.id}")
        await pilot.press("g")
        await pilot.pause()
        manager = app.screen
        assert isinstance(manager, DeckManagerScreen)
        assert manager.query_one(DataTable).row_count == 1
        await pilot.press("enter")
        await pilot.pause()
        editor = app.screen
        assert isinstance(editor, CardEditorScreen)
        assert editor.query_one("#code-editor", TextArea).text == "print('oi')"
        editor.query_one("#description-editor", TextArea).load_text("Mostra oi na tela.")
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert app.screen is manager
        assert svc.decks.get(deck.id).cards[0].description == "Mostra oi na tela."

        # Renomear deck.
        await pilot.press("r")
        await pilot.pause()
        assert isinstance(app.screen, TextPromptModal)
        app.screen.query_one(Input).value = "Asyncio"
        await pilot.press("enter")
        await pilot.pause()
        assert svc.decks.get(deck.id).name == "Asyncio"

        # Apagar card (com confirmação).
        await pilot.press("delete")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmModal)
        await pilot.press("s")
        await pilot.pause()
        assert svc.decks.get(deck.id).cards == []

        # Apagar deck digitando o nome.
        await pilot.press("x")
        await pilot.pause()
        assert isinstance(app.screen, TextPromptModal)
        app.screen.query_one(Input).value = "asyncio"
        await pilot.press("enter")
        await pilot.pause()
        assert svc.decks.list() == []
        assert isinstance(app.screen, MainScreen)


async def test_apagar_deck_com_nome_errado_nao_apaga(svc: Services) -> None:
    deck_id = seed(svc, 1)
    app = CodeCardsApp(svc)
    async with app.run_test() as pilot:
        await pilot.press("g")
        await pilot.pause()
        await pilot.press("x")
        await pilot.pause()
        assert isinstance(app.screen, TextPromptModal)
        app.screen.query_one(Input).value = "outro"
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, DeckManagerScreen)
    assert svc.decks.get(deck_id)


async def test_novo_card_bloqueado_com_100(svc: Services) -> None:
    seed(svc, 100)
    app = CodeCardsApp(svc)
    async with app.run_test() as pilot:
        await pilot.press("g")
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        assert isinstance(app.screen, DeckManagerScreen)


async def test_estudar_deck_criado_pela_tui(svc: Services) -> None:
    seed(svc, 1)
    app = CodeCardsApp(svc)
    async with app.run_test() as pilot:
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, StudyScreen)
