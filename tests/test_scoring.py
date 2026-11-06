"""
Tests del % de match. Usan un embedder FALSO: no descargan el modelo ni
necesitan internet. Así se prueba la lógica del puntaje por separado del modelo.
"""
import pytest

from src import scoring
from src.models import Job
from src.scoring import cosine, rescale, role_score, score_jobs, skill_score

PROFILE = "QA Engineer fintech. Testing de APIs con Postman y SQL."
SKILLS = ["postman", "sql", "fintech", "gherkin", "jira", "aws"]


def make_job(i=1, **overrides) -> Job:
    data = {
        "source": "Test", "source_id": str(i), "title": "QA Engineer", "company": f"C{i}",
        "url": f"https://example.com/{i}", "description": "",
    }
    data.update(overrides)
    return Job(**data)


class FakeEmbedder:
    """
    Vector de 3 dimensiones según palabras clave: [qa/testing, ventas, fintech].
    Textos parecidos -> vectores parecidos, igual que un modelo real pero predecible.
    """

    def __init__(self):
        self.calls = 0

    def embed(self, texts):
        self.calls += 1
        out = []
        for t in texts:
            t = t.lower()
            out.append([
                1.0 if ("qa" in t or "test" in t) else 0.0,
                1.0 if "sales" in t else 0.0,
                1.0 if "fintech" in t else 0.1,
            ])
        return out


# ---------------------------------------------------------------- piezas

def test_cosine():
    assert cosine([1, 0], [1, 0]) == pytest.approx(1.0)
    assert cosine([1, 0], [0, 1]) == pytest.approx(0.0)
    assert cosine([0, 0], [1, 1]) == 0.0          # vector vacío: no explota


@pytest.mark.parametrize(
    "sim, expected",
    [
        (scoring.SIM_FLOOR, 0.0),
        (scoring.SIM_CEIL, 1.0),
        (0.0, 0.0),                    # por debajo: se recorta
        (0.99, 1.0),                   # por encima: se recorta
        ((scoring.SIM_FLOOR + scoring.SIM_CEIL) / 2, 0.5),
    ],
)
def test_rescale_valores_limite(sim, expected):
    assert rescale(sim) == pytest.approx(expected)


def test_skill_score_cuenta_y_satura():
    assert skill_score("Nada que ver", SKILLS) == 0
    assert skill_score("Postman y SQL", SKILLS) == pytest.approx(2 / scoring.SKILLS_FOR_FULL)
    assert skill_score("postman sql fintech gherkin jira aws", SKILLS) == 1.0   # tope en 1


# ---------- role_score(): tu TODO ----------

@pytest.mark.parametrize(
    "title, expected",
    [
        ("QA Automation Engineer", 1.0),
        ("Senior Tester", 1.0),
        ("Analista Funcional Fintech", 0.8),
        ("Data Annotation Specialist", 0.6),
        ("AI Trainer - Video Annotation", 0.6),        # real, Remotive
        ("Customer Support Specialist", 0.4),
        ("Senior Sales Manager", 0.0),
        ("QA Analyst - Customer Support", 1.0),        # gana el PRIMER grupo (QA)
    ],
)
def test_role_score(title, expected):
    assert role_score(title) == expected


# ---------------------------------------------------------- score_jobs()

def test_qa_fintech_le_gana_a_ventas():
    qa = make_job(1, title="QA Engineer", description="Fintech, Postman, SQL, Jira.")
    sales = make_job(2, title="Sales Manager", description="Sell our product.")
    scores = score_jobs([qa, sales], PROFILE, FakeEmbedder(), skills=SKILLS)
    assert scores[qa.uid] > scores[sales.uid]


def test_porcentajes_entre_0_y_100():
    jobs = [make_job(1, title="QA", description="postman sql fintech gherkin jira aws"),
            make_job(2, title="Sales", description="")]
    for pct in score_jobs(jobs, PROFILE, FakeEmbedder(), skills=SKILLS).values():
        assert 0 <= pct <= 100


def test_ingles_a_revisar_baja_puntos():
    base = make_job(1, description="Postman and SQL.")
    revisar = make_job(2, description="Postman and SQL. Excellent English communication skills.")
    scores = score_jobs([base, revisar], PROFILE, FakeEmbedder(), skills=SKILLS)
    assert scores[base.uid] - scores[revisar.uid] == scoring.ENGLISH_REVIEW_PENALTY


def test_un_solo_llamado_al_modelo_para_todas_las_ofertas():
    embedder = FakeEmbedder()
    score_jobs([make_job(i) for i in range(20)], PROFILE, embedder, skills=SKILLS)
    assert embedder.calls == 1


def test_sin_ofertas_no_llama_al_modelo():
    embedder = FakeEmbedder()
    assert score_jobs([], PROFILE, embedder, skills=SKILLS) == {}
    assert embedder.calls == 0


# --------------------------------------------------------- default_scorer

def test_sin_profile_text_no_hay_scoring(monkeypatch):
    # Sin el secret (tests, tu compu): el bot sigue funcionando, ordenado por fecha
    monkeypatch.delenv("PROFILE_TEXT", raising=False)
    assert scoring.default_scorer([make_job()]) is None


def test_skills_txt_real_carga():
    # Funciona con me/ (tu repo) y con templates/me/ (el template público)
    from src.filters import load_list
    assert load_list("skills.txt")


# ------------------------------------------------------------------ gaps

from src.gaps import GAP_PENALTY  # noqa: E402


def test_gaps_obligatorios_bajan_el_match():
    sin_gaps = make_job(1, description="Testing de APIs con Postman.")
    con_gaps = make_job(2, description="Testing de APIs con Postman. Requisito: Cypress y Java.")
    scores = score_jobs([sin_gaps, con_gaps], PROFILE, FakeEmbedder(),
                        skills=SKILLS, tech=["cypress", "java"])
    assert scores[con_gaps.uid] == scores[sin_gaps.uid] - 2 * GAP_PENALTY


def test_gaps_deseables_no_bajan_el_match():
    sin_gaps = make_job(1, description="Testing de APIs con Postman.")
    deseable = make_job(2, description="Testing de APIs con Postman. Cypress es un plus.")
    scores = score_jobs([sin_gaps, deseable], PROFILE, FakeEmbedder(),
                        skills=SKILLS, tech=["cypress", "java"])
    assert scores[deseable.uid] == scores[sin_gaps.uid]
