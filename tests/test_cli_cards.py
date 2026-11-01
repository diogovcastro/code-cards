from __future__ import annotations

from pathlib import Path

import pytest

from code_cards.services.container import build_services
from tests.cli_helpers import run


@pytest.fixture
def deck_id() -> str:
    _, out = run("deck", "create", "Python async")
    return out["data"]["deck"]["id"]


def test_add_por_parametros(deck_id: str) -> None:
    code, out = run(
        "card", "add", "--deck", "python async",
        "--code", "await asyncio.sleep(1)",
        "--description", "Pausa a corrotina por 1s.",
        "--tag", "asyncio", "--tag", "básico",
    )  # fmt: skip
    assert code == 0, out
    assert out["data"]["deck_id"] == deck_id
    card = out["data"]["card"]
    assert out["data"]["card_ids"] == [card["id"]]
    assert card["language"] == "python"
    assert card["highlight"] is True
    assert card["tags"] == ["asyncio", "básico"]
    assert card["is_new"] is True
    assert card["due"] is None


def test_add_por_arquivo_com_linhas(deck_id: str, tmp_path: Path) -> None:
    src = tmp_path / "app.py"
    src.write_text("import x\n\nclass A:\n    def f(self):\n        return 1\n", encoding="utf-8")
    desc = tmp_path / "desc.md"
    desc.write_text("Método que devolve 1.\n", encoding="utf-8")
    code, out = run(
        "card", "add", "--deck", deck_id, "--code-file", str(src), "--lines", "4-5",
        "--description-file", str(desc),
    )  # fmt: skip
    assert code == 0, out
    assert out["data"]["card"]["code"] == "def f(self):\n    return 1"
    assert out["data"]["card"]["description"] == "Método que devolve 1."


def test_add_codigo_via_stdin(deck_id: str) -> None:
    code, out = run(
        "card", "add", "--deck", deck_id, "--code", "-", "--description", "soma",
        input="a + b\n",
    )  # fmt: skip
    assert code == 0, out
    assert out["data"]["card"]["code"] == "a + b"


def test_stdin_duas_vezes_e_erro(deck_id: str) -> None:
    code, out = run(
        "card", "add", "--deck", deck_id, "--code", "-", "--description-file", "-", input="x"
    )
    assert code == 2
    assert out["error"]["code"] == "VALIDATION_ERROR"


def test_linguagem_desconhecida_gera_aviso(deck_id: str, tmp_path: Path) -> None:
    src = tmp_path / "main.rs"
    src.write_text("fn main() {}", encoding="utf-8")
    code, out = run(
        "card", "add", "--deck", deck_id, "--code-file", str(src),
        "--description", "main vazia", "--language", "rust",
    )  # fmt: skip
    assert code == 0
    assert out["data"]["card"]["highlight"] is False
    assert [w["code"] for w in out["warnings"]] == ["UNKNOWN_LANGUAGE"]


def test_add_sem_descricao(deck_id: str) -> None:
    code, out = run("card", "add", "--deck", deck_id, "--code", "x")
    assert code == 2
    assert "descrição" in out["error"]["message"]


def test_arquivo_inexistente(deck_id: str) -> None:
    code, out = run(
        "card", "add", "--deck", deck_id, "--code-file", "/nao/existe.py", "--description", "d"
    )
    assert code == 2
    assert "não encontrado" in out["error"]["message"]


def test_deck_cheio_sai_com_4(deck_id: str) -> None:
    batch = {"deck": deck_id, "cards": [{"code": f"x={i}", "description": "d"} for i in range(100)]}
    build_services().importer.import_batch(batch)
    code, out = run("card", "add", "--deck", deck_id, "--code", "y", "--description", "d")
    assert code == 4
    assert out["error"]["code"] == "DECK_FULL"
    assert out["error"]["details"] == {"deck_id": deck_id, "available": 0, "requested": 1}


def test_list_show_edit_delete(deck_id: str) -> None:
    _, out = run("card", "add", "--deck", deck_id, "--code", "x = 1", "--description", "um")
    card_id = out["data"]["card"]["id"]

    code, out = run("card", "list", "--deck", deck_id)
    assert code == 0
    assert [c["id"] for c in out["data"]["cards"]] == [card_id]

    code, out = run("card", "show", card_id)
    assert code == 0
    assert out["data"]["card"]["description"] == "um"

    _, other = run("deck", "create", "Outro")
    code, out = run(
        "card", "edit", card_id, "--description", "dois", "--tag", "t", "--deck", "Outro"
    )
    assert code == 0, out
    assert out["data"]["card"]["description"] == "dois"
    assert out["data"]["card"]["tags"] == ["t"]
    assert out["data"]["card"]["deck_id"] == other["data"]["deck"]["id"]

    code, out = run("card", "edit", card_id, "--clear-tags")
    assert out["data"]["card"]["tags"] == []

    code, out = run("card", "delete", card_id)
    assert code == 2
    assert out["error"]["code"] == "CONFIRMATION_REQUIRED"
    code, out = run("card", "delete", card_id, "--yes")
    assert code == 0
    code, out = run("card", "show", card_id)
    assert code == 3
    assert out["error"]["code"] == "CARD_NOT_FOUND"


def test_list_sem_deck_lista_todos(deck_id: str) -> None:
    run("deck", "create", "B")
    run("card", "add", "--deck", deck_id, "--code", "a", "--description", "a")
    run("card", "add", "--deck", "B", "--code", "b", "--description", "b")
    _, out = run("card", "list")
    assert sorted(c["code"] for c in out["data"]["cards"]) == ["a", "b"]
    assert len(out["data"]["decks"]) == 2
