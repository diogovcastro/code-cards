from __future__ import annotations

from pathlib import Path

import pytest

from code_cards.services.container import Services
from code_cards.tui.app import CodeCardsApp
from code_cards.tui.screens.main import MainScreen
from code_cards.tui.widgets.deck_table import DeckTable
from tests.factories import make_services


@pytest.fixture
def svc(tmp_path: Path) -> Services:
    return make_services(tmp_path)


def seed(svc: Services, n: int = 3, name: str = "Python async") -> str:
    result = svc.importer.import_batch(
        {
            "deck": name,
            "create_deck_if_missing": True,
            "cards": [{"code": f"x = {i}", "description": f"atribui {i}"} for i in range(n)],
        }
    )
    return result.deck_id


async def test_painel_sem_decks_mostra_boas_vindas(svc: Services) -> None:
    app = CodeCardsApp(svc)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, MainScreen)
        assert app.screen.query_one("#welcome").display is True


async def test_painel_lista_decks_com_contagens(svc: Services) -> None:
    seed(svc, 3)
    app = CodeCardsApp(svc)
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.screen.query_one(DeckTable)
        assert table.option_count >= 1
        assert table.get_option_at_index(0).disabled  # cabeçalho
        row = str(table.get_option_at_index(1).prompt)
        assert "Python async" in row
        assert "3/100" in row
        assert app.screen.query_one("#welcome").display is False
