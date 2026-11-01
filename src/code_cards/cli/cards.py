"""Comandos ``code-cards card ...``."""

from __future__ import annotations

import sys
from typing import Annotated

import typer

from code_cards import languages
from code_cards.cli.common import card_view, deck_view, read_text_file, require_yes, services
from code_cards.cli.output import emit_ok
from code_cards.errors import ValidationError
from code_cards.services.cards import CardDraft, slice_lines

card_app = typer.Typer(help="Adiciona, lista, mostra, edita e apaga cards.", no_args_is_help=True)

CardId = Annotated[str, typer.Argument(help="Id do card (8 caracteres).")]
CodeOpt = Annotated[
    str | None, typer.Option("--code", help="Código do card. Use '-' para ler do stdin.")
]
CodeFileOpt = Annotated[
    str | None,
    typer.Option("--code-file", help="Arquivo com o código ('-' = stdin). Detecta a linguagem."),
]
LinesOpt = Annotated[
    str | None,
    typer.Option("--lines", help="Recorta linhas do código, ex.: 10-40, 10- ou 12."),
]
DescriptionOpt = Annotated[str | None, typer.Option("--description", help="Descrição do card.")]
DescriptionFileOpt = Annotated[
    str | None,
    typer.Option("--description-file", help="Arquivo com a descrição ('-' = stdin)."),
]
LanguageOpt = Annotated[
    str | None,
    typer.Option("--language", help="Linguagem do código (padrão: pela extensão, ou python)."),
]
TagOpt = Annotated[
    list[str] | None, typer.Option("--tag", help="Tag do card. Pode repetir a opção.")
]


class _Stdin:
    """Garante que o stdin seja lido no máximo uma vez por comando."""

    def __init__(self) -> None:
        self.used_by: str | None = None

    def read(self, option: str) -> str:
        if self.used_by is not None:
            raise ValidationError(
                f"{self.used_by} e {option} não podem ler do stdin ao mesmo tempo.",
                {"options": [self.used_by, option]},
            )
        self.used_by = option
        return sys.stdin.read()


def _read_file(path: str, option: str, stdin: _Stdin) -> str:
    return stdin.read(option) if path == "-" else read_text_file(path, option)


def _resolve_code(
    code: str | None, code_file: str | None, lines: str | None, stdin: _Stdin
) -> tuple[str | None, str | None]:
    """Devolve ``(código, linguagem_detectada)``."""
    if code is not None and code_file is not None:
        raise ValidationError("Use --code ou --code-file, não os dois.", {"field": "code"})
    detected: str | None = None
    text: str | None
    if code_file is not None:
        text = _read_file(code_file, "--code-file", stdin)
        if code_file != "-":
            detected = languages.detect_from_filename(code_file)
    elif code == "-":
        text = stdin.read("--code")
    else:
        text = code
    if lines is not None:
        if text is None:
            raise ValidationError("--lines precisa de --code ou --code-file.", {"field": "lines"})
        text = slice_lines(text, lines)
    return text, detected


def _resolve_description(
    description: str | None, description_file: str | None, stdin: _Stdin
) -> str | None:
    if description is not None and description_file is not None:
        raise ValidationError(
            "Use --description ou --description-file, não os dois.", {"field": "description"}
        )
    if description_file is not None:
        return _read_file(description_file, "--description-file", stdin)
    return description


@card_app.command("add")
def card_add(
    deck: Annotated[str, typer.Option("--deck", help="Nome ou id do deck.")],
    code: CodeOpt = None,
    code_file: CodeFileOpt = None,
    lines: LinesOpt = None,
    description: DescriptionOpt = None,
    description_file: DescriptionFileOpt = None,
    language: LanguageOpt = None,
    tag: TagOpt = None,
) -> None:
    """Adiciona um card a um deck."""
    stdin = _Stdin()
    text, detected = _resolve_code(code, code_file, lines, stdin)
    desc = _resolve_description(description, description_file, stdin)
    if text is None:
        raise ValidationError("Informe o código com --code ou --code-file.", {"field": "code"})
    if desc is None:
        raise ValidationError(
            "Informe a descrição com --description ou --description-file.",
            {"field": "description"},
        )
    svc = services()
    target, card, warnings = svc.cards.add(
        deck,
        CardDraft(code=text, description=desc, language=language or detected, tags=tag or []),
    )
    view = card_view(target, card, svc.study)
    emit_ok({"deck_id": target.id, "card_ids": [card.id], "card": view}, warnings)


@card_app.command("list")
def card_list(
    deck: Annotated[
        str | None, typer.Option("--deck", help="Nome ou id do deck (padrão: todos).")
    ] = None,
) -> None:
    """Lista os cards de um deck (ou de todos)."""
    svc = services()
    decks = [svc.decks.get(deck)] if deck is not None else svc.decks.list()
    emit_ok(
        {
            "decks": [deck_view(d) for d in decks],
            "cards": [card_view(d, c, svc.study) for d in decks for c in d.cards],
        }
    )


@card_app.command("show")
def card_show(card_id: CardId) -> None:
    """Mostra um card."""
    svc = services()
    deck, card = svc.cards.find(card_id)
    emit_ok({"card": card_view(deck, card, svc.study)})


@card_app.command("edit")
def card_edit(
    card_id: CardId,
    code: CodeOpt = None,
    code_file: CodeFileOpt = None,
    lines: LinesOpt = None,
    description: DescriptionOpt = None,
    description_file: DescriptionFileOpt = None,
    language: LanguageOpt = None,
    tag: Annotated[
        list[str] | None,
        typer.Option("--tag", help="Substitui as tags do card. Pode repetir a opção."),
    ] = None,
    clear_tags: Annotated[bool, typer.Option("--clear-tags", help="Remove todas as tags.")] = False,
    deck: Annotated[
        str | None, typer.Option("--deck", help="Move o card para este deck (nome ou id).")
    ] = None,
) -> None:
    """Edita um card. Só os campos informados mudam; --deck move o card."""
    if tag and clear_tags:
        raise ValidationError("Use --tag ou --clear-tags, não os dois.", {"field": "tags"})
    stdin = _Stdin()
    text, detected = _resolve_code(code, code_file, lines, stdin)
    desc = _resolve_description(description, description_file, stdin)
    tags: list[str] | None = [] if clear_tags else (tag or None)
    svc = services()
    target, card, warnings = svc.cards.edit(
        card_id,
        code=text,
        description=desc,
        language=language or detected,
        tags=tags,
        deck_ref=deck,
    )
    emit_ok({"card": card_view(target, card, svc.study)}, warnings)


@card_app.command("delete")
def card_delete(
    card_id: CardId,
    yes: Annotated[bool, typer.Option("--yes", help="Confirma a remoção.")] = False,
) -> None:
    """Apaga um card. Exige --yes."""
    svc = services()
    svc.cards.find(card_id)
    require_yes(yes, f"o card '{card_id}'")
    deck, card = svc.cards.delete(card_id)
    emit_ok({"deck_id": deck.id, "card_id": card.id})
