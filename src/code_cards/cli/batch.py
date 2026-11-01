"""Comandos ``code-cards import`` e ``code-cards schema``."""

from __future__ import annotations

import json
import sys
from typing import Annotated, Any

import typer

from code_cards.cli.common import read_text_file, services
from code_cards.cli.output import emit_ok
from code_cards.errors import ValidationError
from code_cards.services.importer import BATCH_SCHEMA


def _load_json(source: str) -> Any:
    if source == "-":
        text = sys.stdin.read()
        origin = "stdin"
    else:
        text = read_text_file(source, "source")
        origin = source
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValidationError(
            f"JSON inválido em {origin}: {exc.msg} (linha {exc.lineno}, coluna {exc.colno}).",
            {"line": exc.lineno, "column": exc.colno},
        ) from exc


def import_command(
    source: Annotated[str, typer.Argument(help="Arquivo JSON do lote, ou '-' para ler do stdin.")],
) -> None:
    """Importa um lote de cards em JSON (tudo ou nada). Veja 'code-cards schema'."""
    result = services().importer.import_batch(_load_json(source))
    emit_ok(
        {
            "deck_id": result.deck_id,
            "deck_name": result.deck_name,
            "deck_created": result.deck_created,
            "card_ids": result.card_ids,
        },
        result.warnings,
    )


def schema_command(
    raw: Annotated[
        bool, typer.Option("--raw", help="Imprime só o JSON Schema, sem o envelope.")
    ] = False,
) -> None:
    """Imprime o JSON Schema do lote de importação."""
    if raw:
        sys.stdout.write(json.dumps(BATCH_SCHEMA, ensure_ascii=False, indent=2) + "\n")
        return
    emit_ok({"schema": BATCH_SCHEMA})
