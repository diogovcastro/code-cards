"""Envelope JSON e códigos de saída da CLI.

Sucesso::

    {"ok": true, "data": {...}, "warnings": []}

Erro::

    {"ok": false, "error": {"code": "DECK_FULL", "message": "...", "details": {...}}}
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from typing import Any

from typer.core import TyperGroup

from code_cards.errors import CodeCardsError

EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_VALIDATION = 2
EXIT_NOT_FOUND = 3
EXIT_CONFLICT = 4

EXIT_CODES: dict[str, int] = {
    "VALIDATION_ERROR": EXIT_VALIDATION,
    "CONFIRMATION_REQUIRED": EXIT_VALIDATION,
    "DECK_NOT_FOUND": EXIT_NOT_FOUND,
    "CARD_NOT_FOUND": EXIT_NOT_FOUND,
    "DECK_FULL": EXIT_CONFLICT,
    "DECK_EXISTS": EXIT_CONFLICT,
    "NOTHING_TO_UNDO": EXIT_CONFLICT,
}


def exit_code_for(error_code: str) -> int:
    return EXIT_CODES.get(error_code, EXIT_INTERNAL)


def _write(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    sys.stdout.flush()


def emit_ok(data: Any, warnings: Sequence[dict[str, Any]] | None = None) -> None:
    _write({"ok": True, "data": data, "warnings": list(warnings or [])})


def emit_error(code: str, message: str, details: dict[str, Any] | None = None) -> int:
    _write({"ok": False, "error": {"code": code, "message": message, "details": details or {}}})
    return exit_code_for(code)


def _is_click_exception(exc: BaseException) -> bool:
    # O Typer embute o Click; checar pelo formato evita depender do módulo privado.
    return hasattr(exc, "format_message") and hasattr(exc, "exit_code")


class JsonTyperGroup(TyperGroup):
    """Grupo raiz que transforma qualquer erro em envelope JSON + código de saída."""

    def main(  # type: ignore[override]
        self,
        args: Sequence[str] | None = None,
        prog_name: str | None = None,
        complete_var: str | None = None,
        standalone_mode: bool = True,
        windows_expand_args: bool = True,
        **extra: Any,
    ) -> Any:
        try:
            rv = super().main(
                args=args,
                prog_name=prog_name,
                complete_var=complete_var,
                standalone_mode=False,
                windows_expand_args=windows_expand_args,
                **extra,
            )
            code = rv if isinstance(rv, int) else EXIT_OK
        except CodeCardsError as exc:
            code = emit_error(exc.code, exc.message, exc.details)
        except Exception as exc:
            if type(exc).__name__ == "NoArgsIsHelpError":
                # Grupo chamado sem subcomando: a ajuda já foi exibida.
                code = EXIT_OK
            elif _is_click_exception(exc):
                code = emit_error(
                    "VALIDATION_ERROR",
                    exc.format_message(),  # type: ignore[attr-defined]
                    {"usage": True},
                )
            elif type(exc).__name__ == "Abort":
                code = emit_error("ABORTED", "Operação interrompida.")
            else:
                code = emit_error(
                    "INTERNAL_ERROR",
                    f"Erro interno: {exc}",
                    {"type": type(exc).__name__},
                )
        if standalone_mode:
            sys.exit(code)
        return code
