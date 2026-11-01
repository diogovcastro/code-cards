"""Migrações de ``schema_version`` dos arquivos de dados.

Cada tipo de arquivo tem uma versão atual e um dicionário
``{versão_de_origem: função}`` que leva o JSON da versão ``n`` para ``n + 1``.
Para mudar o formato: suba a versão em ``models.py`` e registre aqui a função
que converte a versão anterior.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from code_cards.errors import StorageError
from code_cards.models import DECK_SCHEMA_VERSION, SETTINGS_SCHEMA_VERSION

Migration = Callable[[dict[str, Any]], dict[str, Any]]

CURRENT_VERSIONS: dict[str, int] = {
    "deck": DECK_SCHEMA_VERSION,
    "settings": SETTINGS_SCHEMA_VERSION,
}


def _settings_v1_to_v2(data: dict[str, Any]) -> dict[str, Any]:
    """Acrescenta voltar, rolar e o bloco ``mouse``, sem tocar nas teclas já escolhidas."""
    keys = dict(data.get("keys", {}))
    used = set(keys.values())
    keys.setdefault("back", "escape")
    keys.setdefault("scroll_up", None if "w" in used else "w")
    keys.setdefault("scroll_down", None)
    data["keys"] = keys
    data.setdefault("mouse", {})
    return data


MIGRATIONS: dict[str, dict[int, Migration]] = {
    "deck": {},
    "settings": {1: _settings_v1_to_v2},
}


def migrate(kind: str, data: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Leva ``data`` até a versão atual. Devolve ``(dados, mudou)``."""
    current = CURRENT_VERSIONS[kind]
    version = data.get("schema_version")
    if not isinstance(version, int) or version < 1:
        raise StorageError(
            f"Arquivo de {kind} sem 'schema_version' válido.",
            {"kind": kind, "schema_version": version},
        )
    if version > current:
        raise StorageError(
            f"Arquivo de {kind} foi gravado por uma versão mais nova do code-cards "
            f"(schema {version}, este programa entende até {current}).",
            {"kind": kind, "schema_version": version, "supported": current},
        )
    changed = False
    while version < current:
        step = MIGRATIONS[kind].get(version)
        if step is None:
            raise StorageError(
                f"Não há migração de {kind} da versão {version} para {version + 1}.",
                {"kind": kind, "schema_version": version},
            )
        data = step(dict(data))
        version += 1
        data["schema_version"] = version
        changed = True
    return data, changed
