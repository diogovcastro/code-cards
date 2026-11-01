from __future__ import annotations

from pathlib import Path

import pytest

from code_cards.errors import ValidationError
from code_cards.models import DEFAULT_KEYS, Settings
from code_cards.paths import DataPaths
from code_cards.services.settings import (
    SettingsService,
    display_key,
    display_mouse,
    normalize_key,
)
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
    assert display_key("ctrl+s") == "Ctrl+S"
    assert display_key("ctrl+down") == "Ctrl+↓"
    assert display_key("question_mark") == "?"


def test_padroes_de_voltar_e_rolagem(service: SettingsService) -> None:
    keys = service.get().keys
    assert keys["back"] == "escape"
    assert keys["scroll_up"] == "w"
    assert keys["scroll_down"] is None


def test_trocar_tecla_de_voltar(service: SettingsService) -> None:
    assert service.set_key("back", "b").keys["back"] == "b"
    # Esc continua reservado para as outras ações.
    with pytest.raises(ValidationError, match="reservada"):
        service.set_key("great", "escape")
    # E pode voltar a ser a tecla de voltar.
    assert service.set_key("back", "escape").keys["back"] == "escape"


@pytest.mark.parametrize("key", ["enter", "tab"])
def test_voltar_nao_aceita_enter_nem_tab(service: SettingsService, key: str) -> None:
    with pytest.raises(ValidationError, match="voltar"):
        service.set_key("back", key)


@pytest.mark.parametrize("key", ["up", "down"])
def test_setas_sao_reservadas(service: SettingsService, key: str) -> None:
    with pytest.raises(ValidationError, match="reservada"):
        service.set_key("scroll_down", key)


def test_rolagem_pode_ficar_sem_tecla(service: SettingsService) -> None:
    assert service.set_key("scroll_down", "x").keys["scroll_down"] == "x"
    assert service.clear_key("scroll_down").keys["scroll_down"] is None
    with pytest.raises(ValidationError, match="precisa de uma tecla"):
        service.clear_key("great")


def test_rolagem_nao_pode_repetir_tecla_de_nota(service: SettingsService) -> None:
    with pytest.raises(ValidationError, match="já está em uso"):
        service.set_key("scroll_down", "s")


def test_mouse_desligado_por_padrao(service: SettingsService) -> None:
    assert set(service.get().mouse.values()) == {None}


def test_associar_e_remover_botao_do_mouse(service: SettingsService) -> None:
    assert service.set_mouse_button("back", "button8").mouse["back"] == "button8"
    assert service.set_mouse_button("great", "middle").mouse["great"] == "middle"
    # As teclas continuam valendo junto com o mouse.
    assert service.get().keys["great"] == "a"
    assert service.clear_mouse_button("back").mouse["back"] is None


def test_botao_repetido_e_recusado(service: SettingsService) -> None:
    service.set_mouse_button("back", "button8")
    with pytest.raises(ValidationError, match="já está em uso"):
        service.set_mouse_button("undo", "button8")


@pytest.mark.parametrize("button", ["left", "wheel_up", "button1", "x"])
def test_botao_esquerdo_roda_ou_invalido(service: SettingsService, button: str) -> None:
    with pytest.raises(ValidationError, match="reservados"):
        service.set_mouse_button("great", button)


def test_restaurar_padroes_remove_mouse(service: SettingsService) -> None:
    service.set_mouse_button("back", "button8")
    assert set(service.reset().mouse.values()) == {None}


def test_rotulos_de_mouse() -> None:
    assert display_mouse("button8") == "Lateral (voltar)"
    assert display_mouse(None) == "—"
