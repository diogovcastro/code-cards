from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from code_cards.clock import FixedClock
from code_cards.errors import DeckExistsError, DeckNotFoundError, ValidationError
from code_cards.paths import DataPaths
from code_cards.services.decks import DeckService
from code_cards.storage import JsonStore

T0 = datetime(2026, 11, 1, 13, 0, tzinfo=UTC)


@pytest.fixture
def decks(tmp_path: Path) -> DeckService:
    return DeckService(JsonStore(DataPaths(tmp_path)), FixedClock(T0))


def test_cria_e_lista_em_ordem_alfabetica(decks: DeckService) -> None:
    b = decks.create("django ORM")
    a = decks.create("  Python   async ")
    assert a.name == "Python async"
    assert len(a.id) == 6
    assert a.created_at == T0
    assert [d.id for d in decks.list()] == [b.id, a.id]


def test_nome_unico_sem_diferenciar_maiusculas(decks: DeckService) -> None:
    decks.create("Python async")
    with pytest.raises(DeckExistsError):
        decks.create("PYTHON ASYNC")


@pytest.mark.parametrize("name", ["", "   ", "x" * 81])
def test_nome_invalido(decks: DeckService, name: str) -> None:
    with pytest.raises(ValidationError):
        decks.create(name)


def test_busca_por_id_ou_nome(decks: DeckService) -> None:
    deck = decks.create("Python async")
    assert decks.get(deck.id).id == deck.id
    assert decks.get("python ASYNC").id == deck.id
    with pytest.raises(DeckNotFoundError):
        decks.get("Rust")


def test_renomear(decks: DeckService) -> None:
    deck = decks.create("Python")
    decks.create("Rust")
    assert decks.rename("python", "Python 3").name == "Python 3"
    assert decks.get(deck.id).name == "Python 3"
    # Pode mudar só maiúsculas do próprio nome.
    assert decks.rename(deck.id, "PYTHON 3").name == "PYTHON 3"
    with pytest.raises(DeckExistsError):
        decks.rename(deck.id, "rust")


def test_apagar(decks: DeckService) -> None:
    deck = decks.create("Python")
    assert decks.delete("Python").id == deck.id
    assert decks.list() == []
    with pytest.raises(DeckNotFoundError):
        decks.delete(deck.id)
