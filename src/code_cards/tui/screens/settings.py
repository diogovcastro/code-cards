"""Configurações: teclas, ajuda, limites diários, retenção e início do dia.

Cada alteração válida é gravada na hora.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.validation import ValidationResult, Validator
from textual.widgets import Button, Input, Label, Static, Switch

from code_cards.errors import ValidationError
from code_cards.models import ACTION_LABELS, ACTIONS, Settings
from code_cards.services.settings import (
    MAX_PER_DAY,
    MAX_RETENTION,
    MIN_RETENTION,
    display_key,
)
from code_cards.tui.screens.base import ConfigurableBackMixin
from code_cards.tui.widgets.confirm_modal import ConfirmModal
from code_cards.tui.widgets.help_bar import HelpBar

if TYPE_CHECKING:
    pass


def parse_decimal(value: str) -> float:
    return float(value.strip().replace(",", "."))


class RangeValidator(Validator):
    """Aceita números entre ``low`` e ``high`` (vírgula ou ponto como decimal)."""

    def __init__(self, low: float, high: float, *, integer: bool, message: str) -> None:
        super().__init__(failure_description=message)
        self.low = low
        self.high = high
        self.integer = integer

    def validate(self, value: str) -> ValidationResult:
        try:
            number = int(value.strip()) if self.integer else parse_decimal(value)
        except ValueError:
            return self.failure()
        return self.success() if self.low <= number <= self.high else self.failure()


#: campo do Settings → (rótulo, validador, conversão do texto, formatação do valor)
NUMBER_FIELDS: dict[str, tuple[str, Validator, Callable[[str], Any], Callable[[Any], str]]] = {
    "new_cards_per_day": (
        "Cards novos por dia (por deck)",
        RangeValidator(0, MAX_PER_DAY, integer=True, message=f"De 0 a {MAX_PER_DAY}."),
        int,
        str,
    ),
    "reviews_per_day": (
        "Revisões por dia (por deck)",
        RangeValidator(0, MAX_PER_DAY, integer=True, message=f"De 0 a {MAX_PER_DAY}."),
        int,
        str,
    ),
    "desired_retention": (
        "Retenção desejada (0,80 a 0,97)",
        RangeValidator(MIN_RETENTION, MAX_RETENTION, integer=False, message="De 0,80 a 0,97."),
        lambda text: round(parse_decimal(text), 4),
        lambda value: f"{value:.2f}".replace(".", ","),
    ),
    "day_starts_at_hour": (
        "Hora em que o dia de estudo começa",
        RangeValidator(0, 23, integer=True, message="De 0 a 23."),
        int,
        str,
    ),
}


class SettingsScreen(ConfigurableBackMixin, Screen[None]):
    BINDINGS = [
        Binding("escape", "back", "Voltar"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.capturing: str | None = None
        self._loading = False

    @property
    def settings(self) -> Settings:
        return self.cc_app.services.settings.get()

    def compose(self) -> ComposeResult:
        yield Static("Configurações", id="app-title")
        with VerticalScroll(id="settings-body"):
            yield Static("Teclas do estudo", classes="settings-section")
            for action in ACTIONS:
                with Horizontal(classes="settings-row"):
                    yield Label(ACTION_LABELS[action], classes="settings-label")
                    yield Button("", id=f"key-{action}", classes="key-button", compact=True)
            yield Static("Exibição", classes="settings-section")
            with Horizontal(classes="settings-row"):
                yield Label("Barra de ajuda", classes="settings-label")
                yield Switch(id="show-help")
            yield Static("Estudo", classes="settings-section")
            for field, (label, validator, _, _) in NUMBER_FIELDS.items():
                with Horizontal(classes="settings-row"):
                    yield Label(label, classes="settings-label")
                    yield Input(
                        id=f"input-{field}", validators=[validator], classes="number", compact=True
                    )
            with Horizontal(classes="settings-row"):
                yield Button("Restaurar padrões", id="reset", variant="warning")
        yield HelpBar(
            [("enter", "trocar tecla"), ("tab", "próximo campo")],
            id="help",
        )

    def on_mount(self) -> None:
        self.load_values()
        self.query_one("#key-great", Button).focus()

    def load_values(self) -> None:
        settings = self.settings
        self._loading = True
        try:
            for action in ACTIONS:
                self._update_key_button(action, settings.keys[action])
            self.query_one("#show-help", Switch).value = settings.show_help
            for field, (_, _, _, fmt) in NUMBER_FIELDS.items():
                self.query_one(f"#input-{field}", Input).value = fmt(getattr(settings, field))
            help_bar = self.query_one(HelpBar)
            help_bar.set_items(
                [
                    ("enter", "trocar tecla"),
                    ("tab", "próximo campo"),
                    (settings.keys.get("back") or "escape", "voltar"),
                ]
            )
            help_bar.set_enabled(settings.show_help)
        finally:
            self._loading = False

    def _update_key_button(self, action: str, key: str | None) -> None:
        self.query_one(f"#key-{action}", Button).label = display_key(key)

    # -- teclas ---------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id.startswith("key-"):
            self.start_capture(button_id.removeprefix("key-"))
        elif button_id == "reset":
            self.confirm_reset()

    def start_capture(self, action: str) -> None:
        self.capturing = action
        button = self.query_one(f"#key-{action}", Button)
        button.label = "aperte a nova tecla…"
        button.add_class("capturing")

    def stop_capture(self) -> None:
        if self.capturing is None:
            return
        action = self.capturing
        self.capturing = None
        button = self.query_one(f"#key-{action}", Button)
        button.remove_class("capturing")
        self._update_key_button(action, self.settings.keys[action])

    def on_key(self, event: events.Key) -> None:
        if self.capturing is None:
            self.handle_back_key(event)
            return
        event.stop()
        event.prevent_default()
        action = self.capturing
        if event.key == "escape":
            self.stop_capture()
            return
        try:
            self.cc_app.services.settings.set_key(action, event.key)
        except ValidationError as exc:
            self.notify(exc.message, severity="error")
        else:
            self.notify(f"{ACTION_LABELS[action]}: {display_key(event.key)}", timeout=2)
        self.stop_capture()

    # -- demais campos --------------------------------------------------------

    def on_switch_changed(self, event: Switch.Changed) -> None:
        if self._loading or event.switch.id != "show-help":
            return
        self.cc_app.services.settings.update(show_help=event.value)
        self.query_one(HelpBar).set_enabled(event.value)

    def on_input_changed(self, event: Input.Changed) -> None:
        if self._loading:
            return
        field = (event.input.id or "").removeprefix("input-")
        if field not in NUMBER_FIELDS:
            return
        if event.validation_result is not None and not event.validation_result.is_valid:
            return
        _, _, parse, _ = NUMBER_FIELDS[field]
        try:
            self.cc_app.services.settings.update(**{field: parse(event.value)})
        except (ValidationError, ValueError) as exc:
            message = exc.message if isinstance(exc, ValidationError) else str(exc)
            self.notify(message, severity="error")

    def confirm_reset(self) -> None:
        def after(confirmed: bool | None) -> None:
            if confirmed:
                self.cc_app.services.settings.reset()
                self.load_values()
                self.notify("Configurações restauradas.")

        self.app.push_screen(
            ConfirmModal("Restaurar todas as configurações para os padrões?", confirm_label="Sim"),
            after,
        )

    def action_back(self) -> None:
        self.app.pop_screen()
