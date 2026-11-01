"""Fábricas compartilhadas pelos testes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

from code_cards.clock import FixedClock
from code_cards.paths import DataPaths
from code_cards.services.cards import CardService
from code_cards.services.decks import DeckService
from code_cards.services.importer import ImportService
from code_cards.services.settings import SettingsService
from code_cards.services.study import StudyService
from code_cards.storage import JsonStore

SP = timezone(timedelta(hours=-3))
T0 = datetime(2026, 11, 1, 13, 0, tzinfo=UTC)


@dataclass
class Services:
    store: JsonStore
    clock: FixedClock
    settings: SettingsService
    decks: DeckService
    cards: CardService
    study: StudyService
    importer: ImportService


def make_services(root: Path, clock: FixedClock | None = None) -> Services:
    store = JsonStore(DataPaths(root))
    clock = clock or FixedClock(T0, tz=SP)
    settings = SettingsService(store)
    decks = DeckService(store, clock)
    cards = CardService(store, decks, clock)
    return Services(
        store=store,
        clock=clock,
        settings=settings,
        decks=decks,
        cards=cards,
        study=StudyService(store, settings, clock),
        importer=ImportService(store, decks, cards),
    )
