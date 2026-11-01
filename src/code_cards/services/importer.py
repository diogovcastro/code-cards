"""Importação de cards em lote a partir de JSON.

O lote é tudo ou nada: valida todos os cards e o espaço no deck antes de
gravar qualquer coisa.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from code_cards.errors import DeckNotFoundError, ValidationError
from code_cards.models import MAX_CARDS_PER_DECK
from code_cards.services.cards import CardDraft, CardService, Warning, clean_draft, deck_full_error
from code_cards.services.decks import DeckService
from code_cards.storage import JsonStore

BATCH_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Lote de cards do code-cards",
    "description": (
        "Lote de cards para 'code-cards import'. É tudo ou nada: se um card for "
        "inválido ou não houver vagas no deck, nada é gravado."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["deck", "cards"],
    "properties": {
        "deck": {
            "type": "string",
            "minLength": 1,
            "description": "Nome ou id do deck de destino.",
        },
        "create_deck_if_missing": {
            "type": "boolean",
            "default": False,
            "description": "Cria o deck com esse nome se ele não existir.",
        },
        "cards": {
            "type": "array",
            "minItems": 1,
            "maxItems": MAX_CARDS_PER_DECK,
            "description": f"Cards a adicionar. Um deck tem no máximo {MAX_CARDS_PER_DECK}.",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["code", "description"],
                "properties": {
                    "code": {
                        "type": "string",
                        "minLength": 1,
                        "description": "Trecho de código mostrado na frente do card.",
                    },
                    "description": {
                        "type": "string",
                        "minLength": 1,
                        "description": "O que o código faz, revelado no verso do card.",
                    },
                    "language": {
                        "type": "string",
                        "default": "python",
                        "description": (
                            "Linguagem do código. Hoje há highlight para 'python'; "
                            "'text' e outras aparecem como texto puro."
                        ),
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": [],
                    },
                },
            },
        },
    },
}

_BATCH_KEYS = set(BATCH_SCHEMA["properties"])
_CARD_KEYS = set(BATCH_SCHEMA["properties"]["cards"]["items"]["properties"])


@dataclass
class Batch:
    deck: str
    create_deck_if_missing: bool
    cards: list[CardDraft]


@dataclass
class ImportResult:
    deck_id: str
    deck_name: str
    deck_created: bool
    card_ids: list[str]
    warnings: list[Warning] = field(default_factory=list)


def parse_batch(data: Any) -> tuple[Batch, list[Warning]]:
    """Valida a estrutura do lote e de cada card. Junta todos os erros de uma vez."""
    if not isinstance(data, dict):
        raise ValidationError("O lote deve ser um objeto JSON.", {"path": "$"})
    errors: list[dict[str, Any]] = []

    def err(path: str, message: str) -> None:
        errors.append({"path": path, "message": message})

    for key in sorted(set(data) - _BATCH_KEYS):
        err(f"$.{key}", "campo desconhecido")
    deck = data.get("deck")
    if not isinstance(deck, str) or not deck.strip():
        err("$.deck", "obrigatório: nome ou id do deck")
    create = data.get("create_deck_if_missing", False)
    if not isinstance(create, bool):
        err("$.create_deck_if_missing", "deve ser true ou false")
    raw_cards = data.get("cards")
    if not isinstance(raw_cards, list) or not raw_cards:
        err("$.cards", "obrigatório: lista com pelo menos um card")
        raw_cards = []
    elif len(raw_cards) > MAX_CARDS_PER_DECK:
        err("$.cards", f"no máximo {MAX_CARDS_PER_DECK} cards (limite de um deck)")

    drafts: list[CardDraft] = []
    warnings: list[Warning] = []
    for i, raw in enumerate(raw_cards):
        path = f"$.cards[{i}]"
        if not isinstance(raw, dict):
            err(path, "cada card deve ser um objeto")
            continue
        unknown = sorted(set(raw) - _CARD_KEYS)
        for key in unknown:
            err(f"{path}.{key}", "campo desconhecido")
        try:
            draft, card_warnings = clean_draft(
                CardDraft(
                    code=raw.get("code", ""),
                    description=raw.get("description", ""),
                    language=raw.get("language"),
                    tags=raw.get("tags", []),
                ),
                index=i,
            )
        except ValidationError as exc:
            field_name = exc.details.get("field")
            err(f"{path}.{field_name}" if field_name else path, exc.message)
            continue
        drafts.append(draft)
        warnings.extend(card_warnings)

    if errors:
        summary = "; ".join(f"{e['path']}: {e['message']}" for e in errors[:5])
        more = f" (e mais {len(errors) - 5})" if len(errors) > 5 else ""
        raise ValidationError(f"Lote inválido: {summary}{more}.", {"errors": errors})
    assert isinstance(deck, str)
    return Batch(deck=deck.strip(), create_deck_if_missing=create, cards=drafts), warnings


class ImportService:
    def __init__(self, store: JsonStore, decks: DeckService, cards: CardService) -> None:
        self.store = store
        self.decks = decks
        self.cards = cards

    def import_batch(self, data: Any) -> ImportResult:
        batch, warnings = parse_batch(data)
        with self.store.global_lock():
            existing = self.decks.find(batch.deck)
            if existing is None:
                if not batch.create_deck_if_missing:
                    raise DeckNotFoundError(
                        f"Deck '{batch.deck}' não encontrado. "
                        'Use "create_deck_if_missing": true para criá-lo.',
                        {"deck": batch.deck},
                    )
                deck = self.decks.build_new(batch.deck)
                created = True
            else:
                deck = existing
                created = False
            with self.store.deck_lock(deck.id):
                if not created:
                    deck = self.store.load_deck(deck.id)
                if len(batch.cards) > deck.available_slots:
                    raise deck_full_error(deck, len(batch.cards))
                new_cards = self.cards.append_to_deck(deck, batch.cards)
                self.store.save_deck(deck)
        return ImportResult(
            deck_id=deck.id,
            deck_name=deck.name,
            deck_created=created,
            card_ids=[c.id for c in new_cards],
            warnings=warnings,
        )
