"""Ponto de entrada: sem argumentos abre a TUI; com argumentos, a CLI."""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        from code_cards.tui.app import run_tui

        run_tui()
        return

    from code_cards.cli.app import run_cli

    run_cli(args)


if __name__ == "__main__":
    main()
