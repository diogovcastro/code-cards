from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def data_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Todos os testes usam CODE_CARDS_HOME numa pasta temporária."""
    home = tmp_path / "code-cards-home"
    monkeypatch.setenv("CODE_CARDS_HOME", str(home))
    return home
