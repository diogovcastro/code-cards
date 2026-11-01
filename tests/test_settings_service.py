from __future__ import annotations

from pathlib import Path

import pytest

from code_cards.errors import ValidationError
from code_cards.models import DEFAULT_KEYS, Settings
from code_cards.paths import DataPaths
from code_cards.services.settings import SettingsService, display_key, normalize_key
from code_cards.storage import JsonStore


@pytest.fixture
def service(tmp_path: Path) -> SettingsService:
    return SettingsService(JsonStore(DataPaths(tmp_path)))


def test_padroes(service: SettingsService) -> None:
    assert service.get() == Settings()


def test_troca_tecla_e_persiste(service: SettingsService) -> None:
    service.set_key("great", "j")
    assert service.get().keys["great"] == "j"


def test_nao_deixa_tecla_duplicada(service: SettingsService) -> None:
    with pytest.raises(ValidationError, match="já está em uso"):
        service.set_key("great", "s")
    assert service.get().keys == DEFAULT_KEYS


@pytest.mark.parametrize("key", ["escape", "esc", "q", "Q", "?"])
def test_nao_deixa_tecla_reservada(service: SettingsService, key: str) -> None:
    with pytest.raises(ValidationError, match="reservada"):
        service.set_key("great", key)


def test_acao_desconhecida(service: SettingsService) -> None:
    with pytest.raises(ValidationError):
        service.set_key("voar", "x")


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"desired_retention": 0.79}, "desired_retention"),
        ({"desired_retention": 0.98}, "desired_retention"),
        ({"new_cards_per_day": -1}, "new_cards_per_day"),
        ({"reviews_per_day": 1.5}, "reviews_per_day"),
        ({"day_starts_at_hour": 24}, "day_starts_at_hour"),
        ({"show_help": "sim"}, "show_help"),
    ],
)
def test_validacao_de_valores(service: SettingsService, changes: dict, field: str) -> None:
    with pytest.raises(ValidationError) as exc:
        service.update(**changes)
    assert exc.value.details["field"] == field


def test_limites_da_retencao_sao_aceitos(service: SettingsService) -> None:
    assert service.update(desired_retention=0.8).desired_retention == 0.8
    assert service.update(desired_retention=0.97).desired_retention == 0.97


def test_configuracao_desconhecida(service: SettingsService) -> None:
    with pytest.raises(ValidationError, match="desconhecida"):
        service.update(cor="azul")


def test_restaurar_padroes(service: SettingsService) -> None:
    service.update(show_help=False, new_cards_per_day=10)
    assert service.reset() == Settings()
    assert service.get() == Settings()


def test_normaliza_e_exibe_teclas() -> None:
    assert normalize_key(" ") == "space"
    assert normalize_key("Esc") == "escape"
    assert display_key("space") == "Espaço"
    assert display_key("a") == "A"
    assert display_key("ctrl+k") == "Ctrl+k"
