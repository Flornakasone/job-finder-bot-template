"""
Tests de los filtros duros.
Los casos de ubicación salen de datos REALES vistos en el contract check
de Remotive (ej. "USA, Canada, USA timezones").
"""
import pytest

from src.filters import (
    apply_filters,
    check_english,
    check_excluded,
    check_location,
    check_role,
    contains_phrase,
    load_list,
    normalize,
)
from src.models import Job


def make_job(**overrides) -> Job:
    data = {
        "source": "Test",
        "source_id": "1",
        "title": "QA Engineer",
        "company": "Acme",
        "url": "https://example.com/1",
        "location": "Worldwide",
        "description": "We test payments.",
    }
    data.update(overrides)
    return Job(**data)


# ---------------------------------------------------------------- utilidades

def test_normalize_saca_tildes_y_mayusculas():
    assert normalize("Atención al Cliente") == "atencion al cliente"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("QA Engineer", "qa"),
        ("Senior QA/Tester", "qa"),
        ("Sales Manager - Qatar", None),  # 'qa' dentro de 'Qatar' no cuenta
        ("Contest organizer", None),      # 'test' dentro de 'Contest' no cuenta
    ],
)
def test_contains_phrase_respeta_palabras_completas(text, expected):
    assert contains_phrase(text, ["qa", "test"]) == expected


def test_load_list_ignora_comentarios_y_vacias(tmp_path):
    (tmp_path / "x.txt").write_text("# comentario\n\nQA\n  Atención  \n", encoding="utf-8")
    assert load_list("x.txt", config_dir=tmp_path) == ["qa", "atencion"]


def test_los_archivos_de_config_reales_cargan():
    assert "qa" in load_list("keywords.txt")
    assert "mlm" in load_list("excluded.txt")


# ------------------------------------------------------------------ ubicación

@pytest.mark.parametrize(
    "location",
    [
        "Worldwide", 
        "Anywhere", 
        "LATAM", 
        "Latin America", 
        "Argentina",
        "Buenos Aires, Argentina (Hybrid)", 
        "Buenos Aires (Presencial)",
        "Americas", 
        "Remote", 
        "Américas",
        "América Latina",
        "Capital Federal", 
        "100% remoto", 
        "Todo el mundo",
        "Brasil, Argentina, Chile",
    ],
)
def test_ubicaciones_aceptadas(location):
    assert check_location(make_job(location=location)) is None


@pytest.mark.parametrize(
    "location",
    [
        "USA",
        "USA, Canada, USA timezones",                 # real, Remotive
        "Europe, USA, Canada, APAC",                  # real, Remotive
        "Remote - US",                                # 'remote' no alcanza
        "North America",
        "Brazil",
        "Spain",
        "Australia",
        "España",
        "Brasil",
        "Córdoba, Argentina (Presencial)",
        "Argentina (On-site)",
        "",
    ],
)
def test_ubicaciones_rechazadas(location):
    assert check_location(make_job(location=location)) is not None
   


def test_worldwide_pero_la_descripcion_dice_us_only():
    job = make_job(location="Worldwide", description="Remote role. US only, sorry.")
    assert "restringe" in check_location(job)


# --------------------------------------------------------------------- inglés

@pytest.mark.parametrize(
    "description",
    [
        "Requirements: fluent English.",
        "Advanced English is required",
        "Native English speaker",
        "Nivel de inglés: C1",
        "Inglés avanzado excluyente.",
        "Must be bilingual (Spanish/English).",
        "Nivel avanzado de inglés",
    ],
)
def test_ingles_obligatorio_se_descarta(description):
    assert check_english(make_job(description=description)) == "exige inglés avanzado"


@pytest.mark.parametrize(
    "description",
    [
        "Fluent English is a plus.",
        "Advanced English: nice to have",
        "Inglés avanzado deseable.",
        "Intermediate English required.",
        "No English needed.",
        "",
    ],
)
def test_ingles_opcional_o_intermedio_pasa(description):
    assert check_english(make_job(description=description)) is None


def test_ingles_cada_oracion_se_evalua_por_separado():
    # El "plus" está en otra oración: no salva a la primera
    desc = "Fluent English required. Experience with Python is a plus."
    assert check_english(make_job(description=desc)) is not None


# --------------------------------------------------------- rubro y excluidos

KEYWORDS = ["qa", "support", "data annotation"]
EXCLUDED = ["mlm", "commission only", "application fee"]


@pytest.mark.parametrize("title", ["QA Analyst", "Customer Support", "Data Annotation Specialist"])
def test_rubros_buscados_pasan(title):
    assert check_role(make_job(title=title), KEYWORDS) is None


def test_rubro_no_buscado_se_descarta():
    assert check_role(make_job(title="Senior Sales Manager"), KEYWORDS) == "rubro no buscado"


@pytest.mark.parametrize(
    "field, text",
    [
        ("title", "QA Tester - Commission Only"),
        ("description", "Join our MLM team!"),
        ("description", "There is a small application fee of $20."),
    ],
)
def test_excluidos_y_estafas_se_descartan(field, text):
    job = make_job(**{field: text})
    assert check_excluded(job, EXCLUDED).startswith("rubro excluido")


# ------------------------------------------------------------------- pipeline

def test_apply_filters_separa_y_cuenta_motivos():
    jobs = [
        make_job(source_id="1"),                                  # pasa
        make_job(source_id="2", title="Sales Manager"),           # rubro
        make_job(source_id="3", location="USA"),                  # ubicación
        make_job(source_id="4", description="Fluent English."),   # inglés
        make_job(source_id="5", description="MLM opportunity"),   # excluido
    ]
    res = apply_filters(jobs, keywords=KEYWORDS, excluded=EXCLUDED)
    assert [j.source_id for j in res.kept] == ["1"]
    assert res.rejected == {
        "rubro no buscado": 1,
        "ubicación no aceptada": 1,
        "exige inglés avanzado": 1,
        "rubro excluido / estafa": 1,
    }


def test_apply_filters_guarda_motivo_y_oferta_para_depurar():
    job = make_job(title="Sales Manager")
    res = apply_filters([job], keywords=KEYWORDS, excluded=EXCLUDED)
    assert res.rejected_jobs == [("rubro no buscado", job)]


def test_apply_filters_lista_vacia():
    res = apply_filters([], keywords=KEYWORDS, excluded=EXCLUDED)
    assert res.kept == [] and not res.rejected

@pytest.mark.skipif(
    __import__("src.paths", fromlist=["using_template"]).using_template(),
    reason="valida TU me/keywords.txt: en el template público no aplica",
)

@pytest.mark.parametrize(
    "title",
    [
        "AI Trainer - Video Annotation",          # real, Remotive
        "Remote Office Assistant",                # real, Remotive (falso negativo)
        "Virtual Assistant",
        "Asistente Administrativo/a",
        "Analista de Calidad de Software",
        "Mesa de Ayuda",
    ],
)
def test_keywords_reales_cubren_titulos_buscados(title):
    """Regresión: títulos reales que el filtro descartaba por error (falsos negativos)."""
    assert check_role(make_job(title=title), load_list("keywords.txt")) is None

# ------------------------------------------------- región en el título (#41)

from src.filters import check_title_region  # noqa: E402

REGIONS = ["US", "USA", "United States", "UK", "Canada"]


@pytest.mark.parametrize(
    "title",
    [
        "Data Annotator - US",          # caso real (Expedock, Himalayas)
        "QA Engineer – USA",
        "Support Agent (UK)",
        "QA Analyst | Canada",
        "Customer Success, US",
        "QA Engineer - US only",
        "US-based QA Engineer",
        "Remote QA (USA) - Contract",
        "Support Specialist US Only",
        "US Remote Patient Care Advocate",       # caso real (WWR)
        "Remote AI Training - $20/hr - United States",   # caso real (WWR)
    ],
)
def test_titulo_restringido_a_otra_region_se_descarta(title):
    assert check_title_region(make_job(title=title), REGIONS)


@pytest.mark.parametrize(
    "title",
    [   # falsos positivos que NO tienen que descartarse
        "Data Annotator - LATAM",
        "Business Analyst",             # "us" dentro de otra palabra
        "QA for US clients",            # trabaja PARA clientes de US, no dice "only"
        "Payments QA (USD settlements)",
        "Customer Support",
        "QA Engineer - Argentina",
        "USB Testing Engineer",                 
    ],
)

def test_titulo_sin_restriccion_pasa(title):
    assert check_title_region(make_job(title=title), REGIONS) is None


def test_blocklist_vacia_no_descarta_nada():
    # Un fork en US deja la lista vacía y no pierde nada
    assert check_title_region(make_job(title="Data Annotator - US"), []) is None


def test_apply_filters_usa_la_blocklist():
    jobs = [make_job(title="QA Analyst - US"), make_job(title="QA Analyst - LATAM")]
    result = apply_filters(jobs, keywords=["qa"], excluded=[], title_regions=["US"])
    assert [j.title for j in result.kept] == ["QA Analyst - LATAM"]
    assert result.rejected["título restringido a otra región"] == 1


# ------------------------------------------------- idioma en el título

from src.filters import check_title_language  # noqa: E402

SPOKEN = ["Spanish", "English"]


@pytest.mark.parametrize(
    "title",
    [
        "Oromo - AI Product Evaluator",                         # caso real (Himalayas)
        "Customer Support Specialist | German and English",     # caso real: pide alemán
        "Portuguese Speaking QA Analyst",
        "Atención al cliente con portugués",
        "French Content Rater",
        "Japanese Language AI Trainer",
        "Polish Speaker - Customer Support",
    ],
)
def test_titulo_con_idioma_que_no_hablas_se_descarta(title):
    assert check_title_language(make_job(title=title), SPOKEN) == "pide un idioma que no hablás"


@pytest.mark.parametrize(
    "title",
    [
        "Spanish Speaking QA Analyst",
        "Bilingual Customer Support (English/Spanish)",
        "QA Engineer",
        "Polish the UI - QA Intern",                            # "polish" como verbo: pasa
        "AI Evaluator - Español",
        "Thailand Partnerships",                                # "thai" dentro de otra palabra
    ],
)
def test_titulo_sin_idioma_ajeno_pasa(title):
    assert check_title_language(make_job(title=title), SPOKEN) is None


def test_idiomas_se_pueden_escribir_en_castellano():
    assert check_title_language(make_job(title="Soporte en portugués"), ["Español", "Portugués"]) is None


def test_lista_vacia_no_filtra_por_idioma():
    assert check_title_language(make_job(title="German Support"), []) is None


def test_apply_filters_usa_los_idiomas():
    jobs = [make_job(title="QA - German"), make_job(title="QA Analyst")]
    result = apply_filters(jobs, keywords=["qa"], excluded=[], title_regions=[], spoken_languages=["English"])
    assert [j.title for j in result.kept] == ["QA Analyst"]