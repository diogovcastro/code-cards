"""Diálogos modais: confirmação (sim/não) e pedido de texto."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label


class ConfirmModal(ModalScreen[bool]):
    """Pergunta sim/não. Devolve ``True`` se confirmado."""

    BINDINGS = [
        Binding("escape", "answer(False)", "Não", priority=True),
        Binding("n", "answer(False)", "Não", show=False),
        Binding("s,y", "answer(True)", "Sim", show=False),
    ]

    def __init__(self, message: str, *, confirm_label: str = "Sim", danger: bool = False) -> None:
        super().__init__()
        self.message = message
        self.confirm_label = confirm_label
        self.danger = danger

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal"):
            yield Label(self.message, classes="modal-message")
            with Horizontal(classes="modal-buttons"):
                yield Button(
                    self.confirm_label,
                    id="confirm",
                    variant="error" if self.danger else "primary",
                )
                yield Button("Cancelar", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#cancel" if self.danger else "#confirm", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm")

    def action_answer(self, value: bool) -> None:
        self.dismiss(value)


class TextPromptModal(ModalScreen[str | None]):
    """Pede um texto. Devolve o texto (sem espaços nas pontas) ou ``None`` se cancelado."""

    BINDINGS = [Binding("escape", "cancel", "Cancelar", priority=True)]

    def __init__(
        self,
        message: str,
        *,
        value: str = "",
        placeholder: str = "",
        confirm_label: str = "OK",
        danger: bool = False,
    ) -> None:
        super().__init__()
        self.message = message
        self.value = value
        self.placeholder = placeholder
        self.confirm_label = confirm_label
        self.danger = danger

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal"):
            yield Label(self.message, classes="modal-message")
            yield Input(value=self.value, placeholder=self.placeholder, id="prompt-input")
            with Horizontal(classes="modal-buttons"):
                yield Button(
                    self.confirm_label,
                    id="confirm",
                    variant="error" if self.danger else "primary",
                )
                yield Button("Cancelar", id="cancel")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self.dismiss(event.value.strip())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            self.dismiss(self.query_one(Input).value.strip())
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
