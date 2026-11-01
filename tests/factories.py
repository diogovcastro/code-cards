"""Fábricas compartilhadas pelos testes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

from code_cards.clock import FixedClock
from code_cards.paths import DataPaths
from code_cards.services.container import Services, build_services

SP = timezone(timedelta(hours=-3))
T0 = datetime(2026, 11, 1, 13, 0, tzinfo=UTC)


def make_services(root: Path, clock: FixedClock | None = None) -> Services:
    return build_services(DataPaths(root), clock or FixedClock(T0, tz=SP))
