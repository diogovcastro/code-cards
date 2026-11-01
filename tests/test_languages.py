from __future__ import annotations

from textual.widgets import TextArea

from code_cards import languages


def test_python_registrado() -> None:
    lang = languages.get("Python")
    assert lang is not None
    assert lang.tree_sitter == "python"
    assert languages.highlight_for("python") == "python"


def test_texto_puro_e_desconhecida() -> None:
    assert languages.is_known("text")
    assert languages.highlight_for("text") is None
    assert not languages.is_known("cobol")
    assert languages.highlight_for("cobol") is None
    assert languages.label_for("cobol") == "cobol"


def test_deteccao_por_extensao() -> None:
    assert languages.detect_from_filename("app.py") == "python"
    assert languages.detect_from_filename("tipos.PYI") == "python"
    assert languages.detect_from_filename("notas.txt") == "text"
    assert languages.detect_from_filename("main.rs") is None
    assert languages.detect_from_filename("Makefile") is None


def test_gramaticas_existem_no_textual() -> None:
    available = TextArea().available_languages
    for lang in languages.REGISTRY.values():
        assert lang.tree_sitter in available
