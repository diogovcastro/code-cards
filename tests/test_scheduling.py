from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fsrs import Rating

from code_cards.models import Grade
from code_cards.scheduling import (
    GRADE_TO_RATING,
    CardPhase,
    SpacedScheduler,
    format_interval,
)

T0 = datetime(2026, 11, 1, 14, 0, tzinfo=UTC)


@pytest.fixture
def scheduler() -> SpacedScheduler:
    return SpacedScheduler(desired_retention=0.9)


def test_mapeamento_das_notas() -> None:
    expected = {
        Grade.GREAT: Rating.Good,
        Grade.PARTIAL: Rating.Hard,
        Grade.FORGOT: Rating.Again,
    }
    assert expected == GRADE_TO_RATING


def test_card_novo_esta_vencido(scheduler: SpacedScheduler) -> None:
    state = scheduler.new_state(T0)
    assert scheduler.is_due(state, T0)
    assert scheduler.phase(state) is CardPhase.LEARNING


def test_review_gera_entrada_e_novo_estado(scheduler: SpacedScheduler) -> None:
    state = scheduler.new_state(T0)
    new_state, entry = scheduler.review(state, Grade.GREAT, T0, card_id="c1")
    assert entry.card_id == "c1"
    assert entry.grade is Grade.GREAT
    assert entry.rating == 3
    assert entry.reviewed_at == T0
    assert scheduler.due(new_state) > T0
    assert not scheduler.is_due(new_state, T0)


def test_preview_de_card_novo_usa_etapas_de_aprendizado(scheduler: SpacedScheduler) -> None:
    preview = scheduler.preview(scheduler.new_state(T0), T0)
    assert preview[Grade.FORGOT] == timedelta(minutes=1)
    assert preview[Grade.GREAT] == timedelta(minutes=10)
    assert timedelta(minutes=1) <= preview[Grade.PARTIAL] <= timedelta(minutes=10)


def test_preview_e_estavel_e_nao_altera_estado(scheduler: SpacedScheduler) -> None:
    state = scheduler.new_state(T0)
    # Leva o card até a fase de revisão.
    now = T0
    for _ in range(3):
        state, _ = scheduler.review(state, Grade.GREAT, now, card_id="c1")
        now = scheduler.due(state)
    assert scheduler.phase(state) is CardPhase.REVIEW
    snapshot = dict(state)
    first = scheduler.preview(state, now)
    assert first == scheduler.preview(state, now)
    assert state == snapshot
    assert first[Grade.FORGOT] < first[Grade.PARTIAL] <= first[Grade.GREAT]


def test_esquecer_card_em_revisao_volta_para_reaprendizado(scheduler: SpacedScheduler) -> None:
    state = scheduler.new_state(T0)
    now = T0
    for _ in range(3):
        state, _ = scheduler.review(state, Grade.GREAT, now, card_id="c1")
        now = scheduler.due(state)
    state, _ = scheduler.review(state, Grade.FORGOT, now, card_id="c1")
    assert scheduler.phase(state) is CardPhase.RELEARNING
    assert scheduler.due(state) - now == timedelta(minutes=10)


@pytest.mark.parametrize(
    ("delta", "text"),
    [
        (timedelta(seconds=20), "<1min"),
        (timedelta(minutes=10), "10min"),
        (timedelta(hours=3), "3h"),
        (timedelta(days=4), "4d"),
        (timedelta(days=45), "1,5 mês"),
        (timedelta(days=91), "3 meses"),
        (timedelta(days=365), "1 ano"),
        (timedelta(days=900), "2,5 anos"),
    ],
)
def test_format_interval(delta: timedelta, text: str) -> None:
    assert format_interval(delta) == text
