"""Leitura e escrita dos arquivos de dados.

- Escrita atômica: grava num temporário na mesma pasta e troca com
  ``os.replace``. Se o processo cair no meio, o arquivo antigo fica intacto.
- Trava entre processos (``filelock``) por deck e uma trava global para
  operações que olham vários decks (nome único, criação, remoção).
- ``schema_version`` em todo arquivo, com migrações na leitura.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from filelock import FileLock

from code_cards.errors import DeckNotFoundError, StorageError
from code_cards.models import Deck, Settings
from code_cards.paths import DataPaths
from code_cards.storage.migrations import migrate

LOCK_TIMEOUT_SECONDS = 10.0


def dumps(data: Any) -> str:
    """JSON com ``indent=2``, UTF-8 legível e quebra de linha final."""
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def write_json_atomic(path: Path, data: Any) -> None:
    write_text_atomic(path, dumps(data))


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as tmp:
            tmp.write(text)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp_name)
        raise


def read_json(path: Path) -> Any:
    try:
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        raise StorageError(
            f"Arquivo corrompido: {path} ({exc.msg}, linha {exc.lineno}).",
            {"path": str(path)},
        ) from exc


class JsonStore:
    """Acesso aos arquivos da pasta de dados."""

    def __init__(self, paths: DataPaths | None = None) -> None:
        self.paths = paths or DataPaths.default()
        self._locks: dict[str, FileLock] = {}

    @property
    def root(self) -> Path:
        return self.paths.root

    # -- travas -------------------------------------------------------------

    def _lock(self, name: str) -> FileLock:
        lock = self._locks.get(name)
        if lock is None:
            self.paths.locks_dir.mkdir(parents=True, exist_ok=True)
            lock = FileLock(self.paths.lock_file(name), timeout=LOCK_TIMEOUT_SECONDS)
            self._locks[name] = lock
        return lock

    @contextlib.contextmanager
    def deck_lock(self, deck_id: str) -> Iterator[None]:
        """Trava um deck durante leitura → alteração → escrita."""
        with self._lock(f"deck-{deck_id}"):
            yield

    @contextlib.contextmanager
    def global_lock(self) -> Iterator[None]:
        """Trava operações que envolvem o conjunto de decks."""
        with self._lock("global"):
            yield

    # -- decks --------------------------------------------------------------

    def deck_ids(self) -> list[str]:
        if not self.paths.decks_dir.is_dir():
            return []
        return sorted(p.stem for p in self.paths.decks_dir.glob("*.json"))

    def deck_exists(self, deck_id: str) -> bool:
        return self.paths.deck_file(deck_id).is_file()

    def load_deck(self, deck_id: str) -> Deck:
        path = self.paths.deck_file(deck_id)
        if not path.is_file():
            raise DeckNotFoundError(f"Deck '{deck_id}' não encontrado.", {"deck": deck_id})
        raw = read_json(path)
        data, changed = migrate("deck", raw)
        try:
            deck = Deck.from_dict(data)
        except (KeyError, TypeError, ValueError) as exc:
            raise StorageError(
                f"Deck com formato inválido: {path} ({exc!r}).", {"path": str(path)}
            ) from exc
        if changed:
            self.save_deck(deck)
        return deck

    def load_all_decks(self) -> list[Deck]:
        decks = [self.load_deck(deck_id) for deck_id in self.deck_ids()]
        return sorted(decks, key=lambda d: d.name.casefold())

    def save_deck(self, deck: Deck) -> None:
        write_json_atomic(self.paths.deck_file(deck.id), deck.to_dict())

    def delete_deck(self, deck_id: str) -> None:
        for path in (self.paths.deck_file(deck_id), self.paths.reviews_file(deck_id)):
            with contextlib.suppress(FileNotFoundError):
                path.unlink()

    # -- histórico ----------------------------------------------------------

    def append_event(self, deck_id: str, event: dict[str, Any]) -> None:
        """Acrescenta uma linha ao histórico do deck (nunca reescreve)."""
        path = self.paths.reviews_file(deck_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
        with path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())

    def read_events(self, deck_id: str) -> list[dict[str, Any]]:
        """Eventos do histórico. Linhas ilegíveis (ex.: gravação cortada) são puladas."""
        path = self.paths.reviews_file(deck_id)
        if not path.is_file():
            return []
        events: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(event, dict):
                    events.append(event)
        return events

    # -- configurações ------------------------------------------------------

    def load_settings(self) -> Settings:
        path = self.paths.settings_file
        if not path.is_file():
            return Settings()
        data, changed = migrate("settings", read_json(path))
        settings = Settings.from_dict(data)
        if changed:
            self.save_settings(settings)
        return settings

    def save_settings(self, settings: Settings) -> None:
        with self._lock("settings"):
            write_json_atomic(self.paths.settings_file, settings.to_dict())
