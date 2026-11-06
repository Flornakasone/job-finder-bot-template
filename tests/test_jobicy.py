"""
Tests de la fuente Jobicy (escritos ANTES que el código: TDD).
Nunca llaman a la API real.
"""
import json
from pathlib import Path

import pytest
import requests

from src.sources import SourceError, jobicy
from tests.fakes import FakeResponse, FakeSession

FIXTURE = Path(__file__).parent / "fixtures" / "jobicy_sample.json"


@pytest.fixture
def sample_data() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


# ---------- parse() ----------

def test_parse_saltea_ofertas_incompletas(sample_data):
    jobs = jobicy.parse(sample_data)
    assert [j.source_id for j in jobs] == ["2001", "2002"]


def test_parse_mapea_los_campos(sample_data):
    job = jobicy.parse(sample_data)[0]
    assert job.source == "Jobicy"
    assert job.url == "https://jobicy.com/jobs/2001-qa-analyst"
    assert job.location == "LATAM"
    assert job.published_at == "2026-10-21T12:00:00+00:00"


def test_parse_decodifica_entidades_html_en_titulo_y_empresa(sample_data):
    # Jobicy manda "&#8211;" y "&amp;" en vez de "–" y "&"
    job = jobicy.parse(sample_data)[0]
    assert job.title == "QA Analyst – Payments & Reconciliation"
    assert job.company == "Ejemplo & Cía"


def test_parse_limpia_el_html_de_la_descripcion(sample_data):
    desc = jobicy.parse(sample_data)[0].description
    assert desc == "Test payments flows."


def test_parse_usa_el_excerpt_si_no_hay_descripcion(sample_data):
    job = jobicy.parse(sample_data)[1]
    assert job.description == "Only an excerpt, no description."


def test_parse_arma_tags_con_industria_tipo_y_nivel(sample_data):
    jobs = jobicy.parse(sample_data)
    assert jobs[0].tags == ("Technical Support", "QA", "full-time", "Midweight")
    assert jobs[1].tags == ()  # listas vacías y nivel vacío no agregan nada


def test_parse_respuesta_sin_jobs():
    assert jobicy.parse({}) == []


# ---------- fetch() ----------

def test_fetch_pide_200_ofertas_en_una_sola_request(sample_data):
    session = FakeSession(FakeResponse(sample_data))
    jobs = jobicy.fetch(session)
    assert session.calls == 1
    assert session.last_params == {"count": 200}
    assert len(jobs) == 2


@pytest.mark.parametrize(
    "session",
    [
        FakeSession(FakeResponse(status=429)),
        FakeSession(FakeResponse(payload=None)),
        FakeSession(error=requests.Timeout("lento")),
    ],
    ids=["429", "no-json", "timeout"],
)
def test_fetch_convierte_errores_en_source_error(session):
    with pytest.raises(SourceError, match="Jobicy"):
        jobicy.fetch(session)
