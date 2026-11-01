from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import Button, Input, Switch

from code_cards.models import Settings
from code_cards.services.container import Services
from code_cards.tui.app import CodeCardsApp
from code_cards.tui.screens.main import OPEN_SETTINGS, MainScreen
from code_cards.tui.screens.settings import SettingsScreen
from code_cards.tui.screens.study import StudyScreen
from code_cards.tui.widgets.confirm_modal import ConfirmModal
from code_cards.tui.widgets.deck_table import DeckTable
from code_cards.tui.widgets.help_bar import HelpBar
from tests.factories import make_services


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
        assert screen.capturing == "great"
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
