from __future__ import annotations

import json
import multiprocessing
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from code_cards.errors import DeckNotFoundError, StorageError
from code_cards.models import Deck, Settings
from code_cards.paths import DataPaths
from code_cards.storage import json_store, migrations
from code_cards.storage.json_store import JsonStore, write_json_atomic

T0 = datetime(2026, 11, 1, 14, 0, tzinfo=UTC)


@pytest.fixture
def store(tmp_path: Path) -> JsonStore:
    return JsonStore(DataPaths(tmp_path / "data"))


def test_salva_e_carrega_deck(store: JsonStore) -> None:
    deck = Deck(id="abc123", name="Python", created_at=T0)
    store.save_deck(deck)
    assert store.deck_ids() == ["abc123"]
    assert store.load_deck("abc123") == deck
    text = store.paths.deck_file("abc123").read_text(encoding="utf-8")
    assert text.startswith('{\n  "schema_version": 1,\n  "id": "abc123"')
    assert text.endswith("\n")


def test_deck_inexistente(store: JsonStore) -> None:
    with pytest.raises(DeckNotFoundError):
        store.load_deck("nada00")


def test_arquivo_corrompido_vira_storage_error(store: JsonStore) -> None:
    path = store.paths.deck_file("ruim00")
    path.parent.mkdir(parents=True)
    path.write_text("{ quebrado", encoding="utf-8")
    with pytest.raises(StorageError):
        store.load_deck("ruim00")


def test_escrita_atomica_preserva_original_se_falhar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "f.json"
    write_json_atomic(path, {"v": 1})

    def explode(*_: Any) -> None:
        raise OSError("disco cheio")

    monkeypatch.setattr(json_store.os, "replace", explode)
    with pytest.raises(OSError):
        write_json_atomic(path, {"v": 2})
    assert json.loads(path.read_text()) == {"v": 1}
    assert [p.name for p in tmp_path.iterdir()] == ["f.json"]


def test_historico_so_acrescenta(store: JsonStore) -> None:
    store.append_event("abc123", {"type": "review", "id": "r1"})
    store.append_event("abc123", {"type": "undo", "review_id": "r1"})
    path = store.paths.reviews_file("abc123")
    with path.open("a", encoding="utf-8") as fh:
        fh.write('{"type": "rev')  # linha cortada no meio
    events = store.read_events("abc123")
    assert [e["type"] for e in events] == ["review", "undo"]


def test_apagar_deck_remove_historico(store: JsonStore) -> None:
    store.save_deck(Deck(id="abc123", name="Python", created_at=T0))
    store.append_event("abc123", {"type": "review"})
    store.delete_deck("abc123")
    assert store.deck_ids() == []
    assert store.read_events("abc123") == []


def test_settings_padrao_e_persistencia(store: JsonStore) -> None:
    assert store.load_settings() == Settings()
    store.save_settings(Settings(show_help=False))
    assert store.load_settings().show_help is False


def test_migracao_de_schema(store: JsonStore, monkeypatch: pytest.MonkeyPatch) -> None:
    store.save_deck(Deck(id="abc123", name="velho", created_at=T0))

    def v1_para_v2(data: dict[str, Any]) -> dict[str, Any]:
        data["name"] = data["name"].upper()
        return data

    monkeypatch.setitem(migrations.CURRENT_VERSIONS, "deck", 2)
    monkeypatch.setitem(migrations.MIGRATIONS, "deck", {1: v1_para_v2})
    assert store.load_deck("abc123").name == "VELHO"


def test_schema_mais_novo_e_recusado(store: JsonStore) -> None:
    path = store.paths.deck_file("abc123")
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"schema_version": 99, "id": "abc123"}), encoding="utf-8")
    with pytest.raises(StorageError, match="mais nova"):
        store.load_deck("abc123")


def _segura_trava(root: str, ready: Any, release: Any) -> None:
    store = JsonStore(DataPaths(Path(root)))
    with store.deck_lock("abc123"):
        ready.set()
        release.wait(5)


def test_trava_entre_processos(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = multiprocessing.get_context("spawn")
    ready, release = ctx.Event(), ctx.Event()
    root = tmp_path / "data"
    proc = ctx.Process(target=_segura_trava, args=(str(root), ready, release))
    proc.start()
    try:
        assert ready.wait(10)
        monkeypatch.setattr(json_store, "LOCK_TIMEOUT_SECONDS", 0.2)
        other = JsonStore(DataPaths(root))
        start = time.monotonic()
        with pytest.raises(TimeoutError), other.deck_lock("abc123"):
            pass
        assert time.monotonic() - start >= 0.2
    finally:
        release.set()
        proc.join(10)
    with JsonStore(DataPaths(root)).deck_lock("abc123"):
        pass
    assert os.path.isdir(root / ".locks")


def test_migra_settings_v1_para_v2_preservando_teclas(store: JsonStore) -> None:
    path = store.paths.settings_file
    path.parent.mkdir(parents=True, exist_ok=True)
    v1 = {
        "schema_version": 1,
        "keys": {"great": "j", "partial": "k", "forgot": "l", "reveal": "space", "undo": "w"},
        "show_help": False,
        "new_cards_per_day": 10,
    }
    path.write_text(json.dumps(v1), encoding="utf-8")
    settings = store.load_settings()
    assert settings.keys["great"] == "j"
    assert settings.keys["undo"] == "w"
    assert settings.keys["back"] == "escape"
    # "w" já era Desfazer, então rolar para cima fica sem tecla.
    assert settings.keys["scroll_up"] is None
    assert settings.keys["scroll_down"] is None
    assert settings.show_help is False
    assert settings.new_cards_per_day == 10
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["schema_version"] == 2


def test_migra_settings_v1_com_padroes(store: JsonStore) -> None:
    path = store.paths.settings_file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")
    assert store.load_settings() == Settings()
