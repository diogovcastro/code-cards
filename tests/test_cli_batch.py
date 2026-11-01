from __future__ import annotations

import json
from pathlib import Path

from code_cards.cli.app import app
from code_cards.services.importer import BATCH_SCHEMA
from tests.cli_helpers import run, runner


def batch(n: int, deck: str = "Python async", create: bool = True) -> dict:
    return {
        "deck": deck,
        "create_deck_if_missing": create,
        "cards": [{"code": f"x = {i}", "description": f"atribui {i}"} for i in range(n)],
    }


def test_import_de_arquivo(tmp_path: Path) -> None:
    path = tmp_path / "lote.json"
    path.write_text(json.dumps(batch(10)), encoding="utf-8")
    code, out = run("import", str(path))
    assert code == 0, out
    assert out["data"]["deck_created"] is True
    assert len(out["data"]["card_ids"]) == 10
    _, listed = run("deck", "list")
    assert listed["data"]["decks"][0]["cards"] == 10
    assert listed["data"]["decks"][0]["new_today"] == 10


def test_import_via_stdin() -> None:
    code, out = run("import", "-", input=json.dumps(batch(2)))
    assert code == 0, out
    assert len(out["data"]["card_ids"]) == 2


def test_import_tudo_ou_nada() -> None:
    run("import", "-", input=json.dumps(batch(95)))
    code, out = run("import", "-", input=json.dumps(batch(10, create=False)))
    assert code == 4
    assert out["error"]["code"] == "DECK_FULL"
    assert out["error"]["details"]["available"] == 5
    _, listed = run("deck", "list")
    assert listed["data"]["decks"][0]["cards"] == 95


def test_json_invalido() -> None:
    code, out = run("import", "-", input="{ nada")
    assert code == 2
    assert out["error"]["code"] == "VALIDATION_ERROR"
    assert out["error"]["details"]["line"] == 1


def test_lote_invalido_lista_erros() -> None:
    code, out = run("import", "-", input=json.dumps({"deck": "x", "cards": [{"code": "a"}]}))
    assert code == 2
    assert out["error"]["details"]["errors"][0]["path"] == "$.cards[0].description"


def test_deck_inexistente() -> None:
    code, out = run("import", "-", input=json.dumps(batch(1, create=False)))
    assert code == 3
    assert out["error"]["code"] == "DECK_NOT_FOUND"


def test_schema() -> None:
    code, out = run("schema")
    assert code == 0
    assert out["data"]["schema"] == BATCH_SCHEMA
    result = runner.invoke(app, ["schema", "--raw"])
    assert json.loads(result.stdout) == BATCH_SCHEMA
