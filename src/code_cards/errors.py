"""Erros de domínio com código estável, usados pela CLI e pela TUI."""

from __future__ import annotations

from typing import Any


class CodeCardsError(Exception):
    """Erro base. ``code`` é estável e pode ser lido por scripts e LLMs."""

    code = "INTERNAL_ERROR"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ValidationError(CodeCardsError):
    code = "VALIDATION_ERROR"


class DeckNotFoundError(CodeCardsError):
    code = "DECK_NOT_FOUND"


class CardNotFoundError(CodeCardsError):
    code = "CARD_NOT_FOUND"


class DeckFullError(CodeCardsError):
    code = "DECK_FULL"


class DeckExistsError(CodeCardsError):
    code = "DECK_EXISTS"


class NothingToUndoError(CodeCardsError):
    code = "NOTHING_TO_UNDO"


class StorageError(CodeCardsError):
    """Arquivo corrompido, de versão mais nova ou ilegível."""

    code = "STORAGE_ERROR"


class ConfirmationRequiredError(CodeCardsError):
    """Operação destrutiva sem ``--yes``: falha em vez de perguntar."""

    code = "CONFIRMATION_REQUIRED"
