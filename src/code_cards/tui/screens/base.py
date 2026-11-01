"""Comportamento comum das telas: voltar por tecla ou botão do mouse configurado."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual import events

from code_cards.models import Settings

if TYPE_CHECKING:
    from textual.app import App

    from code_cards.tui.app import CodeCardsApp


class ConfigurableBackMixin:
    """Mistura para ``Screen``/``ModalScreen``.

    - O Esc continua com os bindings de cada tela e sempre volta.
    - A tecla de voltar configurada vale onde ``BACK_KEY_ENABLED`` é verdadeiro
      (não vale no editor nem nos diálogos com campo de texto).
    - Os botões do mouse configurados chegam por ``run_mouse_action``, chamado
      pelo app antes de o clique alcançar qualquer widget.
    """

    BACK_KEY_ENABLED = True

    if TYPE_CHECKING:
        app: App[None]

    @property
    def cc_app(self) -> CodeCardsApp:
        return cast("CodeCardsApp", self.app)

    @property
    def current_settings(self) -> Settings:
        return self.cc_app.services.settings.get()

    def back_key(self) -> str:
        return self.current_settings.keys.get("back") or "escape"

    def handle_back_key(self, event: events.Key) -> bool:
        """Trata a tecla de voltar configurada. Devolve ``True`` se tratou."""
        if not self.BACK_KEY_ENABLED or event.key != self.back_key():
            return False
        event.stop()
        event.prevent_default()
        self.go_back()
        return True

    def run_mouse_action(self, action: str) -> None:
        """Executa a ação ligada a um botão do mouse (só voltar, por padrão)."""
        if action == "back":
            self.go_back()

    def go_back(self) -> None:
        self.app.pop_screen()
