"""Exibição de código com o mesmo highlight do editor (TextArea do Textual)."""

from __future__ import annotations

from textual import events
from textual.widgets import Static, TextArea

from code_cards import languages


class StudyCodeView(TextArea):
    """Código da tela de estudo: o clique só dá foco, sem cursor nem seleção.

    Assim a troca de foco entre código e descrição não muda nada na tela.
    """

    ALLOW_SELECT = False

    async def _on_mouse_down(self, event: events.MouseDown) -> None:
        event.stop()
        event.prevent_default()
        self.focus()

    async def _on_mouse_move(self, event: events.MouseMove) -> None:
        return

    async def _on_mouse_up(self, event: events.MouseUp) -> None:
        return


class DescriptionView(Static):
    """Descrição na tela de estudo, sem seleção de texto pelo mouse."""

    ALLOW_SELECT = False


def code_area(
    code: str = "",
    language: str = "python",
    *,
    theme: str = "monokai",
    read_only: bool = False,
    id: str | None = None,
    cls: type[TextArea] = TextArea,
) -> TextArea:
    """TextArea configurado para código; ``read_only=True`` na tela de estudo."""
    area = cls.code_editor(
        code,
        language=languages.highlight_for(language),
        theme=theme,
        read_only=read_only,
        show_line_numbers=True,
        show_cursor=not read_only,
        highlight_cursor_line=not read_only,
        id=id,
    )
    if theme not in area.available_themes:
        area.theme = "monokai"
    return area


def show_code(area: TextArea, code: str, language: str) -> None:
    """Troca o código exibido e a linguagem do highlight."""
    area.language = languages.highlight_for(language)
    area.load_text(code)
    area.scroll_home(animate=False)
    area.move_cursor((0, 0))
