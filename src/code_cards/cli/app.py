"""CLI do code-cards (Typer). Responde sempre em JSON no stdout."""

from __future__ import annotations

from typing import Annotated

import typer

from code_cards import __version__, paths
from code_cards.cli.decks import deck_app
from code_cards.cli.output import JsonTyperGroup, emit_ok

app = typer.Typer(
    name="code-cards",
    cls=JsonTyperGroup,
    help=(
        "Flash cards de código com repetição espaçada. Sem argumentos, abre a TUI. "
        "Com argumentos, responde sempre em JSON (veja docs/CLI.md)."
    ),
    no_args_is_help=False,
    add_completion=False,
    pretty_exceptions_enable=False,
)
app.add_typer(deck_app, name="deck")


@app.callback(invoke_without_command=True)
def _root(
    version: Annotated[bool, typer.Option("--version", help="Mostra a versão e sai.")] = False,
) -> None:
    if version:
        emit_ok({"version": __version__})
        raise typer.Exit()


@app.command("where")
def where() -> None:
    """Mostra a pasta de dados em uso."""
    root = paths.data_dir()
    emit_ok(
        {
            "path": str(root),
            "source": paths.data_dir_source(),
            "env_var": paths.ENV_VAR,
            "exists": root.is_dir(),
        }
    )


def run_cli(args: list[str]) -> None:
    app(args=args, prog_name="code-cards")
