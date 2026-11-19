"""Tests del language gate. Los casos 'real' salen de avisos vistos en las fuentes."""
import pytest

from src.language import english_label, english_requirement, strongest


# ---------- strongest(): tu TODO ----------

@pytest.mark.parametrize(
    "levels, expected",
    [
        ([], ""),
        (["", ""], ""),
        (["deseable"], "deseable"),
        (["deseable", "excluyente", "intermedio"], "excluyente"),
        (["intermedio", "deseable"], "intermedio"),
        (["", "revisar", "deseable"], "revisar"),
    ],
)
def test_strongest_devuelve_el_mas_exigente(levels, expected):
    assert strongest(levels) == expected


# ---------- english_requirement() ----------

@pytest.mark.parametrize(
    "description, expected",
    [
        # excluyente
        ("ADVANCED ENGLISH IS A MUST, you won't be considered if your are not fluent", "excluyente"),  # real, Get on Board
        ("Requirements: fluent English.", "excluyente"),
        ("Inglés avanzado excluyente.", "excluyente"),
        ("Nivel avanzado de inglés.", "excluyente"),
        ("Native English speaker", "excluyente"),
        # revisar (ambiguo)
        ("Dominio del idioma inglés.", "revisar"),
        ("Excelente nivel de inglés oral y escrito.", "revisar"),
        ("Strong written and verbal English communication skills.", "revisar"),
        ("Professional working proficiency in English.", "revisar"),
        # intermedio
        ("Intermediate English required.", "intermedio"),
        ("Inglés intermedio (B2).", "intermedio"),
        # deseable
        ("Fluent English is a plus.", "deseable"),
        ("Inglés avanzado deseable.", "deseable"),
        ("Strong English skills are nice to have.", "deseable"),
        # no dice nada
        ("Experience with Postman and SQL.", ""),
        ("", ""),
    ],
)
def test_english_requirement(description, expected):
    assert english_requirement(description) == expected


def test_cada_oracion_se_evalua_por_separado():
    # El "plus" de la 2.ª oración no suaviza la 1.ª
    assert english_requirement("Fluent English required. Python is a plus.") == "excluyente"


def test_gana_la_oracion_mas_exigente():
    desc = "Intermediate English. Excellent English communication skills."
    assert english_requirement(desc) == "revisar"


# ---------- english_label(): lo que ves en Telegram ----------

@pytest.mark.parametrize(
    "description, expected",
    [
        ("Dominio del idioma inglés.", "revisar el requisito ⚠️"),
        ("Intermediate English required.", "intermedio"),
        ("Fluent English is a plus.", "deseable"),
        ("You will test our APIs and work with the QA team.", "no indica nivel (aviso en inglés)"),
        ("Vas a probar las APIs con el equipo de QA para la app.", "no menciona"),
    ],
)
def test_english_label(description, expected):
    assert english_label(description) == expected

# ---------- excepción: solo inglés ESCRITO avanzado ----------

@pytest.mark.parametrize(
    "description, expected",
    [
        ("Fluent written English required.", "revisar"),            # típico de data annotation
        ("Native-level English writing skills.", "revisar"),
        ("Inglés escrito avanzado.", "revisar"),
        ("Fluent written and spoken English.", "excluyente"),       # pide también hablado
        ("Fluent English, both written and verbal.", "excluyente"),
        ("Fluent English required.", "excluyente"),                 # no aclara: se asume hablado
    ],
)
def test_ingles_avanzado_solo_escrito_pasa_como_revisar(description, expected):
    assert english_requirement(description) == expected