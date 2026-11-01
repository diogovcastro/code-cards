"""Relógio injetável e limite do "dia de estudo".

Todos os horários do app são ``datetime`` com fuso UTC. O fuso local só é
usado para decidir quando começa o dia de estudo e para exibir horários.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, tzinfo
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:
        """Momento atual em UTC (com fuso)."""
        ...

    def local_tz(self) -> tzinfo:
        """Fuso local usado para o dia de estudo e a exibição."""
        ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)

    def local_tz(self) -> tzinfo:
        tz = datetime.now().astimezone().tzinfo
        return tz if tz is not None else UTC


class FixedClock:
    """Relógio parado, para testes. Avança só quando pedido."""

    def __init__(self, now: datetime, tz: tzinfo = UTC) -> None:
        self._now = ensure_utc(now)
        self._tz = tz

    def now(self) -> datetime:
        return self._now

    def local_tz(self) -> tzinfo:
        return self._tz

    def set(self, now: datetime) -> None:
        self._now = ensure_utc(now)

    def advance(self, delta: timedelta | None = None, **kwargs: float) -> datetime:
        self._now += delta if delta is not None else timedelta(**kwargs)
        return self._now


def ensure_utc(dt: datetime) -> datetime:
    """Converte para UTC; ``datetime`` sem fuso é tratado como UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def study_day_start(now: datetime, day_starts_at_hour: int, tz: tzinfo) -> datetime:
    """Início (em UTC) do dia de estudo que contém ``now``.

    Com ``day_starts_at_hour=4``, quem estuda às 2h da manhã ainda está no
    dia de estudo anterior, como no Anki.
    """
    local = ensure_utc(now).astimezone(tz)
    start = local.replace(hour=day_starts_at_hour, minute=0, second=0, microsecond=0)
    if local < start:
        start -= timedelta(days=1)
    return start.astimezone(UTC)


def study_day_end(now: datetime, day_starts_at_hour: int, tz: tzinfo) -> datetime:
    """Fim (exclusivo, em UTC) do dia de estudo que contém ``now``."""
    start_local = study_day_start(now, day_starts_at_hour, tz).astimezone(tz)
    next_local = (start_local + timedelta(days=1)).replace(hour=day_starts_at_hour)
    return next_local.astimezone(UTC)


def to_iso(dt: datetime) -> str:
    """Formata em UTC com sufixo ``Z`` e precisão de segundos."""
    return ensure_utc(dt).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def from_iso(value: str) -> datetime:
    """Lê ISO 8601 (aceita ``Z``) e devolve em UTC."""
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return ensure_utc(datetime.fromisoformat(value))
