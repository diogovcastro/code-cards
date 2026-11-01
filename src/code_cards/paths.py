"""Resolve a pasta de dados do code-cards.

A pasta padrão vem de ``platformdirs.user_data_dir("code-cards")``. A variável
de ambiente ``CODE_CARDS_HOME`` substitui esse caminho (testes, decks
versionados num repositório, perfis separados).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import platformdirs

APP_NAME = "code-cards"
ENV_VAR = "CODE_CARDS_HOME"


def data_dir() -> Path:
    """Pasta de dados em uso, considerando ``CODE_CARDS_HOME``."""
    override = os.environ.get(ENV_VAR, "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return Path(platformdirs.user_data_dir(APP_NAME, appauthor=False))


def data_dir_source() -> str:
    """De onde veio a pasta de dados: ``"env"`` ou ``"default"``."""
    return "env" if os.environ.get(ENV_VAR, "").strip() else "default"


@dataclass(frozen=True)
class DataPaths:
    """Caminhos dos arquivos dentro da pasta de dados."""

    root: Path

    @classmethod
    def default(cls) -> DataPaths:
        return cls(data_dir())

    @property
    def settings_file(self) -> Path:
        return self.root / "settings.json"

    @property
    def decks_dir(self) -> Path:
        return self.root / "decks"

    @property
    def reviews_dir(self) -> Path:
        return self.root / "reviews"

    @property
    def locks_dir(self) -> Path:
        return self.root / ".locks"

    def deck_file(self, deck_id: str) -> Path:
        return self.decks_dir / f"{deck_id}.json"

    def reviews_file(self, deck_id: str) -> Path:
        return self.reviews_dir / f"{deck_id}.jsonl"

    def lock_file(self, name: str) -> Path:
        return self.locks_dir / f"{name}.lock"
