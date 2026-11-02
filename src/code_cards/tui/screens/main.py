"""Painel principal: lista de decks e ações."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import OptionList, Static

from code_cards.errors import CodeCardsError
from code_cards.tui.screens.card_editor import CardEditorScreen
from code_cards.tui.screens.deck_manager import DeckManagerScreen
from code_cards.tui.screens.settings import SettingsScreen
from code_cards.tui.screens.study import StudyScreen
from code_cards.tui.widgets.confirm_modal import TextPromptModal
from code_cards.tui.widgets.deck_table import DECK_PREFIX, DeckTable, MenuItem
from code_cards.tui.widgets.help_bar import HelpBar

if TYPE_CHECKING:
    from code_cards.tui.app import CodeCardsApp

WELCOME = (
    "Bem-vindo ao code-cards!\n\n"
    "Ainda não há decks. Aperte Enter em [b]Criar deck[/b] para começar, "
    "ou importe um lote pela CLI com [b]code-cards import lote.json[/b]."
)

CREATE_DECK = "create-deck"
ADD_CARD = "add-card"
OPEN_SETTINGS = "settings"


class MainScreen(Screen[None]):
    BINDINGS = [
        Binding("g", "manage", "Gerenciar deck"),
        Binding("q", "app.quit", "Sair"),
        Binding("question_mark", "toggle_help", "Ajuda", show=False),
    ]

    @property
    def cc_app(self) -> CodeCardsApp:
        return cast("CodeCardsApp", self.app)

    def compose(self) -> ComposeResult:
        yield Static("code-cards", id="app-title")
        yield Static(WELCOME, id="welcome")
        yield DeckTable(id="deck-list")
        yield HelpBar(id="help")

    def on_mount(self) -> None:
        self.refresh_decks()

    def on_screen_resume(self) -> None:
        self.refresh_decks()

    def menu_actions(self) -> list[MenuItem]:
        """Ações exibidas abaixo dos decks: ``(id, rótulo)``; ``None`` separa grupos."""
        return [
            (CREATE_DECK, "+ Criar deck"),
            (ADD_CARD, "+ Adicionar card"),
            None,
            (OPEN_SETTINGS, "⚙ Configurações"),
        ]

    def help_items(self) -> list[tuple[str, str]]:
        return [("enter", "estudar"), ("g", "gerenciar deck"), ("q", "sair")]

    def refresh_decks(self) -> None:
        try:
            summaries = self.cc_app.services.study.summaries()
        except CodeCardsError as exc:
            self.notify(exc.message, severity="error", timeout=8)
            summaries = []
        table = self.query_one(DeckTable)
        table.set_content(summaries, self.menu_actions())
        self.query_one("#welcome").display = not summaries
        if not summaries:
            table.highlight_id(CREATE_DECK)
        help_bar = self.query_one(HelpBar)
        help_bar.set_items(self.help_items())
        help_bar.set_enabled(self.cc_app.settings.show_help)
        table.focus()

    def action_toggle_help(self) -> None:
        self.query_one(HelpBar).toggle()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        option_id = event.option.id or ""
        if option_id.startswith(DECK_PREFIX):
            self.open_study(option_id.removeprefix(DECK_PREFIX))
        else:
            self.run_menu_action(option_id)

    def open_study(self, deck_id: str) -> None:
        self.app.push_screen(StudyScreen(deck_id))

    def run_menu_action(self, action_id: str) -> None:
        if action_id == CREATE_DECK:
            self.create_deck()
        elif action_id == ADD_CARD:
            self.add_card()
        elif action_id == OPEN_SETTINGS:
            self.app.push_screen(SettingsScreen())

    def action_manage(self) -> None:
        deck_id = self.query_one(DeckTable).highlighted_deck_id
        if deck_id is None:
            self.notify("Selecione um deck para gerenciar.", timeout=3)
            return
        self.app.push_screen(DeckManagerScreen(deck_id))

    def create_deck(self) -> None:
        def after(name: str | None) -> None:
            if not name:
                return
            try:
                deck = self.cc_app.services.decks.create(name)
            except CodeCardsError as exc:
                self.notify(exc.message, severity="error")
                return
            self.notify(f"Deck '{deck.name}' criado.")
            self.refresh_decks()
            self.query_one(DeckTable).highlight_id(f"{DECK_PREFIX}{deck.id}")

        self.app.push_screen(
            TextPromptModal(
                "Nome do novo deck:", placeholder="Python async", confirm_label="Criar"
            ),
            after,
        )

    def add_card(self) -> None:
        if not self.cc_app.services.store.deck_ids():
            self.notify("Crie um deck antes de adicionar cards.", severity="warning")
            return
        deck_id = self.query_one(DeckTable).highlighted_deck_id
        self.app.push_screen(CardEditorScreen(deck_id=deck_id))
