"""Editor de card: o mesmo para criar e para editar."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Input, Label, Select, Static, TextArea

from code_cards import languages
from code_cards.errors import CodeCardsError
from code_cards.models import Card
from code_cards.services.cards import CardDraft
from code_cards.tui.widgets.code_view import code_area
from code_cards.tui.widgets.confirm_modal import ConfirmModal
from code_cards.tui.widgets.help_bar import HelpBar

if TYPE_CHECKING:
    from code_cards.tui.app import CodeCardsApp


@dataclass(frozen=True)
class _Snapshot:
    deck_id: str
    language: str
    code: str
    description: str
    tags: str


def parse_tags(text: str) -> list[str]:
    return [t.strip() for t in text.split(",") if t.strip()]


class CardEditorScreen(Screen[bool]):
    """Devolve ``True`` se o card foi salvo."""

    BINDINGS = [
        Binding("ctrl+s", "save", "Salvar", priority=True),
        Binding("escape", "cancel", "Cancelar", priority=True),
        Binding("ctrl+down", "app.focus_next", "Próximo campo", priority=True, show=False),
        Binding("ctrl+up", "app.focus_previous", "Campo anterior", priority=True, show=False),
    ]

    def __init__(self, *, deck_id: str | None = None, card_id: str | None = None) -> None:
        super().__init__()
        self.initial_deck_id = deck_id
        self.card_id = card_id
        self.card: Card | None = None
        self._initial: _Snapshot | None = None

    @property
    def cc_app(self) -> CodeCardsApp:
        return cast("CodeCardsApp", self.app)

    @property
    def is_new(self) -> bool:
        return self.card_id is None

    def compose(self) -> ComposeResult:
        services = self.cc_app.services
        decks = services.decks.list()
        deck_id = self.initial_deck_id
        language = languages.DEFAULT_LANGUAGE
        code = description = tags = ""
        if self.card_id is not None:
            deck, card = services.cards.find(self.card_id)
            self.card = card
            deck_id = deck.id
            language = card.language
            code, description, tags = card.code, card.description, ", ".join(card.tags)
        if deck_id is None and decks:
            deck_id = decks[0].id

        language_options = [(lang.label, lang.id) for lang in languages.choices()]
        if not languages.is_known(language):
            language_options.append((f"{language} (sem highlight)", language))

        title = "Novo card" if self.is_new else "Editar card"
        yield Static(title, id="app-title")
        with Horizontal(id="editor-selects"):
            with Vertical():
                yield Label("Deck")
                yield Select(
                    [(d.name, d.id) for d in decks],
                    value=deck_id if deck_id is not None else Select.BLANK,
                    allow_blank=False,
                    id="deck-select",
                )
            with Vertical():
                yield Label("Linguagem")
                yield Select(
                    language_options, value=language, allow_blank=False, id="language-select"
                )
        yield code_area(
            code,
            language,
            theme=self.cc_app.settings.editor_theme,
            id="code-editor",
        )
        yield TextArea(description, id="description-editor", soft_wrap=True)
        yield Input(tags, placeholder="tags separadas por vírgula", id="tags-input")
        yield HelpBar(
            [
                ("ctrl+s", "salvar"),
                ("escape", "cancelar"),
                ("ctrl+down", "próximo campo"),
                ("ctrl+up", "campo anterior"),
            ],
            id="help",
        )

    def on_mount(self) -> None:
        self.query_one("#code-editor", TextArea).border_title = "código"
        self.query_one("#description-editor", TextArea).border_title = "descrição"
        self.query_one("#tags-input", Input).border_title = "tags"
        self.query_one(HelpBar).set_enabled(self.cc_app.settings.show_help)
        self._initial = self._snapshot()
        self.query_one("#code-editor", TextArea).focus()

    # -- estado ---------------------------------------------------------------

    def _snapshot(self) -> _Snapshot:
        deck_value = self.query_one("#deck-select", Select).value
        language_value = self.query_one("#language-select", Select).value
        return _Snapshot(
            deck_id=deck_value if isinstance(deck_value, str) else "",
            language=language_value if isinstance(language_value, str) else "",
            code=self.query_one("#code-editor", TextArea).text,
            description=self.query_one("#description-editor", TextArea).text,
            tags=self.query_one("#tags-input", Input).value,
        )

    @property
    def is_dirty(self) -> bool:
        return self._initial is not None and self._snapshot() != self._initial

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "language-select" and isinstance(event.value, str):
            self.query_one("#code-editor", TextArea).language = languages.highlight_for(event.value)

    # -- ações ----------------------------------------------------------------

    def action_save(self) -> None:
        current = self._snapshot()
        if not current.deck_id:
            self.notify("Crie um deck antes de adicionar cards.", severity="error")
            return
        services = self.cc_app.services
        try:
            if self.card_id is None:
                _, _, warnings = services.cards.add(
                    current.deck_id,
                    CardDraft(
                        code=current.code,
                        description=current.description,
                        language=current.language,
                        tags=parse_tags(current.tags),
                    ),
                )
                self.notify("Card criado.")
            else:
                _, _, warnings = services.cards.edit(
                    self.card_id,
                    code=current.code,
                    description=current.description,
                    language=current.language,
                    tags=parse_tags(current.tags),
                    deck_ref=current.deck_id,
                )
                self.notify("Card salvo.")
        except CodeCardsError as exc:
            self.notify(exc.message, severity="error", timeout=6)
            return
        for warning in warnings:
            self.notify(warning["message"], severity="warning")
        self.dismiss(True)

    def action_cancel(self) -> None:
        if not self.is_dirty:
            self.dismiss(False)
            return

        def after(confirmed: bool | None) -> None:
            if confirmed:
                self.dismiss(False)

        self.app.push_screen(
            ConfirmModal("Descartar as alterações deste card?", confirm_label="Descartar"),
            after,
        )
