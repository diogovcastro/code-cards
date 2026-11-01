from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import Button, Input, Switch

from code_cards.models import Settings
from code_cards.services.container import Services
from code_cards.tui import screens
from code_cards.tui.app import CodeCardsApp
from code_cards.tui.screens.main import OPEN_SETTINGS, MainScreen
from code_cards.tui.screens.settings import SettingsScreen
from code_cards.tui.screens.study import StudyScreen
from code_cards.tui.widgets.confirm_modal import ConfirmModal
from code_cards.tui.widgets.deck_table import DeckTable
from code_cards.tui.widgets.help_bar import HelpBar
from tests.factories import make_services
from tests.tui_helpers import mouse_click


@pytest.fixture
def svc(tmp_path: Path) -> Services:
    return make_services(tmp_path)


async def open_settings(app: CodeCardsApp, pilot) -> SettingsScreen:  # type: ignore[no-untyped-def]
    await pilot.pause()
    app.screen.query_one(DeckTable).highlight_id(OPEN_SETTINGS)
    await pilot.press("enter")
    await pilot.pause()
    assert isinstance(app.screen, SettingsScreen)
    return app.screen


async def test_trocar_a_por_j_e_estudar_com_j(svc: Services) -> None:
    deck_id = svc.importer.import_batch(
        {
            "deck": "Python",
            "create_deck_if_missing": True,
            "cards": [
                {"code": "x = 1", "description": "um"},
                {"code": "y = 2", "description": "2"},
            ],
        }
    ).deck_id
    app = CodeCardsApp(svc)
    async with app.run_test(size=(100, 40)) as pilot:
        screen = await open_settings(app, pilot)
        assert str(screen.query_one("#key-great", Button).label) == "A"
        # Enter no botão de Ótimo e depois a tecla nova.
        await pilot.press("enter")
        assert screen.capturing == ("key", "great")
        await pilot.press("j")
        await pilot.pause()
        assert screen.capturing is None
        assert str(screen.query_one("#key-great", Button).label) == "J"
        assert svc.settings.get().keys["great"] == "j"

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, MainScreen)
        app.screen.query_one(DeckTable).highlight_id(f"deck:{deck_id}")
        await pilot.press("enter")
        await pilot.pause()
        study = app.screen
        assert isinstance(study, StudyScreen)
        await pilot.press("space")
        assert "J Ótimo" in str(study.query_one(HelpBar).render())
        await pilot.press("a")  # A não faz mais nada
        await pilot.pause()
        assert svc.store.read_events(deck_id) == []
        await pilot.press("j")
        await pilot.pause()
    assert [e["grade"] for e in svc.store.read_events(deck_id)] == ["great"]


async def test_tecla_duplicada_ou_reservada_e_recusada(svc: Services) -> None:
    app = CodeCardsApp(svc)
    async with app.run_test(size=(100, 40)) as pilot:
        screen = await open_settings(app, pilot)
        await pilot.press("enter", "s")  # S já é Parcial
        await pilot.pause()
        await pilot.press("enter", "q")  # reservada
        await pilot.pause()
        assert str(screen.query_one("#key-great", Button).label) == "A"
        # Esc durante a captura só cancela a captura.
        await pilot.press("enter", "escape")
        await pilot.pause()
        assert app.screen is screen
        assert screen.capturing is None
    assert svc.settings.get().keys["great"] == "a"


async def test_campos_numericos_e_ajuda(svc: Services) -> None:
    app = CodeCardsApp(svc)
    async with app.run_test(size=(100, 40)) as pilot:
        screen = await open_settings(app, pilot)
        screen.query_one("#input-new_cards_per_day", Input).value = "20"
        screen.query_one("#input-desired_retention", Input).value = "0,85"
        screen.query_one("#input-reviews_per_day", Input).value = "abc"  # inválido: ignora
        screen.query_one("#input-day_starts_at_hour", Input).value = "30"  # inválido: ignora
        screen.query_one("#show-help", Switch).value = False
        await pilot.pause()
        assert screen.query_one(HelpBar).display is False
    settings = svc.settings.get()
    assert settings.new_cards_per_day == 20
    assert settings.desired_retention == 0.85
    assert settings.reviews_per_day == 200
    assert settings.day_starts_at_hour == 4
    assert settings.show_help is False


async def test_restaurar_padroes(svc: Services) -> None:
    svc.settings.update(new_cards_per_day=5, show_help=False)
    svc.settings.set_key("great", "j")
    app = CodeCardsApp(svc)
    async with app.run_test(size=(100, 40)) as pilot:
        screen = await open_settings(app, pilot)
        screen.query_one("#reset", Button).press()
        await pilot.pause()
        assert isinstance(app.screen, ConfirmModal)
        await pilot.press("s")
        await pilot.pause()
        assert screen.query_one("#input-new_cards_per_day", Input).value == "50"
        assert str(screen.query_one("#key-great", Button).label) == "A"
    assert svc.settings.get() == Settings()


async def test_capturar_botao_lateral_e_usar_para_voltar(svc: Services) -> None:
    deck_id = svc.importer.import_batch(
        {
            "deck": "Python",
            "create_deck_if_missing": True,
            "cards": [{"code": "x", "description": "d"}],
        }
    ).deck_id
    app = CodeCardsApp(svc)
    async with app.run_test(size=(100, 40)) as pilot:
        screen = await open_settings(app, pilot)
        screen.query_one("#mouse-back", Button).focus()
        await pilot.press("enter")
        assert screen.capturing == ("mouse", "back")
        # Clique esquerdo durante a captura é recusado e a captura continua.
        await mouse_click(app, pilot, 1)
        assert screen.capturing == ("mouse", "back")
        await mouse_click(app, pilot, 8)
        assert screen.capturing is None
        assert str(screen.query_one("#mouse-back", Button).label) == "Lateral (voltar)"
        assert svc.settings.get().mouse["back"] == "button8"
        # Fora da captura, o mesmo botão volta para o painel.
        await mouse_click(app, pilot, 8)
        assert isinstance(app.screen, MainScreen)
        app.screen.query_one(DeckTable).highlight_id(f"deck:{deck_id}")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, StudyScreen)
        await mouse_click(app, pilot, 8)
        assert isinstance(app.screen, MainScreen)


async def test_remover_botao_com_del(svc: Services) -> None:
    svc.settings.set_mouse_button("undo", "middle")
    app = CodeCardsApp(svc)
    async with app.run_test(size=(100, 40)) as pilot:
        screen = await open_settings(app, pilot)
        assert str(screen.query_one("#mouse-undo", Button).label) == "Botão do meio"
        screen.query_one("#mouse-undo", Button).focus()
        await pilot.press("enter", "delete")
        await pilot.pause()
        assert str(screen.query_one("#mouse-undo", Button).label) == "—"
    assert svc.settings.get().mouse["undo"] is None


async def test_botao_repetido_e_recusado_na_tela(svc: Services) -> None:
    svc.settings.set_mouse_button("undo", "right")
    app = CodeCardsApp(svc)
    async with app.run_test(size=(100, 40)) as pilot:
        screen = await open_settings(app, pilot)
        screen.query_one("#mouse-great", Button).focus()
        await pilot.press("enter")
        await mouse_click(app, pilot, 3)
        assert screen.capturing is None
    assert svc.settings.get().mouse["great"] is None


async def test_captura_de_mouse_expira(svc: Services, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(screens.settings, "MOUSE_CAPTURE_TIMEOUT", 0.5)
    app = CodeCardsApp(svc)
    async with app.run_test(size=(100, 40)) as pilot:
        screen = await open_settings(app, pilot)
        screen.query_one("#mouse-back", Button).focus()
        await pilot.press("enter")
        assert screen.capturing == ("mouse", "back")
        await pilot.pause(1.0)
        assert screen.capturing is None


async def test_del_remove_tecla_de_rolagem_mas_nao_de_nota(svc: Services) -> None:
    app = CodeCardsApp(svc)
    async with app.run_test(size=(100, 40)) as pilot:
        screen = await open_settings(app, pilot)
        screen.query_one("#key-scroll_up", Button).focus()
        await pilot.press("enter", "delete")
        await pilot.pause()
        assert str(screen.query_one("#key-scroll_up", Button).label) == "—"
        screen.query_one("#key-great", Button).focus()
        await pilot.press("enter", "delete")
        await pilot.pause()
        assert str(screen.query_one("#key-great", Button).label) == "A"
    keys = svc.settings.get().keys
    assert keys["scroll_up"] is None
    assert keys["great"] == "a"


async def test_trocar_tecla_de_voltar_na_tela(svc: Services) -> None:
    app = CodeCardsApp(svc)
    async with app.run_test(size=(100, 40)) as pilot:
        screen = await open_settings(app, pilot)
        screen.query_one("#key-back", Button).focus()
        await pilot.press("enter", "b")
        await pilot.pause()
        assert str(screen.query_one("#key-back", Button).label) == "B"
        await pilot.press("b")
        await pilot.pause()
        assert isinstance(app.screen, MainScreen)
