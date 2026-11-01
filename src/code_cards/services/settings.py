"""Serviço de configurações: leitura, validação e gravação do settings.json."""

from __future__ import annotations

import math
from dataclasses import fields, replace
from typing import Any

from code_cards.errors import ValidationError
from code_cards.models import ACTIONS, OPTIONAL_KEY_ACTIONS, Settings
from code_cards.storage import JsonStore

#: Teclas que nunca podem ser usadas pelas ações. O Esc sempre volta (e pode
#: ser a tecla da ação voltar); as setas ↑/↓ sempre rolam no estudo.
RESERVED_KEYS: frozenset[str] = frozenset({"escape", "q", "Q", "question_mark", "up", "down"})
#: Teclas proibidas só para a ação voltar (abrem itens nas listas).
BACK_FORBIDDEN_KEYS: frozenset[str] = frozenset({"enter", "tab", "shift+tab"})

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
    "up": "↑",
    "down": "↓",
    "left": "←",
    "right": "→",
}

MODIFIER_DISPLAY: dict[str, str] = {"ctrl": "Ctrl", "shift": "Shift", "alt": "Alt"}


def normalize_key(key: str) -> str:
    key = key if key == " " else key.strip()
    if not key:
        raise ValidationError("Tecla vazia.", {"field": "keys"})
    return KEY_ALIASES.get(key.lower(), key)


def display_key(key: str | None) -> str:
    """Nome amigável de uma tecla do Textual: ``ctrl+s`` → ``Ctrl+S``."""
    if key is None:
        return "—"
    *modifiers, base = key.split("+") if key != "+" else ["+"]
    if base in KEY_DISPLAY:
        base = KEY_DISPLAY[base]
    elif len(base) == 1:
        base = base.upper()
    return "+".join([*(MODIFIER_DISPLAY.get(m, m) for m in modifiers), base])


def _key_error(message: str, action: str, key: str, **extra: Any) -> ValidationError:
    return ValidationError(message, {"field": "keys", "action": action, "key": key, **extra})


def validate_keys(keys: dict[str, str | None]) -> None:
    missing = [
        action for action in ACTIONS if action not in OPTIONAL_KEY_ACTIONS and not keys.get(action)
    ]
    if missing:
        raise ValidationError(f"Faltam teclas para: {', '.join(missing)}.", {"missing": missing})
    seen: dict[str, str] = {}
    for action in ACTIONS:
        key = keys.get(action)
        if key is None:
            continue
        if key in RESERVED_KEYS and not (action == "back" and key == "escape"):
            raise _key_error(f"A tecla '{display_key(key)}' é reservada.", action, key)
        if action == "back" and key in BACK_FORBIDDEN_KEYS:
            raise _key_error(
                f"A tecla '{display_key(key)}' não pode ser usada para voltar.", action, key
            )
        if key in seen:
            raise _key_error(
                f"A tecla '{display_key(key)}' já está em uso por '{seen[key]}'.",
                action,
                key,
                conflict=seen[key],
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

    @staticmethod
    def _check_action(action: str) -> None:
        if action not in ACTIONS:
            raise ValidationError(f"Ação desconhecida: '{action}'.", {"action": action})

    def set_key(self, action: str, key: str) -> Settings:
        self._check_action(action)
        return self.update(keys={action: normalize_key(key)})

    def clear_key(self, action: str) -> Settings:
        """Remove a tecla de uma ação opcional (rolagem)."""
        self._check_action(action)
        if action not in OPTIONAL_KEY_ACTIONS:
            raise ValidationError(
                "Essa ação precisa de uma tecla.", {"field": "keys", "action": action}
            )
        return self.update(keys={action: None})

    def reset(self) -> Settings:
        return self.save(Settings())
