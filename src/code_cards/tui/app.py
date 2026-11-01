"""TUI do code-cards (Textual)."""

from __future__ import annotations

from textual import events
from textual.app import App

from code_cards.models import Settings
from code_cards.services.container import Services, build_services
from code_cards.tui.mouse import button_name, install_extra_button_support


class CodeCardsApp(App[None]):
    CSS_PATH = "styles.tcss"
    TITLE = "code-cards"

    def __init__(self, services: Services | None = None) -> None:
        install_extra_button_support()
        super().__init__()
        self.services = services or build_services()
        self._swallowed_buttons: set[int] = set()

    @property
    def settings(self) -> Settings:
        return self.services.settings.get()

    def mouse_action_for(self, button: int) -> str | None:
        """Ação configurada para um botão do mouse, se houver."""
        name = button_name(button)
        if name is None:
            return None
        for action, configured in self.settings.mouse.items():
            if configured == name:
                return action
        return None

    async def on_event(self, event: events.Event) -> None:
        # Eventos do terminal passam por aqui antes de chegar à tela. Os botões
        # configurados são consumidos aqui para não acionarem o widget sob o ponteiro.
        if isinstance(event, events.MouseEvent) and not event.is_forwarded:
            if isinstance(event, events.MouseUp) and event.button in self._swallowed_buttons:
                self._swallowed_buttons.discard(event.button)
                return
            if self._intercept_mouse(event):
                if isinstance(event, events.MouseDown):
                    self._swallowed_buttons.add(event.button)
                return
        await super().on_event(event)

    def _intercept_mouse(self, event: events.MouseEvent) -> bool:
        capture = getattr(self.screen, "handle_mouse_capture", None)
        if capture is not None and capture(event):
            return True
        if not isinstance(event, events.MouseDown) or event.button == 1:
            return False
        action = self.mouse_action_for(event.button)
        if action is None:
            return False
        handler = getattr(self.screen, "run_mouse_action", None)
        if handler is not None:
            handler(action)
        return True

    def on_mount(self) -> None:
        from code_cards.tui.screens.main import MainScreen

        self.push_screen(MainScreen())


def run_tui() -> None:
    CodeCardsApp().run()
