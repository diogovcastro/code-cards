from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from code_cards.errors import DeckFullError, DeckNotFoundError, ValidationError
from code_cards.services.cards import CardDraft
from tests.factories import Services, make_services


@pytest.fixture
def svc(tmp_path: Path) -> Services:
    return make_services(tmp_path)


def card(i: int = 0, **kw: Any) -> dict[str, Any]:
    return {"code": f"x = {i}", "description": f"atribui {i}", **kw}


def fill(svc: Services, deck_name: str, n: int) -> None:
    deck = svc.decks.get(deck_name)
    with svc.store.deck_lock(deck.id):
        loaded = svc.store.load_deck(deck.id)
        svc.cards.append_to_deck(loaded, [CardDraft(f"y = {i}", "d") for i in range(n)])
        svc.store.save_deck(loaded)


def test_cria_deck_e_cards(svc: Services) -> None:
    result = svc.importer.import_batch(
        {
            "deck": "Python async",
            "create_deck_if_missing": True,
            "cards": [card(0, tags=["asyncio"]), card(1, language="python")],
        }
    )
    assert result.deck_created
    deck = svc.decks.get("python async")
    assert deck.id == result.deck_id
    assert [c.id for c in deck.cards] == result.card_ids
    assert deck.cards[0].tags == ["asyncio"]


def test_deck_inexistente_sem_flag(svc: Services) -> None:
    with pytest.raises(DeckNotFoundError, match="create_deck_if_missing"):
        svc.importer.import_batch({"deck": "Nada", "cards": [card()]})
    assert svc.decks.list() == []


def test_tudo_ou_nada_por_falta_de_vagas(svc: Services) -> None:
    svc.decks.create("Python")
    fill(svc, "Python", 95)
    with pytest.raises(DeckFullError) as exc:
        svc.importer.import_batch({"deck": "Python", "cards": [card(i) for i in range(10)]})
    assert exc.value.details["available"] == 5
    assert "5 vaga" in exc.value.message
    assert len(svc.decks.get("Python").cards) == 95


def test_tudo_ou_nada_por_card_invalido(svc: Services) -> None:
    svc.decks.create("Python")
    with pytest.raises(ValidationError) as exc:
        svc.importer.import_batch(
            {"deck": "Python", "cards": [card(0), {"code": "x", "description": ""}]}
        )
    assert exc.value.details["errors"][0]["path"] == "$.cards[1].description"
    assert svc.decks.get("Python").cards == []


def test_lista_todos_os_erros(svc: Services) -> None:
    with pytest.raises(ValidationError) as exc:
        svc.importer.import_batch(
            {"deck": "", "extra": 1, "cards": [{"code": "x", "descripton": "typo"}, 3]}
        )
    paths = [e["path"] for e in exc.value.details["errors"]]
    assert paths == [
        "$.extra",
        "$.deck",
        "$.cards[0].descripton",
        "$.cards[0].description",
        "$.cards[1]",
    ]


def test_avisa_linguagem_desconhecida(svc: Services) -> None:
    result = svc.importer.import_batch(
        {"deck": "Go", "create_deck_if_missing": True, "cards": [card(language="go")]}
    )
    assert result.warnings[0]["code"] == "UNKNOWN_LANGUAGE"
    assert result.warnings[0]["details"]["index"] == 0


@pytest.mark.parametrize("data", [[], "x", {"deck": "a", "cards": []}, {"deck": "a"}])
def test_estrutura_invalida(svc: Services, data: Any) -> None:
    with pytest.raises(ValidationError):
        svc.importer.import_batch(data)


def test_mais_de_100_cards(svc: Services) -> None:
    with pytest.raises(ValidationError):
        svc.importer.import_batch(
            {"deck": "a", "create_deck_if_missing": True, "cards": [card(i) for i in range(101)]}
        )
