"""Utilidades compartilhadas pelos comandos da CLI."""

from __future__ import annotations

from typing import Any

from code_cards import languages
from code_cards.clock import to_iso
from code_cards.errors import ConfirmationRequiredError
from code_cards.models import Card, Deck
from code_cards.services.container import Services, build_services
from code_cards.services.study import StudyService


def services() -> Services:
    """Serviços sobre a pasta de dados atual (respeita ``CODE_CARDS_HOME``)."""
    return build_services()


def require_yes(yes: bool, what: str) -> None:
    if not yes:
        raise ConfirmationRequiredError(
            f"Para apagar {what}, repita o comando com --yes.", {"flag": "--yes"}
        )


def deck_view(deck: Deck, study: StudyService | None = None) -> dict[str, Any]:
    view: dict[str, Any] = {
        "id": deck.id,
        "name": deck.name,
        "created_at": to_iso(deck.created_at),
        "cards": len(deck.cards),
        "available": deck.available_slots,
    }
    if study is not None:
        summary = study.summary(deck)
        view["new_today"] = summary.new
        view["due_today"] = summary.due
    return view


def card_view(deck: Deck, card: Card, study: StudyService) -> dict[str, Any]:
    scheduler = study.scheduler()
    return {
        "id": card.id,
        "deck_id": deck.id,
        "deck_name": deck.name,
        "language": card.language,
        "highlight": languages.highlight_for(card.language) is not None,
        "code": card.code,
        "description": card.description,
        "tags": list(card.tags),
        "created_at": to_iso(card.created_at),
        "updated_at": to_iso(card.updated_at),
        "is_new": card.is_new,
        "introduced_at": to_iso(card.introduced_at) if card.introduced_at else None,
        "due": None if card.is_new else to_iso(scheduler.due(card.fsrs)),
    }
