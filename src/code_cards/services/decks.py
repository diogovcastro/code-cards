"""Serviço de decks: criar, listar, renomear e apagar.

O nome do deck é único sem diferenciar maiúsculas. Onde se pede um deck,
aceita-se o id ou o nome.
"""

from __future__ import annotations

from code_cards.clock import Clock, SystemClock
from code_cards.errors import DeckExistsError, DeckNotFoundError, ValidationError
from code_cards.models import Deck, new_deck_id
from code_cards.storage import JsonStore

MAX_DECK_NAME = 80


def clean_deck_name(name: str) -> str:
    cleaned = " ".join(name.split())
    if not cleaned:
        raise ValidationError("O nome do deck não pode ser vazio.", {"field": "name"})
    if len(cleaned) > MAX_DECK_NAME:
        raise ValidationError(
            f"O nome do deck pode ter no máximo {MAX_DECK_NAME} caracteres.",
            {"field": "name", "length": len(cleaned)},
        )
    return cleaned


class DeckService:
    def __init__(self, store: JsonStore, clock: Clock | None = None) -> None:
        self.store = store
        self.clock: Clock = clock or SystemClock()

    def list(self) -> list[Deck]:
        return self.store.load_all_decks()

    def find(self, ref: str) -> Deck | None:
        """Procura por id exato e depois por nome (sem diferenciar maiúsculas)."""
        ref = ref.strip()
        if not ref:
            return None
        if self.store.deck_exists(ref):
            return self.store.load_deck(ref)
        wanted = " ".join(ref.split()).casefold()
        for deck in self.store.load_all_decks():
            if deck.name.casefold() == wanted:
                return deck
        return None

    def get(self, ref: str) -> Deck:
        deck = self.find(ref)
        if deck is None:
            raise DeckNotFoundError(f"Deck '{ref}' não encontrado.", {"deck": ref})
        return deck

    def _ensure_name_free(self, name: str, ignore_id: str | None = None) -> None:
        for deck in self.store.load_all_decks():
            if deck.id != ignore_id and deck.name.casefold() == name.casefold():
                raise DeckExistsError(
                    f"Já existe um deck chamado '{deck.name}'.",
                    {"deck_id": deck.id, "name": deck.name},
                )

    def _new_unique_id(self) -> str:
        while True:
            deck_id = new_deck_id()
            if not self.store.deck_exists(deck_id):
                return deck_id

    def build_new(self, name: str) -> Deck:
        """Monta um deck novo (sem gravar). Use dentro de ``global_lock``."""
        name = clean_deck_name(name)
        self._ensure_name_free(name)
        return Deck(id=self._new_unique_id(), name=name, created_at=self.clock.now())

    def create(self, name: str) -> Deck:
        with self.store.global_lock():
            deck = self.build_new(name)
            self.store.save_deck(deck)
        return deck

    def rename(self, ref: str, new_name: str) -> Deck:
        new_name = clean_deck_name(new_name)
        with self.store.global_lock():
            deck_id = self.get(ref).id
            self._ensure_name_free(new_name, ignore_id=deck_id)
            with self.store.deck_lock(deck_id):
                deck = self.store.load_deck(deck_id)
                deck.name = new_name
                self.store.save_deck(deck)
        return deck

    def delete(self, ref: str) -> Deck:
        with self.store.global_lock():
            deck = self.get(ref)
            with self.store.deck_lock(deck.id):
                self.store.delete_deck(deck.id)
        return deck
