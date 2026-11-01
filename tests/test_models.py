from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from code_cards.clock import FixedClock, from_iso, study_day_end, study_day_start, to_iso
from code_cards.models import (
    DEFAULT_KEYS,
    Card,
    Deck,
    Grade,
    ReviewEntry,
    Settings,
    new_card_id,
    new_deck_id,
)

T0 = datetime(2026, 11, 1, 14, 0, tzinfo=UTC)


def make_card(**overrides: object) -> Card:
    data: dict[str, object] = {
        "id": "c7d1e0b2",
        "language": "python",
        "code": "async def main():\n    await asyncio.gather(a(), b())",
        "description": "Roda a() e b() concorrentemente.",
        "created_at": T0,
        "updated_at": T0,
        "fsrs": {"state": 1},
    }
    data.update(overrides)
    return Card(**data)  # type: ignore[arg-type]


def test_ids_tem_tamanho_certo() -> None:
    assert len(new_deck_id()) == 6
    assert len(new_card_id()) == 8
    assert new_card_id() != new_card_id()


def test_card_ida_e_volta() -> None:
    card = make_card(tags=["asyncio"], introduced_at=T0 + timedelta(minutes=3))
    assert Card.from_dict(card.to_dict()) == card


def test_card_ordem_fixa_das_chaves() -> None:
    assert list(make_card().to_dict()) == [
        "id",
        "language",
        "code",
        "description",
        "tags",
        "created_at",
        "updated_at",
        "introduced_at",
        "fsrs",
    ]


def test_deck_ida_e_volta() -> None:
    deck = Deck(id="k3f9a2", name="Python async", created_at=T0, cards=[make_card()])
    data = deck.to_dict()
    assert data["schema_version"] == 1
    assert data["created_at"] == "2026-11-01T14:00:00Z"
    assert Deck.from_dict(data) == deck
    assert deck.available_slots == 99


def test_card_first_line_ignora_linhas_vazias() -> None:
    assert make_card(code="\n\n  x = 1\ny = 2").first_line == "x = 1"


def test_review_entry_formato() -> None:
    entry = ReviewEntry("r1", "c1", Grade.GREAT, 3, T0)
    assert entry.to_dict() == {
        "type": "review",
        "id": "r1",
        "card_id": "c1",
        "grade": "great",
        "rating": 3,
        "reviewed_at": "2026-11-01T14:00:00Z",
    }
    assert ReviewEntry.from_dict(entry.to_dict()) == entry


def test_settings_padroes_e_parcial() -> None:
    settings = Settings.from_dict({"keys": {"great": "j", "invalida": "x"}})
    assert settings.keys == {**DEFAULT_KEYS, "great": "j"}
    assert settings.new_cards_per_day == 50
    assert settings.reviews_per_day == 200
    assert Settings.from_dict(settings.to_dict()) == settings


def test_iso() -> None:
    assert to_iso(T0) == "2026-11-01T14:00:00Z"
    assert from_iso("2026-11-01T14:00:00Z") == T0
    assert from_iso("2026-11-01T11:00:00-03:00") == T0


def test_dia_de_estudo_vira_as_4h_locais() -> None:
    sp = timezone(timedelta(hours=-3))
    # 02h em São Paulo (05h UTC) ainda pertence ao dia anterior.
    madrugada = datetime(2026, 11, 2, 5, 0, tzinfo=UTC)
    assert study_day_start(madrugada, 4, sp) == datetime(2026, 11, 1, 7, 0, tzinfo=UTC)
    assert study_day_end(madrugada, 4, sp) == datetime(2026, 11, 2, 7, 0, tzinfo=UTC)
    # 04h em ponto já é o dia novo.
    quatro = datetime(2026, 11, 2, 7, 0, tzinfo=UTC)
    assert study_day_start(quatro, 4, sp) == quatro


def test_fixed_clock_avanca() -> None:
    clock = FixedClock(T0)
    clock.advance(minutes=10)
    assert clock.now() == T0 + timedelta(minutes=10)
