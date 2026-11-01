"""Tela de estudo: mostra o código, revela a descrição e recebe a nota."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, cast

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Static, TextArea

from code_cards.errors import CardNotFoundError, CodeCardsError, DeckNotFoundError
from code_cards.models import ACTIONS, Grade, Settings
from code_cards.scheduling import format_interval
from code_cards.services.study import StudyItem, StudyService
from code_cards.tui.widgets.code_view import code_area, show_code
from code_cards.tui.widgets.help_bar import HelpBar

if TYPE_CHECKING:
    from code_cards.tui.app import CodeCardsApp

GRADE_ORDER = (Grade.GREAT, Grade.PARTIAL, Grade.FORGOT)


class StudyScreen(Screen[None]):
    BINDINGS = [
        Binding("escape", "back", "Voltar"),
        Binding("question_mark", "toggle_help", "Ajuda", show=False),
    ]

    def __init__(self, deck_id: str) -> None:
        super().__init__()
        self.deck_id = deck_id
        self.item: StudyItem | None = None
        self.revealed = False
        self.settings: Settings = Settings()
        self.study: StudyService | None = None

    @property
    def cc_app(self) -> CodeCardsApp:
        return cast("CodeCardsApp", self.app)

    def compose(self) -> ComposeResult:
        with Horizontal(id="study-header"):
            yield Static(id="deck-name")
            yield Static(id="counts")
        yield code_area(read_only=True, id="code", theme=self.cc_app.settings.editor_theme)
        with VerticalScroll(id="description-box"):
            yield Static(id="description")
        yield Static(id="done")
        yield HelpBar(id="help")

    def on_mount(self) -> None:
        services = self.cc_app.services
        # A pilha de desfazer vale para esta sessão de estudo.
        self.study = StudyService(services.store, services.settings, services.clock)
        self.settings = services.settings.get()
        self.query_one("#code", TextArea).border_title = "código"
        self.query_one("#description-box").border_title = "descrição"
        self.query_one(HelpBar).set_enabled(self.settings.show_help)
        self.load_next()

    # -- estado ---------------------------------------------------------------

    def _service(self) -> StudyService:
        assert self.study is not None
        return self.study

    def _key_to_action(self) -> dict[str, str]:
        return {key: action for action, key in self.settings.keys.items()}

    def update_header(self) -> None:
        try:
            deck = self.cc_app.services.store.load_deck(self.deck_id)
        except DeckNotFoundError:
            return
        summary = self._service().summary(deck)
        self.query_one("#deck-name", Static).update(Text(deck.name, style="bold"))
        counts = Text()
        counts.append("Novos ", style="dim")
        counts.append(str(summary.new), style="cyan")
        counts.append(" · Revisar ", style="dim")
        counts.append(str(summary.due), style="green")
        self.query_one("#counts", Static).update(counts)

    def load_next(self) -> None:
        try:
            item = self._service().next_card(self.deck_id)
        except DeckNotFoundError:
            self.notify("O deck não existe mais.", severity="error")
            self.app.pop_screen()
            return
        self.show_item(item)

    def show_item(self, item: StudyItem | None) -> None:
        self.item = item
        self.revealed = False
        self.update_header()
        code = self.query_one("#code", TextArea)
        desc_box = self.query_one("#description-box")
        done = self.query_one("#done", Static)
        if item is None:
            code.display = False
            desc_box.display = False
            done.display = True
            done.update(self._done_text())
            self._set_help([("escape", "voltar")])
            return
        done.display = False
        code.display = True
        desc_box.display = False
        show_code(code, item.card.code, item.card.language)
        code.focus()
        self.query_one("#description", Static).update(Text(item.card.description))
        self._set_help([(self.settings.keys["reveal"], "mostrar descrição"), ("escape", "voltar")])

    def _done_text(self) -> Text:
        text = Text("Deck concluído por hoje!\n\n", style="bold green")
        next_due = self._service().next_due(self.deck_id)
        if next_due is None:
            text.append("Não há revisões agendadas.", style="dim")
        else:
            text.append("Próxima revisão: ", style="dim")
            text.append(self._format_local(next_due), style="bold")
        return text

    def _format_local(self, when: datetime) -> str:
        local = when.astimezone(self.cc_app.services.clock.local_tz())
        now = self.cc_app.services.clock.now().astimezone(local.tzinfo)
        delta = format_interval(when - self.cc_app.services.clock.now())
        if local.date() == now.date():
            return f"hoje às {local:%H:%M} (em {delta})"
        return f"{local:%d/%m/%Y às %H:%M} (em {delta})"

    def _set_help(self, items: list[tuple[str, str]], separator: str = " · ") -> None:
        self.query_one(HelpBar).set_items(items, separator=separator)

    # -- ações ----------------------------------------------------------------

    def reveal(self) -> None:
        if self.item is None or self.revealed:
            return
        self.revealed = True
        self.query_one("#description-box").display = True
        keys = self.settings.keys
        items = [
            (keys[grade.value], f"{grade.label} · {format_interval(self.item.previews[grade])}")
            for grade in GRADE_ORDER
        ]
        items.append((keys["undo"], "desfazer"))
        self._set_help(items, separator="    ")

    def answer(self, grade: Grade) -> None:
        if self.item is None or not self.revealed:
            return
        try:
            self._service().answer(self.deck_id, self.item.card.id, grade)
        except CardNotFoundError:
            self.notify("Esse card foi apagado em outro lugar; pulando.", severity="warning")
        except CodeCardsError as exc:
            self.notify(exc.message, severity="error")
            return
        self.load_next()

    def undo(self) -> None:
        service = self._service()
        if not service.can_undo:
            self.notify("Nada para desfazer.", timeout=2)
            return
        try:
            deck_id, card_id = service.undo()
            item = service.item_for(deck_id, card_id)
        except CodeCardsError as exc:
            self.notify(exc.message, severity="error")
            self.load_next()
            return
        self.show_item(item)

    def on_key(self, event: events.Key) -> None:
        action = self._key_to_action().get(event.key)
        if action is None or action not in ACTIONS:
            return
        event.stop()
        event.prevent_default()
        if action == "reveal":
            self.reveal()
        elif action == "undo":
            self.undo()
        else:
            self.answer(Grade(action))

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_toggle_help(self) -> None:
        self.query_one(HelpBar).toggle()
