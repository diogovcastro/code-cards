from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import Input, Select, TextArea

from code_cards.services.container import Services
from code_cards.tui.app import CodeCardsApp
from code_cards.tui.screens.card_editor import CardEditorScreen, parse_tags
from code_cards.tui.screens.main import ADD_CARD, CREATE_DECK, MainScreen
from code_cards.tui.widgets.confirm_modal import ConfirmModal, TextPromptModal
from code_cards.tui.widgets.deck_table import DeckTable
from tests.factories import make_services


@pytest.fixture
def svc(tmp_path: Path) -> Services:
    return make_services(tmp_path)


async def open_editor(app: CodeCardsApp, pilot) -> CardEditorScreen:  # type: ignore[no-untyped-def]
    app.screen.query_one(DeckTable).highlight_id(ADD_CARD)
    await pilot.press("enter")
    await pilot.pause()
    assert isinstance(app.screen, CardEditorScreen)
    return app.screen


def test_parse_tags() -> None:
    assert parse_tags(" a, b ,, c ") == ["a", "b", "c"]


async def test_criar_deck_e_card_pelo_painel(svc: Services) -> None:
    app = CodeCardsApp(svc)
    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause()
        table = app.screen.query_one(DeckTable)
        assert table.highlighted_option is not None
        assert table.highlighted_option.id == CREATE_DECK

        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, TextPromptModal)
        app.screen.query_one(Input).value = "Python async"
        await pilot.press("enter")
        await pilot.pause()
        [deck] = svc.decks.list()
        assert deck.name == "Python async"
        assert table.highlighted_deck_id == deck.id

        editor = await open_editor(app, pilot)
        assert editor.query_one("#deck-select", Select).value == deck.id
        editor.query_one("#code-editor", TextArea).load_text("print('oi')")
        editor.query_one("#description-editor", TextArea).load_text("Imprime oi.")
        editor.query_one("#tags-input", Input).value = "básico, io"
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert isinstance(app.screen, MainScreen)
        [card] = svc.decks.get(deck.id).cards
        assert card.code == "print('oi')"
        assert card.description == "Imprime oi."
        assert card.tags == ["básico", "io"]
        assert "1/100" in str(table.get_option_at_index(1).prompt)


async def test_nome_de_deck_duplicado_mostra_erro(svc: Services) -> None:
    svc.decks.create("Python")
    app = CodeCardsApp(svc)
    async with app.run_test() as pilot:
        app.screen.query_one(DeckTable).highlight_id(CREATE_DECK)
        await pilot.press("enter")
        await pilot.pause()
        app.screen.query_one(Input).value = "python"
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, MainScreen)
    assert len(svc.decks.list()) == 1


async def test_adicionar_card_sem_deck_avisa(svc: Services) -> None:
    app = CodeCardsApp(svc)
    async with app.run_test() as pilot:
        app.screen.query_one(DeckTable).highlight_id(ADD_CARD)
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, MainScreen)


async def test_cancelar_com_alteracao_pede_confirmacao(svc: Services) -> None:
    deck = svc.decks.create("Python")
    app = CodeCardsApp(svc)
    async with app.run_test() as pilot:
        await open_editor(app, pilot)
        # Sem alteração, Esc sai direto.
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, MainScreen)

        editor = await open_editor(app, pilot)
        editor.query_one("#code-editor", TextArea).load_text("y = 2")
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmModal)
        await pilot.press("escape")  # não descarta
        await pilot.pause()
        assert app.screen is editor
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("s")  # descarta
        await pilot.pause()
        assert isinstance(app.screen, MainScreen)
    assert svc.decks.get(deck.id).cards == []


async def test_erro_de_validacao_mantem_o_editor(svc: Services) -> None:
    svc.decks.create("Python")
    app = CodeCardsApp(svc)
    async with app.run_test() as pilot:
        editor = await open_editor(app, pilot)
        editor.query_one("#code-editor", TextArea).load_text("z = 3")
        await pilot.press("ctrl+s")  # sem descrição
        await pilot.pause()
        assert app.screen is editor


async def test_trocar_linguagem_atualiza_highlight(svc: Services) -> None:
    svc.decks.create("Python")
    app = CodeCardsApp(svc)
    async with app.run_test() as pilot:
        editor = await open_editor(app, pilot)
        code = editor.query_one("#code-editor", TextArea)
        assert code.language == "python"
        editor.query_one("#language-select", Select).value = "text"
        await pilot.pause()
        assert code.language is None


async def test_secoes_do_editor_alinhadas_e_espacadas(svc: Services) -> None:
    svc.decks.create("Python")
    app = CodeCardsApp(svc)
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        screen = await open_editor(app, pilot)
        deck = screen.query_one("#deck-select").region
        language = screen.query_one("#language-select").region
        sections = [screen.query_one(q).region for q in ("#code-editor", "#description-editor")]
        sections.append(screen.query_one("#tags-input").region)
        # Mesmas bordas laterais: os dois seletores juntos ocupam a largura das seções.
        for region in sections:
            assert region.x == deck.x
            assert region.right == language.right
        # Uma linha de espaço entre seções consecutivas.
        tops = [language.y, *(r.y for r in sections)]
        bottoms = [language.bottom, *(r.bottom for r in sections)]
        assert all(top - bottom == 1 for bottom, top in zip(bottoms, tops[1:], strict=False))
