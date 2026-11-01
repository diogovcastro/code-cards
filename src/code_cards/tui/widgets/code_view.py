"""Exibição de código com o mesmo highlight do editor (TextArea do Textual)."""

from __future__ import annotations

from textual.widgets import TextArea

from code_cards import languages


def code_area(
    code: str = "",
    language: str = "python",
    *,
    theme: str = "monokai",
    read_only: bool = False,
    id: str | None = None,
) -> TextArea:
    """TextArea configurado para código; ``read_only=True`` na tela de estudo."""
    area = TextArea.code_editor(
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
