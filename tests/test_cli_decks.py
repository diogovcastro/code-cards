from __future__ import annotations

from pathlib import Path

from tests.cli_helpers import run


def test_where_usa_code_cards_home(data_home: Path) -> None:
    code, out = run("where")
    assert code == 0
    assert out["ok"] is True
    assert out["data"]["path"] == str(data_home.resolve())
    assert out["data"]["source"] == "env"
    assert out["warnings"] == []


def test_version() -> None:
    code, out = run("--version")
    assert code == 0
    assert out["data"]["version"]


def test_ciclo_de_deck() -> None:
    code, out = run("deck", "create", "Python async")
    assert code == 0
    deck = out["data"]["deck"]
    assert deck["name"] == "Python async"
    assert deck["cards"] == 0
    assert deck["available"] == 100

    code, out = run("deck", "list")
    assert code == 0
    assert [d["id"] for d in out["data"]["decks"]] == [deck["id"]]
    assert out["data"]["decks"][0]["new_today"] == 0

    code, out = run("deck", "rename", "python ASYNC", "Asyncio")
    assert code == 0
    assert out["data"]["deck"]["name"] == "Asyncio"

    code, out = run("deck", "delete", deck["id"], "--yes")
    assert code == 0
    assert out["data"] == {"deck_id": deck["id"], "name": "Asyncio", "deleted_cards": 0}


def test_deck_duplicado_sai_com_4() -> None:
    run("deck", "create", "Python")
    code, out = run("deck", "create", "python")
    assert code == 4
    assert out["ok"] is False
    assert out["error"]["code"] == "DECK_EXISTS"


def test_deck_inexistente_sai_com_3() -> None:
    code, out = run("deck", "rename", "nada", "x")
    assert code == 3
    assert out["error"]["code"] == "DECK_NOT_FOUND"


def test_apagar_sem_yes_falha_sem_perguntar() -> None:
    run("deck", "create", "Python")
    code, out = run("deck", "delete", "Python")
    assert code == 2
    assert out["error"]["code"] == "CONFIRMATION_REQUIRED"
    _, listed = run("deck", "list")
    assert len(listed["data"]["decks"]) == 1


def test_nome_vazio_sai_com_2() -> None:
    code, out = run("deck", "create", "  ")
    assert code == 2
    assert out["error"]["code"] == "VALIDATION_ERROR"


def test_erro_de_uso_tambem_e_json() -> None:
    code, out = run("deck", "create")
    assert code == 2
    assert out["error"]["code"] == "VALIDATION_ERROR"
    code, out = run("comando-inexistente")
    assert code == 2
    assert out["ok"] is False


def test_grupo_sem_subcomando_mostra_ajuda() -> None:
    from code_cards.cli.app import app
    from tests.cli_helpers import runner

    result = runner.invoke(app, ["deck"])
    assert result.exit_code == 0
    assert "create" in result.stdout
