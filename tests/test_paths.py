"""Tests de dónde se busca la configuración: me/ -> config/ -> templates/me/."""
import pytest

from src.paths import find_config, using_template


@pytest.fixture
def dirs(tmp_path):
    me, config, template = tmp_path / "me", tmp_path / "config", tmp_path / "templates"
    for d in (me, config, template):
        d.mkdir()
    return me, config, template


def test_me_gana_sobre_config_y_template(dirs):
    me, config, template = dirs
    for d in dirs:
        (d / "keywords.txt").write_text("x")
    assert find_config("keywords.txt", search=dirs) == me / "keywords.txt"


def test_si_no_esta_en_me_usa_config(dirs):
    me, config, template = dirs
    (config / "excluded.txt").write_text("x")
    (template / "excluded.txt").write_text("x")
    assert find_config("excluded.txt", search=dirs) == config / "excluded.txt"


def test_sin_me_usa_el_ejemplo(dirs):
    me, config, template = dirs
    (template / "skills.txt").write_text("x")
    assert find_config("skills.txt", search=dirs) == template / "skills.txt"


def test_si_no_existe_en_ningun_lado_avisa(dirs):
    with pytest.raises(FileNotFoundError, match="nada.txt"):
        find_config("nada.txt", search=dirs)


def test_using_template(tmp_path):
    assert using_template(tmp_path / "me") is True
    (tmp_path / "me").mkdir()
    assert using_template(tmp_path / "me") is False


@pytest.mark.parametrize("name", ["settings.toml", "keywords.txt", "skills.txt", "tech.txt", "empresas.txt"])
def test_el_template_trae_todos_los_archivos(name):
    # Si alguien borra un ejemplo, un usuario nuevo se queda sin configuración
    from src.paths import TEMPLATE_DIR
    assert (TEMPLATE_DIR / name).exists()


def test_el_template_es_un_toml_valido():
    from src.settings import load_settings
    from src.paths import TEMPLATE_DIR
    settings = load_settings(TEMPLATE_DIR / "settings.toml")
    assert settings.accepted_locations and settings.role_groups
