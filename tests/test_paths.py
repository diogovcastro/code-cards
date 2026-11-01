from __future__ import annotations

from pathlib import Path

import pytest

from code_cards import paths


def test_usa_code_cards_home(data_home: Path) -> None:
    assert paths.data_dir() == data_home.resolve()
    assert paths.data_dir_source() == "env"


def test_sem_variavel_usa_pasta_do_sistema(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(paths.ENV_VAR, raising=False)
    resolved = paths.data_dir()
    assert resolved.name == "code-cards"
    assert paths.data_dir_source() == "default"


def test_variavel_vazia_e_ignorada(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(paths.ENV_VAR, "  ")
    assert paths.data_dir_source() == "default"


def test_caminhos_internos(tmp_path: Path) -> None:
    p = paths.DataPaths(tmp_path)
    assert p.settings_file == tmp_path / "settings.json"
    assert p.deck_file("k3f9a2") == tmp_path / "decks" / "k3f9a2.json"
    assert p.reviews_file("k3f9a2") == tmp_path / "reviews" / "k3f9a2.jsonl"
