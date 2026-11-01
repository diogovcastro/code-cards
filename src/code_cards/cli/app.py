"""CLI do code-cards (Typer)."""

from __future__ import annotations

import typer

from code_cards import __version__

app = typer.Typer(
    name="code-cards",
    help="Flash cards de código com repetição espaçada. Sem argumentos, abre a TUI.",
    no_args_is_help=False,
    add_completion=False,
)


@app.callback(invoke_without_command=True)
def _root(
    version: bool = typer.Option(False, "--version", help="Mostra a versão e sai."),
) -> None:
    if version:
        typer.echo(__version__)
        raise typer.Exit()


def run_cli(args: list[str]) -> None:
    app(args=args, prog_name="code-cards")
