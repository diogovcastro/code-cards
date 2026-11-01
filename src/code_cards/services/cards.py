"""Serviço de cards: adicionar, listar, editar, mover e apagar.

Regras que valem para CLI e TUI:

- cada card está em um único deck;
- um deck tem no máximo ``MAX_CARDS_PER_DECK`` cards;
- código e descrição são obrigatórios;
- linguagem desconhecida é aceita, com aviso (aparece como texto puro).
"""

from __future__ import annotations

import contextlib
import textwrap
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from code_cards import languages
from code_cards.clock import Clock, SystemClock
from code_cards.errors import CardNotFoundError, DeckFullError, ValidationError
from code_cards.models import MAX_CARDS_PER_DECK, Card, Deck, new_card_id
from code_cards.scheduling import SpacedScheduler
from code_cards.services.decks import DeckService
from code_cards.storage import JsonStore

MAX_CODE_CHARS = 20_000
MAX_DESCRIPTION_CHARS = 5_000
MAX_TAGS = 20
MAX_TAG_CHARS = 40

Warning = dict[str, Any]


@dataclass
class CardDraft:
    """Dados de um card ainda não validado (vindo da CLI, da TUI ou de um lote)."""

    code: str
    description: str
    language: str | None = None
    tags: list[str] = field(default_factory=list)


def _where(index: int | None) -> dict[str, Any]:
    return {} if index is None else {"index": index}


def _prefix(index: int | None) -> str:
    return "" if index is None else f"Card {index}: "


def clean_code(code: str, index: int | None = None) -> str:
    if not isinstance(code, str):
        raise ValidationError(f"{_prefix(index)}'code' deve ser texto.", _where(index))
    code = code.replace("\r\n", "\n").replace("\r", "\n").rstrip()
    # Remove linhas vazias no começo, mas preserva a indentação da primeira linha.
    lines = code.split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    code = "\n".join(lines)
    if not code.strip():
        raise ValidationError(
            f"{_prefix(index)}o código não pode ser vazio.", {"field": "code", **_where(index)}
        )
    if len(code) > MAX_CODE_CHARS:
        raise ValidationError(
            f"{_prefix(index)}o código passa de {MAX_CODE_CHARS} caracteres.",
            {"field": "code", "length": len(code), **_where(index)},
        )
    return code


def clean_description(description: str, index: int | None = None) -> str:
    if not isinstance(description, str):
        raise ValidationError(f"{_prefix(index)}'description' deve ser texto.", _where(index))
    description = description.replace("\r\n", "\n").strip()
    if not description:
        raise ValidationError(
            f"{_prefix(index)}a descrição não pode ser vazia.",
            {"field": "description", **_where(index)},
        )
    if len(description) > MAX_DESCRIPTION_CHARS:
        raise ValidationError(
            f"{_prefix(index)}a descrição passa de {MAX_DESCRIPTION_CHARS} caracteres.",
            {"field": "description", "length": len(description), **_where(index)},
        )
    return description


def clean_tags(tags: list[str], index: int | None = None) -> list[str]:
    if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
        raise ValidationError(
            f"{_prefix(index)}'tags' deve ser uma lista de textos.",
            {"field": "tags", **_where(index)},
        )
    result: list[str] = []
    for tag in tags:
        tag = " ".join(tag.split())
        if not tag or tag in result:
            continue
        if len(tag) > MAX_TAG_CHARS:
            raise ValidationError(
                f"{_prefix(index)}a tag '{tag[:20]}…' passa de {MAX_TAG_CHARS} caracteres.",
                {"field": "tags", **_where(index)},
            )
        result.append(tag)
    if len(result) > MAX_TAGS:
        raise ValidationError(
            f"{_prefix(index)}no máximo {MAX_TAGS} tags por card.",
            {"field": "tags", **_where(index)},
        )
    return result


def clean_language(language: str | None, index: int | None = None) -> tuple[str, list[Warning]]:
    if language is None:
        return languages.DEFAULT_LANGUAGE, []
    if not isinstance(language, str) or not language.strip():
        raise ValidationError(
            f"{_prefix(index)}'language' deve ser um texto não vazio.",
            {"field": "language", **_where(index)},
        )
    language_id = languages.normalize(language)
    if languages.is_known(language_id):
        return language_id, []
    warning: Warning = {
        "code": "UNKNOWN_LANGUAGE",
        "message": (
            f"{_prefix(index)}a linguagem '{language_id}' não tem highlight; "
            "o card aparece como texto puro."
        ),
        "details": {"language": language_id, **_where(index)},
    }
    return language_id, [warning]


def clean_draft(draft: CardDraft, index: int | None = None) -> tuple[CardDraft, list[Warning]]:
    language, warnings = clean_language(draft.language, index)
    cleaned = CardDraft(
        code=clean_code(draft.code, index),
        description=clean_description(draft.description, index),
        language=language,
        tags=clean_tags(draft.tags, index),
    )
    return cleaned, warnings


def slice_lines(text: str, spec: str) -> str:
    """Recorta as linhas ``A-B`` (1-based, inclusivo) e remove a indentação comum.

    Aceita ``"10-40"``, ``"10-"`` (até o fim) e ``"10"`` (uma linha só).
    """
    spec = spec.strip()
    lines = text.replace("\r\n", "\n").split("\n")
    try:
        if "-" in spec:
            start_s, end_s = spec.split("-", 1)
            start = int(start_s)
            end = int(end_s) if end_s.strip() else len(lines)
        else:
            start = end = int(spec)
    except ValueError as exc:
        raise ValidationError(
            f"Intervalo de linhas inválido: '{spec}'. Use, por exemplo, 10-40.",
            {"field": "lines", "value": spec},
        ) from exc
    if start < 1 or end < start or start > len(lines):
        raise ValidationError(
            f"Intervalo de linhas fora do arquivo: '{spec}' (o arquivo tem {len(lines)} linhas).",
            {"field": "lines", "value": spec, "line_count": len(lines)},
        )
    return textwrap.dedent("\n".join(lines[start - 1 : end]))


def deck_full_error(deck: Deck, requested: int = 1) -> DeckFullError:
    available = deck.available_slots
    if available == 0:
        message = f"O deck '{deck.name}' já tem {MAX_CARDS_PER_DECK} cards."
    else:
        message = (
            f"O deck '{deck.name}' só tem {available} vaga(s); foram enviados {requested} cards."
        )
    return DeckFullError(
        message,
        {"deck_id": deck.id, "available": available, "requested": requested},
    )


class CardService:
    def __init__(self, store: JsonStore, decks: DeckService, clock: Clock | None = None) -> None:
        self.store = store
        self.decks = decks
        self.clock: Clock = clock or SystemClock()
        self._scheduler = SpacedScheduler()

    # -- consultas ----------------------------------------------------------

    def find(self, card_id: str) -> tuple[Deck, Card]:
        card_id = card_id.strip()
        for deck in self.store.load_all_decks():
            card = deck.find_card(card_id)
            if card is not None:
                return deck, card
        raise CardNotFoundError(f"Card '{card_id}' não encontrado.", {"card_id": card_id})

    def _all_card_ids(self) -> set[str]:
        return {c.id for d in self.store.load_all_decks() for c in d.cards}

    # -- criação ------------------------------------------------------------

    def append_to_deck(self, deck: Deck, drafts: list[CardDraft]) -> list[Card]:
        """Valida e acrescenta cards a ``deck`` (em memória). Tudo ou nada.

        Quem chama deve segurar a trava do deck e gravar o resultado.
        """
        if len(drafts) > deck.available_slots:
            raise deck_full_error(deck, len(drafts))
        now = self.clock.now()
        existing = self._all_card_ids()
        cards: list[Card] = []
        for draft in drafts:
            card_id = new_card_id()
            while card_id in existing:
                card_id = new_card_id()
            existing.add(card_id)
            cards.append(
                Card(
                    id=card_id,
                    language=draft.language or languages.DEFAULT_LANGUAGE,
                    code=draft.code,
                    description=draft.description,
                    tags=list(draft.tags),
                    created_at=now,
                    updated_at=now,
                    fsrs=self._scheduler.new_state(now),
                )
            )
        deck.cards.extend(cards)
        return cards

    def add(self, deck_ref: str, draft: CardDraft) -> tuple[Deck, Card, list[Warning]]:
        cleaned, warnings = clean_draft(draft)
        deck_id = self.decks.get(deck_ref).id
        with self.store.deck_lock(deck_id):
            deck = self.store.load_deck(deck_id)
            [card] = self.append_to_deck(deck, [cleaned])
            self.store.save_deck(deck)
        return deck, card, warnings

    # -- alteração ----------------------------------------------------------

    @contextlib.contextmanager
    def _locked(self, *deck_ids: str) -> Iterator[None]:
        """Trava vários decks sempre na mesma ordem, para evitar deadlock."""
        with contextlib.ExitStack() as stack:
            for deck_id in sorted(set(deck_ids)):
                stack.enter_context(self.store.deck_lock(deck_id))
            yield

    def edit(
        self,
        card_id: str,
        *,
        code: str | None = None,
        description: str | None = None,
        language: str | None = None,
        tags: list[str] | None = None,
        deck_ref: str | None = None,
    ) -> tuple[Deck, Card, list[Warning]]:
        """Altera os campos informados. ``deck_ref`` move o card para outro deck."""
        warnings: list[Warning] = []
        new_code = clean_code(code) if code is not None else None
        new_description = clean_description(description) if description is not None else None
        new_tags = clean_tags(tags) if tags is not None else None
        new_language: str | None = None
        if language is not None:
            new_language, warnings = clean_language(language)

        source, _ = self.find(card_id)
        target_id = self.decks.get(deck_ref).id if deck_ref is not None else source.id

        with self._locked(source.id, target_id):
            source = self.store.load_deck(source.id)
            card = source.find_card(card_id)
            if card is None:
                raise CardNotFoundError(f"Card '{card_id}' não encontrado.", {"card_id": card_id})
            target = source if target_id == source.id else self.store.load_deck(target_id)
            if target is not source and target.available_slots == 0:
                raise deck_full_error(target)

            changed = False
            for attr, value in (
                ("code", new_code),
                ("description", new_description),
                ("language", new_language),
                ("tags", new_tags),
            ):
                if value is not None and getattr(card, attr) != value:
                    setattr(card, attr, value)
                    changed = True
            if changed:
                card.updated_at = self.clock.now()

            if target is not source:
                source.cards.remove(card)
                target.cards.append(card)
                # Grava o destino primeiro: se algo falhar no meio, o card
                # fica duplicado em vez de sumir.
                self.store.save_deck(target)
                self.store.save_deck(source)
            elif changed:
                self.store.save_deck(source)
        return target, card, warnings

    def delete(self, card_id: str) -> tuple[Deck, Card]:
        deck, _ = self.find(card_id)
        with self.store.deck_lock(deck.id):
            deck = self.store.load_deck(deck.id)
            card = deck.find_card(card_id)
            if card is None:
                raise CardNotFoundError(f"Card '{card_id}' não encontrado.", {"card_id": card_id})
            deck.cards.remove(card)
            self.store.save_deck(deck)
        return deck, card
