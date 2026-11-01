"""Gerenciar deck: lista os cards e permite editar, apagar, renomear e criar."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Static

from code_cards.errors import CodeCardsError, DeckNotFoundError
from code_cards.models import MAX_CARDS_PER_DECK, Card, Deck
from code_cards.scheduling import format_interval
from code_cards.tui.screens.card_editor import CardEditorScreen
from code_cards.tui.widgets.confirm_modal import ConfirmModal, TextPromptModal
from code_cards.tui.widgets.help_bar import HelpBar

if TYPE_CHECKING:
    from code_cards.tui.app import CodeCardsApp

CODE_WIDTH = 30
DESCRIPTION_WIDTH = 30


def _clip(text: str, width: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= width else text[: width - 1] + "…"


class DeckManagerScreen(Screen[None]):
    BINDINGS = [
        Binding("escape", "back", "Voltar"),
        Binding("enter", "edit_card", "Editar", show=False, priority=True),
        Binding("delete", "delete_card", "Apagar card"),
        Binding("r", "rename_deck", "Renomear"),
        Binding("x", "delete_deck", "Apagar deck"),
        Binding("n", "new_card", "Novo card"),
        Binding("question_mark", "toggle_help", "Ajuda", show=False),
    ]

    def __init__(self, deck_id: str) -> None:
        super().__init__()
        self.deck_id = deck_id
        self.deck: Deck | None = None

    @property
    def cc_app(self) -> CodeCardsApp:
        return cast("CodeCardsApp", self.app)

    def compose(self) -> ComposeResult:
        yield Static(id="app-title")
        yield Static(id="empty-deck")
        table: DataTable[str | Text] = DataTable(id="card-table", cursor_type="row")
        yield table
        yield HelpBar(
            [
                ("enter", "editar"),
                ("delete", "apagar"),
                ("n", "novo card"),
                ("r", "renomear deck"),
                ("x", "apagar deck"),
                ("escape", "voltar"),
            ],
            id="help",
        )

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_column("Código", width=CODE_WIDTH, key="code")
        table.add_column("Descrição", width=DESCRIPTION_WIDTH, key="description")
        table.add_column("Próxima revisão", key="due")
        self.query_one(HelpBar).set_enabled(self.cc_app.settings.show_help)
        self.reload()

    def on_screen_resume(self) -> None:
        self.reload()

    # -- dados ----------------------------------------------------------------

    def reload(self, select_card: str | None = None) -> None:
        try:
            self.deck = self.cc_app.services.store.load_deck(self.deck_id)
        except DeckNotFoundError:
            self._leave()
            return
        deck = self.deck
        title = Text(deck.name, style="bold")
        title.append(f"  {len(deck.cards)}/{MAX_CARDS_PER_DECK} cards", style="dim")
        self.query_one("#app-title", Static).update(title)

        table = self.query_one(DataTable)
        previous = select_card or self.selected_card_id
        table.clear()
        for card in deck.cards:
            table.add_row(
                _clip(card.first_line, CODE_WIDTH),
                _clip(card.description, DESCRIPTION_WIDTH),
                self._due_text(card),
                key=card.id,
            )
        empty = not deck.cards
        table.display = not empty
        empty_msg = self.query_one("#empty-deck", Static)
        empty_msg.display = empty
        empty_msg.update("Este deck ainda não tem cards. Aperte N para criar o primeiro.")
        if previous is not None:
            for index, card in enumerate(deck.cards):
                if card.id == previous:
                    table.move_cursor(row=index)
                    break
        table.focus()

    def _due_text(self, card: Card) -> Text:
        if card.is_new:
            return Text("novo", style="cyan")
        services = self.cc_app.services
        due = services.study.scheduler().due(card.fsrs)
        now = services.clock.now()
        if due <= now:
            return Text("agora", style="green")
        return Text(f"em {format_interval(due - now)}")

    @property
    def selected_card_id(self) -> str | None:
        table = self.query_one(DataTable)
        if not table.row_count:
            return None
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        return row_key.value

    # -- ações ----------------------------------------------------------------

    def _leave(self) -> None:
        """Volta ao painel uma única vez, mesmo se chamado de mais de um lugar."""
        if self.is_current:
            self.app.pop_screen()

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_toggle_help(self) -> None:
        self.query_one(HelpBar).toggle()

    def action_edit_card(self) -> None:
        card_id = self.selected_card_id
        if card_id is not None:
            self.app.push_screen(CardEditorScreen(card_id=card_id))

    def action_new_card(self) -> None:
        if self.deck is not None and self.deck.available_slots == 0:
            self.notify(
                f"O deck já tem {MAX_CARDS_PER_DECK} cards. Apague ou mova algum antes.",
                severity="warning",
            )
            return
        self.app.push_screen(CardEditorScreen(deck_id=self.deck_id))

    def action_delete_card(self) -> None:
        card_id = self.selected_card_id
        if card_id is None or self.deck is None:
            return
        card = self.deck.find_card(card_id)
        label = _clip(card.first_line, 40) if card else card_id

        def after(confirmed: bool | None) -> None:
            if not confirmed:
                return
            try:
                self.cc_app.services.cards.delete(card_id)
            except CodeCardsError as exc:
                self.notify(exc.message, severity="error")
            else:
                self.notify("Card apagado.")
            self.reload()

        self.app.push_screen(
            ConfirmModal(f"Apagar o card\n{label}?", confirm_label="Apagar", danger=True), after
        )

    def action_rename_deck(self) -> None:
        if self.deck is None:
            return

        def after(name: str | None) -> None:
            if not name:
                return
            try:
                self.cc_app.services.decks.rename(self.deck_id, name)
            except CodeCardsError as exc:
                self.notify(exc.message, severity="error")
            self.reload()

        self.app.push_screen(
            TextPromptModal("Novo nome do deck:", value=self.deck.name, confirm_label="Renomear"),
            after,
        )

    def action_delete_deck(self) -> None:
        if self.deck is None:
            return
        name = self.deck.name

        def after(typed: str | None) -> None:
            if typed is None:
                return
            if typed.casefold() != name.casefold():
                self.notify("O nome não confere; o deck não foi apagado.", severity="warning")
                return
            try:
                self.cc_app.services.decks.delete(self.deck_id)
            except CodeCardsError as exc:
                self.notify(exc.message, severity="error")
                return
            self.notify(f"Deck '{name}' apagado.")
            self._leave()

        self.app.push_screen(
            TextPromptModal(
                f"Isso apaga o deck '{name}', seus {len(self.deck.cards)} cards e o histórico.\n"
                "Digite o nome do deck para confirmar:",
                placeholder=name,
                confirm_label="Apagar deck",
                danger=True,
            ),
            after,
        )
