"""Registro de linguagens e highlight.

Para adicionar uma linguagem, registre-a em ``REGISTRY``. Cards antigos com
esse ``language`` passam a ter highlight sem migração.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePath


@dataclass(frozen=True)
class Language:
    id: str  # "python"
    label: str  # "Python"
    extensions: tuple[str, ...]  # (".py", ".pyi")
    tree_sitter: str | None  # nome da gramática no TextArea do Textual


PLAIN_TEXT = Language("text", "Texto puro", (".txt",), None)

REGISTRY: dict[str, Language] = {
    "python": Language("python", "Python", (".py", ".pyi"), "python"),
}

DEFAULT_LANGUAGE = "python"


def normalize(language_id: str) -> str:
    return language_id.strip().lower()


def get(language_id: str) -> Language | None:
    language_id = normalize(language_id)
    if language_id == PLAIN_TEXT.id:
        return PLAIN_TEXT
    return REGISTRY.get(language_id)


def is_known(language_id: str) -> bool:
    return get(language_id) is not None


def highlight_for(language_id: str) -> str | None:
    """Gramática do Textual para ``language_id`` (``None`` = texto puro)."""
    language = get(language_id)
    return language.tree_sitter if language else None


def label_for(language_id: str) -> str:
    language = get(language_id)
    return language.label if language else language_id


def detect_from_filename(filename: str) -> str | None:
    suffix = PurePath(filename).suffix.lower()
    if not suffix:
        return None
    for language in (*REGISTRY.values(), PLAIN_TEXT):
        if suffix in language.extensions:
            return language.id
    return None


def choices() -> list[Language]:
    """Linguagens que podem ser escolhidas no editor."""
    return [*REGISTRY.values(), PLAIN_TEXT]
