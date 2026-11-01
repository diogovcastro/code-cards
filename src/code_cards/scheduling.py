"""Adaptador do agendamento (FSRS).

O resto do app só conhece ``SpacedScheduler`` e trata o estado do card como
um ``dict`` opaco. Só este módulo sabe que o ``dict`` é um ``fsrs.Card``
serializado, então dá para trocar o algoritmo sem mexer em mais nada.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from fsrs import Card as FsrsCard
from fsrs import Rating, Scheduler, State

from code_cards.clock import ensure_utc
from code_cards.models import Grade, ReviewEntry, new_review_id

GRADE_TO_RATING: dict[Grade, Rating] = {
    Grade.GREAT: Rating.Good,
    Grade.PARTIAL: Rating.Hard,
    Grade.FORGOT: Rating.Again,
}


class CardPhase(StrEnum):
    LEARNING = "learning"
    REVIEW = "review"
    RELEARNING = "relearning"


_STATE_TO_PHASE = {
    State.Learning: CardPhase.LEARNING,
    State.Review: CardPhase.REVIEW,
    State.Relearning: CardPhase.RELEARNING,
}


class SpacedScheduler:
    def __init__(self, desired_retention: float = 0.9) -> None:
        self.desired_retention = desired_retention
        # Padrões da biblioteca: etapas de 1 e 10 min, reaprendizado de 10 min,
        # intervalo máximo de 36500 dias.
        self._scheduler = Scheduler(desired_retention=desired_retention)
        # Sem fuzzing para a prévia mostrar um número estável.
        self._preview = Scheduler(desired_retention=desired_retention, enable_fuzzing=False)

    @staticmethod
    def _load(state: dict[str, Any]) -> FsrsCard:
        return FsrsCard.from_dict(state)  # type: ignore[arg-type]

    @staticmethod
    def _dump(card: FsrsCard) -> dict[str, Any]:
        return dict(card.to_dict())

    def new_state(self, now: datetime) -> dict[str, Any]:
        """Estado de um card que nunca foi estudado, disponível a partir de ``now``."""
        return self._dump(FsrsCard(card_id=0, due=ensure_utc(now)))

    def review(
        self, state: dict[str, Any], grade: Grade, now: datetime, card_id: str
    ) -> tuple[dict[str, Any], ReviewEntry]:
        now = ensure_utc(now)
        rating = GRADE_TO_RATING[grade]
        card, _log = self._scheduler.review_card(self._load(state), rating, now)
        entry = ReviewEntry(
            id=new_review_id(),
            card_id=card_id,
            grade=grade,
            rating=int(rating),
            reviewed_at=now,
        )
        return self._dump(card), entry

    def preview(self, state: dict[str, Any], now: datetime) -> dict[Grade, timedelta]:
        """Intervalo até a próxima revisão para cada nota, sem alterar o estado."""
        now = ensure_utc(now)
        result: dict[Grade, timedelta] = {}
        for grade, rating in GRADE_TO_RATING.items():
            card, _log = self._preview.review_card(self._load(state), rating, now)
            result[grade] = card.due - now
        return result

    def due(self, state: dict[str, Any]) -> datetime:
        return ensure_utc(self._load(state).due)

    def is_due(self, state: dict[str, Any], now: datetime) -> bool:
        return self.due(state) <= ensure_utc(now)

    def phase(self, state: dict[str, Any]) -> CardPhase:
        return _STATE_TO_PHASE[self._load(state).state]


def format_interval(delta: timedelta) -> str:
    """Formato curto para a barra de notas: ``10min``, ``3h``, ``4d``, ``2 meses``."""
    seconds = max(0, delta.total_seconds())
    minutes = seconds / 60
    if minutes < 1:
        return "<1min"
    if minutes < 60:
        return f"{round(minutes)}min"
    hours = minutes / 60
    if hours < 24:
        return f"{round(hours)}h"
    days = hours / 24
    if days < 31:
        return f"{round(days)}d"
    if days < 365:
        months = round(days / 30.4, 1)
        return _plural(months, "mês", "meses")
    years = round(days / 365, 1)
    return _plural(years, "ano", "anos")


def _plural(value: float, singular: str, plural: str) -> str:
    text = f"{value:.1f}".rstrip("0").rstrip(".").replace(".", ",")
    return f"{text} {singular if value < 2 else plural}"
