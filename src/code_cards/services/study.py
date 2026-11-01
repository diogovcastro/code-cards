"""Fila de estudo, resposta às notas, limites diários e desfazer.

Ordem da fila ao abrir um deck:

1. Cards em aprendizado/reaprendizado já vencidos.
2. Revisões vencidas, até ``reviews_per_day``.
3. Cards novos, até ``new_cards_per_day``, em ordem de criação.

Se nada disso sobrar, mas houver cards em aprendizado vencendo nos próximos
``LEARN_AHEAD`` minutos, eles aparecem logo ("aprender adiantado").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from code_cards.clock import Clock, SystemClock, from_iso, study_day_end, study_day_start
from code_cards.errors import CardNotFoundError, NothingToUndoError
from code_cards.models import Card, Deck, Grade, ReviewEntry, Settings, undo_event
from code_cards.scheduling import CardPhase, SpacedScheduler
from code_cards.services.settings import SettingsService
from code_cards.storage import JsonStore

LEARN_AHEAD = timedelta(minutes=20)


class QueueKind(StrEnum):
    LEARNING = "learning"
    REVIEW = "review"
    NEW = "new"


@dataclass(frozen=True)
class DeckSummary:
    deck_id: str
    name: str
    new: int
    due: int
    total: int


@dataclass(frozen=True)
class StudyItem:
    deck_id: str
    card: Card
    kind: QueueKind
    previews: dict[Grade, timedelta]


@dataclass
class StudyQueue:
    learning: list[Card] = field(default_factory=list)
    review: list[Card] = field(default_factory=list)
    new: list[Card] = field(default_factory=list)

    def first(self) -> tuple[Card, QueueKind] | None:
        for kind, cards in (
            (QueueKind.LEARNING, self.learning),
            (QueueKind.REVIEW, self.review),
            (QueueKind.NEW, self.new),
        ):
            if cards:
                return cards[0], kind
        return None

    @property
    def due_count(self) -> int:
        return len(self.learning) + len(self.review)


@dataclass(frozen=True)
class _UndoRecord:
    deck_id: str
    card_id: str
    review_id: str
    previous_fsrs: dict[str, Any]
    previous_introduced_at: datetime | None


class StudyService:
    """Uma instância corresponde a uma sessão (a pilha de desfazer é da sessão)."""

    def __init__(
        self,
        store: JsonStore,
        settings: SettingsService | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.store = store
        self.settings_service = settings or SettingsService(store)
        self.clock: Clock = clock or SystemClock()
        self._undo_stack: list[_UndoRecord] = []

    # -- utilidades ---------------------------------------------------------

    def _settings(self) -> Settings:
        return self.settings_service.get()

    def scheduler(self, settings: Settings | None = None) -> SpacedScheduler:
        resolved = settings if settings is not None else self._settings()
        return SpacedScheduler(desired_retention=resolved.desired_retention)

    def _day_bounds(self, settings: Settings, now: datetime) -> tuple[datetime, datetime]:
        tz = self.clock.local_tz()
        return (
            study_day_start(now, settings.day_starts_at_hour, tz),
            study_day_end(now, settings.day_starts_at_hour, tz),
        )

    def _reviewed_today(self, deck: Deck, day_start: datetime) -> int:
        """Cards já vistos antes de hoje que foram revisados hoje (sem os desfeitos)."""
        events = self.store.read_events(deck.id)
        undone = {e.get("review_id") for e in events if e.get("type") == "undo"}
        introduced_before = {
            c.id for c in deck.cards if c.introduced_at is not None and c.introduced_at < day_start
        }
        reviewed: set[str] = set()
        for event in events:
            if event.get("type") != "review" or event.get("id") in undone:
                continue
            try:
                when = from_iso(event["reviewed_at"])
            except (KeyError, ValueError):
                continue
            card_id = event.get("card_id")
            if when >= day_start and card_id in introduced_before:
                reviewed.add(card_id)
        return len(reviewed)

    # -- fila ---------------------------------------------------------------

    def build_queue(self, deck: Deck, *, learn_ahead: bool = True) -> StudyQueue:
        settings = self._settings()
        scheduler = self.scheduler(settings)
        now = self.clock.now()
        day_start, _ = self._day_bounds(settings, now)

        queue = StudyQueue()
        upcoming_learning: list[Card] = []
        for card in deck.cards:
            if card.is_new:
                queue.new.append(card)
                continue
            due = scheduler.due(card.fsrs)
            phase = scheduler.phase(card.fsrs)
            if phase is CardPhase.REVIEW:
                if due <= now:
                    queue.review.append(card)
            elif due <= now:
                queue.learning.append(card)
            elif due <= now + LEARN_AHEAD:
                upcoming_learning.append(card)

        def by_due(c: Card) -> datetime:
            return scheduler.due(c.fsrs)

        queue.learning.sort(key=by_due)
        queue.review.sort(key=by_due)

        review_left = max(0, settings.reviews_per_day - self._reviewed_today(deck, day_start))
        queue.review = queue.review[:review_left]

        introduced_today = sum(
            1 for c in deck.cards if c.introduced_at is not None and c.introduced_at >= day_start
        )
        new_left = max(0, settings.new_cards_per_day - introduced_today)
        queue.new = queue.new[:new_left]

        if learn_ahead and queue.first() is None and upcoming_learning:
            queue.learning = sorted(upcoming_learning, key=by_due)
        return queue

    def summary(self, deck: Deck) -> DeckSummary:
        queue = self.build_queue(deck, learn_ahead=False)
        return DeckSummary(
            deck_id=deck.id,
            name=deck.name,
            new=len(queue.new),
            due=queue.due_count,
            total=len(deck.cards),
        )

    def summaries(self) -> list[DeckSummary]:
        return [self.summary(deck) for deck in self.store.load_all_decks()]

    def next_card(self, deck_id: str) -> StudyItem | None:
        """Próximo card do deck, relendo o arquivo (a CLI pode ter mudado algo)."""
        deck = self.store.load_deck(deck_id)
        first = self.build_queue(deck).first()
        if first is None:
            return None
        card, kind = first
        previews = self.scheduler().preview(card.fsrs, self.clock.now())
        return StudyItem(deck_id=deck.id, card=card, kind=kind, previews=previews)

    def item_for(self, deck_id: str, card_id: str) -> StudyItem:
        """Item de estudo de um card específico (ex.: o card que acabou de ser desfeito)."""
        deck = self.store.load_deck(deck_id)
        card = deck.find_card(card_id)
        if card is None:
            raise CardNotFoundError(
                f"Card '{card_id}' não está mais no deck.",
                {"card_id": card_id, "deck_id": deck_id},
            )
        scheduler = self.scheduler()
        if card.is_new:
            kind = QueueKind.NEW
        elif scheduler.phase(card.fsrs) is CardPhase.REVIEW:
            kind = QueueKind.REVIEW
        else:
            kind = QueueKind.LEARNING
        previews = scheduler.preview(card.fsrs, self.clock.now())
        return StudyItem(deck_id=deck.id, card=card, kind=kind, previews=previews)

    def next_due(self, deck_id: str) -> datetime | None:
        """Quando o deck terá algo para estudar de novo (``None`` se nunca)."""
        deck = self.store.load_deck(deck_id)
        settings = self._settings()
        scheduler = self.scheduler(settings)
        now = self.clock.now()
        candidates = [scheduler.due(c.fsrs) for c in deck.cards if not c.is_new]
        future = [d for d in candidates if d > now]
        result = min(future) if future else None
        has_new = any(c.is_new for c in deck.cards)
        if has_new and settings.new_cards_per_day > 0:
            _, day_end = self._day_bounds(settings, now)
            result = day_end if result is None else min(result, day_end)
        return result

    # -- respostas ----------------------------------------------------------

    def answer(self, deck_id: str, card_id: str, grade: Grade) -> ReviewEntry:
        now = self.clock.now()
        scheduler = self.scheduler()
        with self.store.deck_lock(deck_id):
            deck = self.store.load_deck(deck_id)
            card = deck.find_card(card_id)
            if card is None:
                raise CardNotFoundError(
                    f"Card '{card_id}' não está mais no deck.",
                    {"card_id": card_id, "deck_id": deck_id},
                )
            previous_fsrs = dict(card.fsrs)
            previous_introduced_at = card.introduced_at
            new_state, entry = scheduler.review(card.fsrs, grade, now, card_id=card_id)
            card.fsrs = new_state
            if card.introduced_at is None:
                card.introduced_at = now
            self.store.save_deck(deck)
            self.store.append_event(deck_id, entry.to_dict())
        self._undo_stack.append(
            _UndoRecord(
                deck_id=deck_id,
                card_id=card_id,
                review_id=entry.id,
                previous_fsrs=previous_fsrs,
                previous_introduced_at=previous_introduced_at,
            )
        )
        return entry

    @property
    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    def undo(self) -> tuple[str, str]:
        """Desfaz a última resposta da sessão. Devolve ``(deck_id, card_id)``."""
        if not self._undo_stack:
            raise NothingToUndoError("Não há resposta para desfazer.")
        record = self._undo_stack.pop()
        with self.store.deck_lock(record.deck_id):
            deck = self.store.load_deck(record.deck_id)
            card = deck.find_card(record.card_id)
            if card is None:
                raise CardNotFoundError(
                    f"Card '{record.card_id}' não está mais no deck.",
                    {"card_id": record.card_id, "deck_id": record.deck_id},
                )
            card.fsrs = dict(record.previous_fsrs)
            card.introduced_at = record.previous_introduced_at
            self.store.save_deck(deck)
            self.store.append_event(record.deck_id, undo_event(record.review_id, self.clock.now()))
        return record.deck_id, record.card_id
