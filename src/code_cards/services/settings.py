"""Serviço de configurações: leitura, validação e gravação do settings.json."""

from __future__ import annotations

import math
from dataclasses import fields, replace
from typing import Any

from code_cards.errors import ValidationError
from code_cards.models import ACTIONS, Settings
from code_cards.storage import JsonStore

#: Teclas que nunca podem ser usadas por uma ação de estudo.
RESERVED_KEYS: frozenset[str] = frozenset({"escape", "q", "Q", "question_mark"})

MIN_RETENTION = 0.80
MAX_RETENTION = 0.97
MAX_PER_DAY = 9999

#: Apelidos aceitos ao configurar teclas (o valor salvo é o nome do Textual).
KEY_ALIASES: dict[str, str] = {
    " ": "space",
    "esc": "escape",
    "?": "question_mark",
    "return": "enter",
}

#: Nomes amigáveis para exibir teclas na barra de ajuda.
KEY_DISPLAY: dict[str, str] = {
    "space": "Espaço",
    "escape": "Esc",
    "enter": "Enter",
    "tab": "Tab",
    "question_mark": "?",
    "delete": "Del",
    "backspace": "Backspace",
}


def normalize_key(key: str) -> str:
    key = key if key == " " else key.strip()
    if not key:
        raise ValidationError("Tecla vazia.", {"field": "keys"})
    return KEY_ALIASES.get(key.lower(), key)


def display_key(key: str) -> str:
    if key in KEY_DISPLAY:
        return KEY_DISPLAY[key]
    if len(key) == 1:
        return key.upper()
    return key.replace("ctrl+", "Ctrl+").replace("shift+", "Shift+").replace("alt+", "Alt+")


def validate_keys(keys: dict[str, str]) -> None:
    missing = [action for action in ACTIONS if action not in keys]
    if missing:
        raise ValidationError(f"Faltam teclas para: {', '.join(missing)}.", {"missing": missing})
    seen: dict[str, str] = {}
    for action in ACTIONS:
        key = keys[action]
        if key in RESERVED_KEYS:
            raise ValidationError(
                f"A tecla '{display_key(key)}' é reservada.",
                {"field": "keys", "action": action, "key": key},
            )
        if key in seen:
            raise ValidationError(
                f"A tecla '{display_key(key)}' já está em uso por '{seen[key]}'.",
                {"field": "keys", "action": action, "key": key, "conflict": seen[key]},
            )
        seen[key] = action


def _check_int(name: str, value: Any, low: int, high: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValidationError(
            f"'{name}' deve ser um inteiro entre {low} e {high}.",
            {"field": name, "value": value},
        )


def validate_settings(settings: Settings) -> None:
    validate_keys(settings.keys)
    _check_int("new_cards_per_day", settings.new_cards_per_day, 0, MAX_PER_DAY)
    _check_int("reviews_per_day", settings.reviews_per_day, 0, MAX_PER_DAY)
    _check_int("day_starts_at_hour", settings.day_starts_at_hour, 0, 23)
    retention = settings.desired_retention
    if (
        isinstance(retention, bool)
        or not isinstance(retention, int | float)
        or math.isnan(retention)
        or not MIN_RETENTION <= retention <= MAX_RETENTION
    ):
        raise ValidationError(
            f"'desired_retention' deve estar entre {MIN_RETENTION:.2f} e {MAX_RETENTION:.2f}.",
            {"field": "desired_retention", "value": retention},
        )
    if not isinstance(settings.show_help, bool):
        raise ValidationError("'show_help' deve ser verdadeiro ou falso.", {"field": "show_help"})
    if not isinstance(settings.editor_theme, str) or not settings.editor_theme.strip():
        raise ValidationError("'editor_theme' não pode ser vazio.", {"field": "editor_theme"})


class SettingsService:
    def __init__(self, store: JsonStore) -> None:
        self.store = store

    def get(self) -> Settings:
        return self.store.load_settings()

    def save(self, settings: Settings) -> Settings:
        validate_settings(settings)
        self.store.save_settings(settings)
        return settings

    def update(self, **changes: Any) -> Settings:
        known = {f.name for f in fields(Settings)}
        unknown = sorted(set(changes) - known)
        if unknown:
            raise ValidationError(
                f"Configuração desconhecida: {', '.join(unknown)}.", {"unknown": unknown}
            )
        current = self.get()
        if "keys" in changes:
            changes["keys"] = {**current.keys, **changes["keys"]}
        return self.save(replace(current, **changes))

    def set_key(self, action: str, key: str) -> Settings:
        if action not in ACTIONS:
            raise ValidationError(f"Ação desconhecida: '{action}'.", {"action": action})
        return self.update(keys={action: normalize_key(key)})

    def reset(self) -> Settings:
        return self.save(Settings())
