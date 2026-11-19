"""
Tests de gaps. Usan listas chicas armadas acá (no los .txt de config/):
así un cambio en tu config no rompe los tests.
"""
import pytest

from src.gaps import GAP_MAX_PENALTY, GAP_PENALTY, find_gaps, gap_penalty, is_soft, mark_desirable

TECH = ["playwright", "cypress", "java", "crm", "dynamics 365", "sql", "c#"]
SKILLS = ["sql", "postman", "jira"]


# -------------------------------------------------- obligatorio vs deseable

@pytest.mark.parametrize(
    "description, expected",
    [
        ("Experiencia con Playwright.", ["playwright"]),
        ("Requisitos: Java y Cypress.", ["cypress", "java"]),          # orden de TECH
        ("Cypress es un plus.", []),                                   # deseable
        ("Nice to have: Playwright.", []),
        ("Se valora experiencia en Java.", []),
        ("Java excluyente. Cypress es un plus.", ["java"]),            # oración por oración
        ("Experiencia con SQL y Postman.", []),                        # ya son tus skills
        ("Testing de soluciones Microsoft Dynamics 365 CRM.", ["crm", "dynamics 365"]),
        ("Buscamos QA manual.", []),                                   # no pide nada de TECH
        ("", []),
    ],
)
def test_find_gaps(description, expected):
    assert find_gaps(description, TECH, SKILLS) == expected


def test_palabra_completa_no_matchea_dentro_de_otra():
    # "java" no tiene que matchear "javascript"
    assert find_gaps("Experiencia con JavaScript.", TECH, SKILLS) == []


def test_un_gap_repetido_cuenta_una_vez():
    assert find_gaps("Playwright. Más Playwright. Playwright.", TECH, SKILLS) == ["playwright"]


def test_se_queda_con_el_termino_mas_largo():
    assert find_gaps("Dynamics 365 y Dynamics.", ["dynamics", "dynamics 365"], []) == ["dynamics 365"]


@pytest.mark.parametrize(
    "sentence, expected",
    [("cypress es un plus", True), ("nice to have: java", True),
     ("surplus de java", False), ("java requerido", False)],
)
def test_is_soft(sentence, expected):
    assert is_soft(sentence) is expected


# ------------------------------------------------------- penalización (BVA)

@pytest.mark.parametrize(
    "n_gaps, expected",
    [
        (0, 0),
        (1, GAP_PENALTY),
        (GAP_MAX_PENALTY // GAP_PENALTY, GAP_MAX_PENALTY),       # justo en el tope
        (GAP_MAX_PENALTY // GAP_PENALTY + 1, GAP_MAX_PENALTY),   # pasa el tope: no resta más
        (20, GAP_MAX_PENALTY),
    ],
)
def test_gap_penalty_valores_limite(n_gaps, expected):
    assert gap_penalty(["x"] * n_gaps) == expected


# ------------------------------------------------- secciones "desirable"

def test_mark_desirable_hace_que_no_cuente_como_gap():
    text = mark_desirable("Experiencia con Cypress.\nConocimientos de Java")
    assert find_gaps(text, TECH, SKILLS) == []


# ------------------------------------------- regresión con un aviso real

def test_regresion_aviso_dynamics_365():
    """
    Bug de producción: el bot le dio 100% y el evaluador de CV ~45%
    (pedía testing de CRM y automatización de UI). Usa TU config real a propósito:
    si un día sumás Dynamics a skills.txt, este test te avisa que cambió el criterio.
    """
    from pathlib import Path
    from src.filters import load_list

    text = (Path(__file__).parent / "fixtures" / "dynamics_job.txt").read_text(encoding="utf-8")
    gaps = find_gaps(text, load_list("tech.txt"), load_list("skills.txt"))
    assert gap_penalty(gaps) >= 2 * GAP_PENALTY, gaps
