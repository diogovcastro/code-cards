"""Lista de decks do painel principal (com as ações abaixo dos decks)."""

from __future__ import annotations

import contextlib

from rich.text import Text
from textual.widgets import OptionList
from textual.widgets.option_list import Option, OptionDoesNotExist

from code_cards.models import MAX_CARDS_PER_DECK
from code_cards.services.study import DeckSummary

NAME_WIDTH = 28
DECK_PREFIX = "deck:"


def _fit(name: str, width: int) -> str:
    return name if len(name) <= width else name[: width - 1] + "…"


HEADER_ID = "header"
#: Prefixo dos espaçadores entre grupos de ações (opções vazias e desabilitadas).
SPACER_PREFIX = "spacer:"

#: Ação do painel ``(id, rótulo)``; ``None`` vira uma linha em branco entre grupos.
MenuItem = tuple[str, str] | None


def header_text() -> Text:
    return Text(f"{'Decks':<{NAME_WIDTH}} {'Novos':>6} {'Revisar':>8} {'Cards':>9}", style="bold")


def deck_row(summary: DeckSummary) -> Text:
    text = Text()
    text.append(f"{_fit(summary.name, NAME_WIDTH):<{NAME_WIDTH}} ")
    text.append(f"{summary.new:>6}", style="cyan" if summary.new else "dim")
    text.append(f" {summary.due:>8}", style="green" if summary.due else "dim")
    text.append(f" {summary.total:>5}/{MAX_CARDS_PER_DECK}", style="dim")
    return text


class DeckTable(OptionList):
    """``OptionList`` com cabeçalho, uma linha por deck e, depois, as ações do painel."""

    def set_content(self, summaries: list[DeckSummary], actions: list[MenuItem]) -> None:
        """Reconstrói a lista mantendo o cursor no mesmo item, se possível."""
        previous = self.highlighted_option.id if self.highlighted_option is not None else None
        self.clear_options()
        options: list[Option | None] = []
        if summaries:
            # O cabeçalho é uma opção desabilitada para ficar alinhado com as linhas.
            options.append(Option(header_text(), id=HEADER_ID, disabled=True))
            options.extend(Option(deck_row(s), id=f"{DECK_PREFIX}{s.deck_id}") for s in summaries)
            if actions:
                options.append(None)
        for index, item in enumerate(actions):
            if item is None:
                # Linha em branco entre grupos; o cursor pula opções desabilitadas.
                options.append(Option("", id=f"{SPACER_PREFIX}{index}", disabled=True))
            else:
                action_id, label = item
                options.append(Option(label, id=action_id))
        self.add_options(options)
        if previous is not None:
            try:
                self.highlighted = self.get_option_index(previous)
                return
            except OptionDoesNotExist:
                pass
        for index in range(self.option_count):
            if not self.get_option_at_index(index).disabled:
                self.highlighted = index
                break

    @property
    def highlighted_deck_id(self) -> str | None:
        option = self.highlighted_option
        if option is None or option.id is None or not option.id.startswith(DECK_PREFIX):
            return None
        return option.id.removeprefix(DECK_PREFIX)

    def highlight_id(self, option_id: str) -> None:
        with contextlib.suppress(OptionDoesNotExist):
            self.highlighted = self.get_option_index(option_id)
