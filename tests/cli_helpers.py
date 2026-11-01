from __future__ import annotations

import json
from typing import Any

from typer.testing import CliRunner

from code_cards.cli.app import app

runner = CliRunner()


def run(*args: str, input: str | None = None) -> tuple[int, dict[str, Any]]:
    """Roda a CLI e devolve (código de saída, envelope JSON)."""
    result = runner.invoke(app, list(args), input=input, prog_name="code-cards")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:  # pragma: no cover - ajuda a depurar
        raise AssertionError(f"Saída não é JSON:\n{result.output}") from exc
    return result.exit_code, payload
