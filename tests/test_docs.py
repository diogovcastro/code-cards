from __future__ import annotations

import json
from pathlib import Path

from code_cards.services.importer import BATCH_SCHEMA

DOCS = Path(__file__).resolve().parent.parent / "docs"


def test_schema_da_documentacao_esta_atualizado() -> None:
    """Se falhar, rode: uv run code-cards schema --raw > docs/batch.schema.json"""
    on_disk = json.loads((DOCS / "batch.schema.json").read_text(encoding="utf-8"))
    assert on_disk == BATCH_SCHEMA
