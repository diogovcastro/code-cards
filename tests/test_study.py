from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from code_cards.clock import FixedClock
from code_cards.errors import CardNotFoundError, NothingToUndoError
from code_cards.models import Card, Deck, Grade
from code_cards.paths import DataPaths
from code_cards.scheduling import SpacedScheduler
from code_cards.services.settings import SettingsService
from code_cards.services.study import QueueKind, StudyService
from code_cards.storage import JsonStore

SP = timezone(timedelta(hours=-3))
# 10h da manhã em São Paulo.
T0 = datetime(2026, 11, 1, 13, 0, tzinfo=UTC)


@pytest.fixture
def store(tmp_path: Path) -> JsonStore:
    return JsonStore(DataPaths(tmp_path))


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(T0, tz=SP)


@pytest.fixture
def study(store: JsonStore, clock: FixedClock) -> StudyService:
    return StudyService(store, SettingsService(store), clock)


def make_deck(store: JsonStore, n_cards: int, deck_id: str = "deck01") -> Deck:
    scheduler = SpacedScheduler()
    created = T0 - timedelta(days=1)
    cards = [
        Card(
            id=f"card{i:04d}",
            language="python",
            code=f"x = {i}",
            description=f"atribui {i}",
            created_at=created + timedelta(seconds=i),
            updated_at=created,
            fsrs=scheduler.new_state(created),
        )
        for i in range(n_cards)
    ]
    deck = Deck(id=deck_id, name=f"Deck {deck_id}", created_at=created, cards=cards)
    store.save_deck(deck)
    return deck


def test_cards_novos_em_ordem_de_criacao(store: JsonStore, study: StudyService) -> None:
    make_deck(store, 3)
    item = study.next_card("deck01")
    assert item is not None
    assert item.card.id == "card0000"
    assert item.kind is QueueKind.NEW
    assert item.previews[Grade.GREAT] == timedelta(minutes=10)


def test_resposta_marca_introducao_e_grava_historico(store: JsonStore, study: StudyService) -> None:
    make_deck(store, 1)
    entry = study.answer("deck01", "card0000", Grade.GREAT)
    card = store.load_deck("deck01").cards[0]
    assert card.introduced_at == T0
    events = store.read_events("deck01")
    assert events == [entry.to_dict()]


def test_ordem_aprendizado_revisao_novo(
    store: JsonStore, study: StudyService, clock: FixedClock
) -> None:
    make_deck(store, 3)
    # card0000 vai para revisão (passa as duas etapas de aprendizado).
    study.answer("deck01", "card0000", Grade.GREAT)
    clock.advance(minutes=10)
    study.answer("deck01", "card0000", Grade.GREAT)
    # card0001 fica em aprendizado.
    study.answer("deck01", "card0001", Grade.FORGOT)
    # Avança até a revisão do card0000 vencer.
    due_review = study.scheduler().due(store.load_deck("deck01").cards[0].fsrs)
    clock.set(due_review)
    queue = study.build_queue(store.load_deck("deck01"))
    assert [c.id for c in queue.learning] == ["card0001"]
    assert [c.id for c in queue.review] == ["card0000"]
    assert [c.id for c in queue.new] == ["card0002"]
    item = study.next_card("deck01")
    assert item is not None
    assert item.card.id == "card0001"
    assert item.kind is QueueKind.LEARNING


def test_limite_de_novos_por_dia(store: JsonStore, study: StudyService, clock: FixedClock) -> None:
    make_deck(store, 60)
    for _ in range(50):
        item = study.next_card("deck01")
        assert item is not None
        assert item.kind is QueueKind.NEW
        study.answer("deck01", item.card.id, Grade.GREAT)
        study.answer("deck01", item.card.id, Grade.GREAT)  # sai do aprendizado
    summary = study.summary(store.load_deck("deck01"))
    assert summary.new == 0
    assert summary.total == 60
    # 03h59 do dia seguinte (horário de SP) ainda é o mesmo dia de estudo.
    clock.set(datetime(2026, 11, 2, 6, 59, tzinfo=UTC))
    assert study.summary(store.load_deck("deck01")).new == 0
    # 04h00 abre um dia novo.
    clock.set(datetime(2026, 11, 2, 7, 0, tzinfo=UTC))
    assert study.summary(store.load_deck("deck01")).new == 10


def test_limite_de_novos_configuravel(store: JsonStore, study: StudyService) -> None:
    make_deck(store, 10)
    study.settings_service.update(new_cards_per_day=3)
    assert study.summary(store.load_deck("deck01")).new == 3


def test_limite_de_revisoes_por_dia(
    store: JsonStore, study: StudyService, clock: FixedClock
) -> None:
    make_deck(store, 5)
    for i in range(5):
        study.answer("deck01", f"card{i:04d}", Grade.GREAT)
    clock.advance(minutes=10)
    for i in range(5):
        study.answer("deck01", f"card{i:04d}", Grade.GREAT)
    study.settings_service.update(reviews_per_day=2)
    clock.advance(days=30)
    deck = store.load_deck("deck01")
    assert study.summary(deck).due == 2
    item = study.next_card("deck01")
    assert item is not None
    assert item.kind is QueueKind.REVIEW
    study.answer("deck01", item.card.id, Grade.GREAT)
    assert study.summary(store.load_deck("deck01")).due == 1


def test_desfazer_restaura_estado_e_introducao(store: JsonStore, study: StudyService) -> None:
    make_deck(store, 2)
    before = store.load_deck("deck01").cards[0]
    entry = study.answer("deck01", "card0000", Grade.PARTIAL)
    assert study.can_undo
    assert study.undo() == ("deck01", "card0000")
    after = store.load_deck("deck01").cards[0]
    assert after.fsrs == before.fsrs
    assert after.introduced_at is None
    events = store.read_events("deck01")
    assert events[-1]["type"] == "undo"
    assert events[-1]["review_id"] == entry.id
    assert not study.can_undo
    with pytest.raises(NothingToUndoError):
        study.undo()


def test_desfazer_revisao_libera_limite(
    store: JsonStore, study: StudyService, clock: FixedClock
) -> None:
    make_deck(store, 2)
    for cid in ("card0000", "card0001"):
        study.answer("deck01", cid, Grade.GREAT)
        study.answer("deck01", cid, Grade.GREAT)
    study.settings_service.update(reviews_per_day=1)
    clock.advance(days=30)
    item = study.next_card("deck01")
    assert item is not None
    study.answer("deck01", item.card.id, Grade.GREAT)
    assert study.summary(store.load_deck("deck01")).due == 0
    study.undo()
    assert study.summary(store.load_deck("deck01")).due == 1


def test_aprender_adiantado(store: JsonStore, study: StudyService) -> None:
    make_deck(store, 1)
    study.answer("deck01", "card0000", Grade.GREAT)  # volta em 10 min
    deck = store.load_deck("deck01")
    assert study.summary(deck).due == 0
    item = study.next_card("deck01")
    assert item is not None
    assert item.card.id == "card0000"
    assert item.kind is QueueKind.LEARNING


def test_deck_concluido_e_proxima_revisao(store: JsonStore, study: StudyService) -> None:
    make_deck(store, 1)
    study.answer("deck01", "card0000", Grade.GREAT)
    study.answer("deck01", "card0000", Grade.GREAT)
    assert study.next_card("deck01") is None
    next_due = study.next_due("deck01")
    assert next_due is not None
    assert next_due > T0


def test_proxima_revisao_considera_novos_de_amanha(store: JsonStore, study: StudyService) -> None:
    make_deck(store, 2)
    study.settings_service.update(new_cards_per_day=1)
    study.answer("deck01", "card0000", Grade.GREAT)
    study.answer("deck01", "card0000", Grade.GREAT)
    assert study.next_card("deck01") is None
    # Próximo dia de estudo começa às 04h de SP = 07h UTC.
    next_due = study.next_due("deck01")
    assert next_due is not None
    assert next_due <= datetime(2026, 11, 2, 7, 0, tzinfo=UTC)


def test_card_apagado_durante_estudo(store: JsonStore, study: StudyService) -> None:
    make_deck(store, 1)
    deck = store.load_deck("deck01")
    deck.cards.clear()
    store.save_deck(deck)
    with pytest.raises(CardNotFoundError):
        study.answer("deck01", "card0000", Grade.GREAT)


def test_item_de_card_especifico_apos_desfazer(store: JsonStore, study: StudyService) -> None:
    make_deck(store, 2)
    study.answer("deck01", "card0000", Grade.GREAT)
    _, card_id = study.undo()
    item = study.item_for("deck01", card_id)
    assert item.card.id == "card0000"
    assert item.kind is QueueKind.NEW
    assert item.previews[Grade.FORGOT] == timedelta(minutes=1)
    with pytest.raises(CardNotFoundError):
        study.item_for("deck01", "naoexiste")
