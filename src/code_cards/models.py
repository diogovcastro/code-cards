"""Modelos de domínio: Deck, Card, ReviewEntry, Settings e Grade.

Cada modelo sabe se converter para ``dict`` com as chaves numa ordem fixa
(para diffs legíveis no git) e voltar a partir dele.
"""

from __future__ import annotations

import secrets
import string
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from code_cards.clock import from_iso, to_iso

DECK_SCHEMA_VERSION = 1
SETTINGS_SCHEMA_VERSION = 2
MAX_CARDS_PER_DECK = 100

_ID_ALPHABET = string.ascii_lowercase + string.digits


def new_id(length: int, prefix: str = "") -> str:
    return prefix + "".join(secrets.choice(_ID_ALPHABET) for _ in range(length))


def new_deck_id() -> str:
    return new_id(6)


def new_card_id() -> str:
    return new_id(8)


def new_review_id() -> str:
    return new_id(8, prefix="r")


class Grade(StrEnum):
    """Notas do usuário. O adaptador FSRS converte em ``Rating``."""

    GREAT = "great"  # Ótimo      → Rating.Good
    PARTIAL = "partial"  # Parcial    → Rating.Hard
    FORGOT = "forgot"  # Não lembro → Rating.Again

    @property
    def label(self) -> str:
        return GRADE_LABELS[self]


GRADE_LABELS: dict[Grade, str] = {
    Grade.GREAT: "Ótimo",
    Grade.PARTIAL: "Parcial",
    Grade.FORGOT: "Não lembro",
}


def _opt_iso(dt: datetime | None) -> str | None:
    return to_iso(dt) if dt is not None else None


def _opt_dt(value: str | None) -> datetime | None:
    return from_iso(value) if value else None


@dataclass
class Card:
    id: str
    language: str
    code: str
    description: str
    created_at: datetime
    updated_at: datetime
    fsrs: dict[str, Any]
    tags: list[str] = field(default_factory=list)
    introduced_at: datetime | None = None

    @property
    def is_new(self) -> bool:
        return self.introduced_at is None

    @property
    def first_line(self) -> str:
        for line in self.code.splitlines():
            if line.strip():
                return line.strip()
        return ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "language": self.language,
            "code": self.code,
            "description": self.description,
            "tags": list(self.tags),
            "created_at": to_iso(self.created_at),
            "updated_at": to_iso(self.updated_at),
            "introduced_at": _opt_iso(self.introduced_at),
            "fsrs": self.fsrs,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Card:
        return cls(
            id=data["id"],
            language=data.get("language", "text"),
            code=data["code"],
            description=data["description"],
            tags=list(data.get("tags", [])),
            created_at=from_iso(data["created_at"]),
            updated_at=from_iso(data["updated_at"]),
            introduced_at=_opt_dt(data.get("introduced_at")),
            fsrs=dict(data["fsrs"]),
        )


@dataclass
class Deck:
    id: str
    name: str
    created_at: datetime
    cards: list[Card] = field(default_factory=list)

    @property
    def available_slots(self) -> int:
        return max(0, MAX_CARDS_PER_DECK - len(self.cards))

    def find_card(self, card_id: str) -> Card | None:
        for card in self.cards:
            if card.id == card_id:
                return card
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": DECK_SCHEMA_VERSION,
            "id": self.id,
            "name": self.name,
            "created_at": to_iso(self.created_at),
            "cards": [card.to_dict() for card in self.cards],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Deck:
        return cls(
            id=data["id"],
            name=data["name"],
            created_at=from_iso(data["created_at"]),
            cards=[Card.from_dict(c) for c in data.get("cards", [])],
        )


@dataclass
class ReviewEntry:
    """Evento de revisão gravado no histórico ``reviews/<deck-id>.jsonl``."""

    id: str
    card_id: str
    grade: Grade
    rating: int
    reviewed_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "review",
            "id": self.id,
            "card_id": self.card_id,
            "grade": self.grade.value,
            "rating": self.rating,
            "reviewed_at": to_iso(self.reviewed_at),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewEntry:
        return cls(
            id=data["id"],
            card_id=data["card_id"],
            grade=Grade(data["grade"]),
            rating=int(data["rating"]),
            reviewed_at=from_iso(data["reviewed_at"]),
        )


def undo_event(review_id: str, at: datetime) -> dict[str, Any]:
    return {"type": "undo", "review_id": review_id, "at": to_iso(at)}


#: Ações configuráveis (teclas e, depois, botões do mouse).
ACTIONS: tuple[str, ...] = (
    "great",
    "partial",
    "forgot",
    "reveal",
    "undo",
    "back",
    "scroll_up",
    "scroll_down",
)
ACTION_LABELS: dict[str, str] = {
    "great": "Ótimo",
    "partial": "Parcial",
    "forgot": "Não lembro",
    "reveal": "Mostrar descrição",
    "undo": "Desfazer",
    "back": "Voltar",
    "scroll_up": "Rolar para cima",
    "scroll_down": "Rolar para baixo",
}
#: Ações que podem ficar sem tecla (as setas ↑/↓ sempre rolam).
OPTIONAL_KEY_ACTIONS: frozenset[str] = frozenset({"scroll_up", "scroll_down"})
DEFAULT_KEYS: dict[str, str | None] = {
    "great": "a",
    "partial": "s",
    "forgot": "d",
    "reveal": "space",
    "undo": "u",
    "back": "escape",
    "scroll_up": "w",
    "scroll_down": None,  # "s" é Parcial
}


@dataclass
class Settings:
    keys: dict[str, str | None] = field(default_factory=lambda: dict(DEFAULT_KEYS))
    show_help: bool = True
    new_cards_per_day: int = 50
    reviews_per_day: int = 200
    desired_retention: float = 0.9
    day_starts_at_hour: int = 4
    editor_theme: str = "monokai"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SETTINGS_SCHEMA_VERSION,
            "keys": {action: self.keys.get(action) for action in ACTIONS},
            "show_help": self.show_help,
            "new_cards_per_day": self.new_cards_per_day,
            "reviews_per_day": self.reviews_per_day,
            "desired_retention": self.desired_retention,
            "day_starts_at_hour": self.day_starts_at_hour,
            "editor_theme": self.editor_theme,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Settings:
        defaults = cls()
        keys = dict(DEFAULT_KEYS)
        keys.update({k: v for k, v in data.get("keys", {}).items() if k in DEFAULT_KEYS})
        return cls(
            keys=keys,
            show_help=bool(data.get("show_help", defaults.show_help)),
            new_cards_per_day=int(data.get("new_cards_per_day", defaults.new_cards_per_day)),
            reviews_per_day=int(data.get("reviews_per_day", defaults.reviews_per_day)),
            desired_retention=float(data.get("desired_retention", defaults.desired_retention)),
            day_starts_at_hour=int(data.get("day_starts_at_hour", defaults.day_starts_at_hour)),
            editor_theme=str(data.get("editor_theme", defaults.editor_theme)),
        )
