"""TUI do code-cards (Textual)."""

from __future__ import annotations

from textual.app import App

from code_cards.models import Settings
from code_cards.services.container import Services, build_services


class CodeCardsApp(App[None]):
    CSS_PATH = "styles.tcss"
    TITLE = "code-cards"

    def __init__(self, services: Services | None = None) -> None:
        super().__init__()
        self.services = services or build_services()

    @property
    def settings(self) -> Settings:
        return self.services.settings.get()

    def on_mount(self) -> None:
        from code_cards.tui.screens.main import MainScreen

        self.push_screen(MainScreen())


def run_tui() -> None:
    CodeCardsApp().run()
