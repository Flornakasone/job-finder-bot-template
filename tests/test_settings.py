"""Tests de config/settings.toml: lo configurable del bot."""
from src.settings import Settings, load_settings


def test_lee_los_valores_del_archivo(tmp_path):
    path = tmp_path / "settings.toml"
    path.write_text(
        '[ranking]\ntop_n = 5\nmin_score = 40\n'
        '[filters]\ntitle_region_blocklist = ["US"]\n',
        encoding="utf-8",
    )
    assert load_settings(path) == Settings(top_n=5, min_score=40, title_region_blocklist=["US"])


def test_claves_faltantes_usan_valores_por_defecto(tmp_path):
    path = tmp_path / "settings.toml"
    path.write_text("[ranking]\nmin_score = 50\n", encoding="utf-8")
    assert load_settings(path) == Settings(min_score=50)


def test_sin_archivo_usa_valores_por_defecto(tmp_path):
    assert load_settings(tmp_path / "no-existe.toml") == Settings()


def test_el_settings_real_carga():
    # Si alguien rompe la sintaxis del .toml, este test lo avisa antes del cron
    settings = load_settings()
    assert settings.top_n > 0
    assert 0 <= settings.min_score <= 100

def test_lee_los_idiomas(tmp_path):
    path = tmp_path / "settings.toml"
    path.write_text('[filters]\nspoken_languages = ["Spanish"]\n', encoding="utf-8")
    assert load_settings(path).spoken_languages == ["Spanish"]

def test_lee_el_dia_del_reporte(tmp_path):
    path = tmp_path / "settings.toml"
    path.write_text('[report]\nweekly_gaps_day = "lunes"\n', encoding="utf-8")
    assert load_settings(path).weekly_gaps_day == "lunes"

def test_lee_ubicacion_y_roles(tmp_path):
    path = tmp_path / "settings.toml"
    path.write_text(
        '[location]\naccepted = ["spain"]\nonsite_ok = ["madrid"]\n'
        '[[roles]]\nweight = 1.0\nwords = ["ux"]\n', encoding="utf-8")
    s = load_settings(path)
    assert (s.accepted_locations, s.onsite_locations, s.role_groups) == (["spain"], ["madrid"], [(1.0, ["ux"])])