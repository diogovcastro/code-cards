"""Comandos ``code-cards deck ...``."""

from __future__ import annotations

from typing import Annotated

import typer

from code_cards.cli.common import deck_view, require_yes, services
from code_cards.cli.output import emit_ok

deck_app = typer.Typer(help="Cria, lista, renomeia e apaga decks.", no_args_is_help=True)

DeckRef = Annotated[str, typer.Argument(help="Nome ou id do deck.")]


@deck_app.command("list")
def deck_list() -> None:
    """Lista os decks com o total de cards e o que há para estudar hoje."""
    svc = services()
    emit_ok({"decks": [deck_view(d, svc.study) for d in svc.decks.list()]})


@deck_app.command("create")
def deck_create(name: Annotated[str, typer.Argument(help="Nome do deck (único).")]) -> None:
    """Cria um deck vazio."""
    svc = services()
    deck = svc.decks.create(name)
    emit_ok({"deck": deck_view(deck)})


@deck_app.command("rename")
def deck_rename(
    deck: DeckRef,
    new_name: Annotated[str, typer.Argument(help="Novo nome.")],
) -> None:
    """Renomeia um deck."""
    svc = services()
    renamed = svc.decks.rename(deck, new_name)
    emit_ok({"deck": deck_view(renamed)})


@deck_app.command("delete")
def deck_delete(
    deck: DeckRef,
    yes: Annotated[bool, typer.Option("--yes", help="Confirma a remoção.")] = False,
) -> None:
    """Apaga um deck, seus cards e seu histórico. Exige --yes."""
    svc = services()
    target = svc.decks.get(deck)
    require_yes(yes, f"o deck '{target.name}' e seus {len(target.cards)} cards")
    deleted = svc.decks.delete(target.id)
    emit_ok({"deck_id": deleted.id, "name": deleted.name, "deleted_cards": len(deleted.cards)})
