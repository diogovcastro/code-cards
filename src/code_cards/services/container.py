"""Monta todos os serviços sobre a mesma pasta de dados e o mesmo relógio."""

from __future__ import annotations

from dataclasses import dataclass

from code_cards.clock import Clock, SystemClock
from code_cards.paths import DataPaths
from code_cards.services.cards import CardService
from code_cards.services.decks import DeckService
from code_cards.services.importer import ImportService
from code_cards.services.settings import SettingsService
from code_cards.services.study import StudyService
from code_cards.storage import JsonStore


@dataclass
class Services:
    store: JsonStore
    clock: Clock
    settings: SettingsService
    decks: DeckService
    cards: CardService
    study: StudyService
    importer: ImportService


def build_services(paths: DataPaths | None = None, clock: Clock | None = None) -> Services:
    store = JsonStore(paths or DataPaths.default())
    clock = clock or SystemClock()
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
