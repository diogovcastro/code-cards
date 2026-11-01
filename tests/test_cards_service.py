from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from code_cards.clock import FixedClock
from code_cards.errors import CardNotFoundError, DeckFullError, ValidationError
from code_cards.paths import DataPaths
from code_cards.services.cards import CardDraft, CardService, slice_lines
from code_cards.services.decks import DeckService
from code_cards.storage import JsonStore

T0 = datetime(2026, 11, 1, 13, 0, tzinfo=UTC)


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(T0)


@pytest.fixture
def decks(tmp_path: Path, clock: FixedClock) -> DeckService:
    return DeckService(JsonStore(DataPaths(tmp_path)), clock)


@pytest.fixture
def cards(decks: DeckService, clock: FixedClock) -> CardService:
    return CardService(decks.store, decks, clock)


def draft(i: int = 0, **kw: object) -> CardDraft:
    data: dict[str, object] = {"code": f"x = {i}\n", "description": f" atribui {i} "}
    data.update(kw)
    return CardDraft(**data)  # type: ignore[arg-type]


def test_adiciona_card(decks: DeckService, cards: CardService) -> None:
    deck = decks.create("Python")
    _, card, warnings = cards.add("python", draft(tags=["a", " a ", "b"]))
    assert warnings == []
    assert len(card.id) == 8
    assert card.code == "x = 0"
    assert card.description == "atribui 0"
    assert card.language == "python"
    assert card.tags == ["a", "b"]
    assert card.is_new
    assert decks.get(deck.id).cards == [card]


def test_linguagem_desconhecida_gera_aviso(decks: DeckService, cards: CardService) -> None:
    decks.create("Rust")
    _, card, warnings = cards.add("Rust", draft(language="Rust"))
    assert card.language == "rust"
    assert [w["code"] for w in warnings] == ["UNKNOWN_LANGUAGE"]


@pytest.mark.parametrize(
    "kw", [{"code": "  \n "}, {"description": ""}, {"code": "x" * 20_001}, {"tags": [1]}]
)
def test_validacao(decks: DeckService, cards: CardService, kw: dict) -> None:
    decks.create("Python")
    with pytest.raises(ValidationError):
        cards.add("Python", draft(**kw))
    assert decks.get("Python").cards == []


def test_limite_de_100_cards(decks: DeckService, cards: CardService) -> None:
    deck = decks.create("Python")
    with cards.store.deck_lock(deck.id):
        loaded = cards.store.load_deck(deck.id)
        cards.append_to_deck(loaded, [draft(i) for i in range(100)])
        cards.store.save_deck(loaded)
    with pytest.raises(DeckFullError) as exc:
        cards.add("Python", draft())
    assert exc.value.details["available"] == 0
    assert "100 cards" in exc.value.message


def test_editar_campos(decks: DeckService, cards: CardService, clock: FixedClock) -> None:
    decks.create("Python")
    _, card, _ = cards.add("Python", draft())
    clock.advance(minutes=5)
    _, edited, _ = cards.edit(card.id, description="nova", tags=["t"])
    assert edited.description == "nova"
    assert edited.tags == ["t"]
    assert edited.code == "x = 0"
    assert edited.updated_at > edited.created_at
    assert edited.fsrs == card.fsrs


def test_mover_card_entre_decks(decks: DeckService, cards: CardService) -> None:
    a = decks.create("A")
    b = decks.create("B")
    _, card, _ = cards.add("A", draft())
    target, moved, _ = cards.edit(card.id, deck_ref="b")
    assert target.id == b.id
    assert decks.get(a.id).cards == []
    assert [c.id for c in decks.get(b.id).cards] == [moved.id]


def test_mover_para_deck_cheio(decks: DeckService, cards: CardService) -> None:
    decks.create("A")
    full = decks.create("Cheio")
    with cards.store.deck_lock(full.id):
        loaded = cards.store.load_deck(full.id)
        cards.append_to_deck(loaded, [draft(i) for i in range(100)])
        cards.store.save_deck(loaded)
    _, card, _ = cards.add("A", draft())
    with pytest.raises(DeckFullError):
        cards.edit(card.id, deck_ref="Cheio")
    assert cards.find(card.id)[0].name == "A"


def test_apagar_e_buscar(decks: DeckService, cards: CardService) -> None:
    decks.create("Python")
    _, card, _ = cards.add("Python", draft())
    assert cards.find(card.id)[1].id == card.id
    cards.delete(card.id)
    with pytest.raises(CardNotFoundError):
        cards.find(card.id)
    with pytest.raises(CardNotFoundError):
        cards.delete(card.id)


def test_slice_lines() -> None:
    text = "a\n    def f():\n        return 1\nb"
    assert slice_lines(text, "2-3") == "def f():\n    return 1"
    assert slice_lines(text, "4") == "b"
    assert slice_lines(text, "3-") == "        return 1\nb"
    for bad in ["x", "0-2", "3-2", "9-10"]:
        with pytest.raises(ValidationError):
            slice_lines(text, bad)
