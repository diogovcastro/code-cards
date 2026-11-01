"""Barra de ajuda no rodapé, com as teclas da tela atual."""

from __future__ import annotations

from rich.text import Text
from textual.widgets import Static

from code_cards.services.settings import display_key

HelpItem = tuple[str, str]  # (tecla no formato do Textual, rótulo)


class HelpBar(Static):
    """Mostra ``Tecla rótulo · Tecla rótulo``. Some se ``enabled`` for falso."""

    DEFAULT_CLASSES = "help-bar"

    def __init__(
        self, items: list[HelpItem] | None = None, *, enabled: bool = True, id: str | None = None
    ) -> None:
        super().__init__("", id=id)
        self._items: list[HelpItem] = items or []
        self._separator = " · "
        self.enabled = enabled

    def on_mount(self) -> None:
        self._refresh()

    def set_items(self, items: list[HelpItem], *, separator: str = " · ") -> None:
        self._items = items
        self._separator = separator
        self._refresh()

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        self._refresh()

    def toggle(self) -> None:
        self.set_enabled(not self.enabled)

    def _refresh(self) -> None:
        text = Text()
        for i, (key, label) in enumerate(self._items):
            if i:
                text.append(self._separator, style="dim")
            text.append(display_key(key), style="bold")
            text.append(f" {label}")
        self.update(text)
        self.display = self.enabled and bool(self._items)
