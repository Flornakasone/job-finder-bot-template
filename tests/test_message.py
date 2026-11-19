from datetime import date

import pytest

from src.message import MAX_LEN, build_messages, format_job, location_label
from src.models import Job

TODAY = date(2026, 10, 29)


def make_job(**overrides) -> Job:
    data = {
        "source": "Remotive",
        "source_id": "1",
        "title": "QA Engineer",
        "company": "Acme",
        "url": "https://remotive.com/remote-jobs/qa/1",
        "location": "Worldwide",
    }
    data.update(overrides)
    return Job(**data)


@pytest.mark.parametrize(
    "location, expected",
    [
        ("Worldwide", "Remoto global"),
        ("Anywhere", "Remoto global"),
        ("LATAM", "Remoto LATAM"),
        ("América Latina", "Remoto LATAM"),
        ("Buenos Aires, Argentina (Hybrid)", "Buenos Aires, Argentina (Hybrid)"),
        ("", "Sin ubicación"),
        ("Argentina, Brazil, Chile, Mexico, Peru", "Argentina + 4 países"),
        ("Brazil, Argentina", "Brazil, Argentina"),       
        ("Argentina", "Argentina")],
    
)
def test_location_label(location, expected):
    assert location_label(location) == expected



def test_format_job_incluye_link_y_atribucion_de_la_fuente():
    text = format_job(make_job())
    assert "QA Engineer – Acme" in text
    assert "📍 Remoto global" in text
    # Los términos de Remotive/Jobicy exigen link original + nombrar la fuente
    assert "https://remotive.com/remote-jobs/qa/1" in text
    assert "vía Remotive" in text


def test_format_job_sin_empresa_no_deja_guion_suelto():
    assert "🔹 QA Engineer\n" in format_job(make_job(company=""))


def test_sin_ofertas_manda_mensaje_corto():
    msgs = build_messages([], TODAY, total_checked=210)
    assert len(msgs) == 1
    assert "no hay ofertas nuevas" in msgs[0]
    assert "210" in msgs[0]


def test_encabezado_con_fecha_y_cantidades():
    msgs = build_messages([make_job()], TODAY, total_checked=210)
    assert msgs[0].startswith("🗂 29/10 · 1 ofertas nuevas (de 210 revisadas)")


def test_texto_largo_se_parte_sin_cortar_ofertas():
    jobs = [make_job(source_id=str(i), title="QA " + "x" * 300,
                     url=f"https://remotive.com/remote-jobs/qa/{i}/") for i in range(30)]
    msgs = build_messages(jobs, TODAY, total_checked=30)
    assert len(msgs) > 1
    assert all(len(m) <= MAX_LEN for m in msgs)
    # Cada oferta aparece entera exactamente una vez
    todo = "\n\n".join(msgs)
    for j in jobs:
        assert todo.count(j.url) == 1


def test_el_titulo_aparece_una_sola_vez():
    text = format_job(make_job(), score=80)
    assert text.count("QA Engineer") == 1

# ------------------------------------------------- evaluación con IA (#16)

from src.evaluate import Evaluation  # noqa: E402

EVAL = Evaluation("GO_CON_RESERVAS", "QA fintech y APIs", "Cypress")


def test_format_job_con_evaluacion_muestra_veredicto_aporto_y_falta():
    text = format_job(make_job(), score=80, evaluation=EVAL)
    assert "🧭 🟡 Postulate con reservas" in text
    assert "✅ Cumplo: QA fintech y APIs" in text
    assert "⚠️ Falta: Cypress" in text
    assert text.endswith("(vía Remotive)")       # el link sigue siendo la última línea


def test_format_job_sin_evaluacion_no_muestra_lineas_de_ia():
    text = format_job(make_job(), score=80)
    assert "🧭" not in text and "Aporto" not in text


def test_build_messages_usa_la_evaluacion_de_cada_oferta():
    con, sin = make_job(source_id="1"), make_job(source_id="2", url="<https://remotive.com/remote-jobs/qa/2>")
    msg = build_messages([con, sin], TODAY, total_checked=2, evaluations={con.uid: EVAL})[0]
    assert msg.count("🧭") == 1