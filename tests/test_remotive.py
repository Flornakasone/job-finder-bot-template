"""
Tests de la fuente Remotive.
Nunca llaman a la API real: usan un JSON de ejemplo (fixture) y una
sesión falsa. Así son rápidos, no dependen de internet y no gastan
las 4 requests diarias que permite Remotive.
"""
import json
from pathlib import Path

import pytest
import requests

from src.sources import SourceError, remotive
from tests.fakes import FakeResponse, FakeSession

FIXTURE = Path(__file__).parent / "fixtures" / "remotive_sample.json"


@pytest.fixture
def sample_data() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


# ---------- parse() ----------

def test_parse_saltea_ofertas_incompletas(sample_data):
    jobs = remotive.parse(sample_data)
    # 4 en el JSON, 2 rotas (sin título / sin id) -> quedan 2
    assert [j.source_id for j in jobs] == ["1001", "1002"]


def test_parse_mapea_los_campos(sample_data):
    job = remotive.parse(sample_data)[0]
    assert job.source == "Remotive"
    assert job.title == "QA Automation Engineer"  # sin espacios extra
    assert job.company == "Ejemplo Fintech"
    assert job.location == "Worldwide"
    assert job.url.startswith("https://remotive.com/")
    assert job.published_at == "2026-10-20T10:23:26"


def test_parse_limpia_y_deduplica_tags(sample_data):
    # Hallazgo del contract check: la API real trae "tags" con espacios
    # sobrantes ("Typescript "); además probamos repetidos y vacíos
    job = remotive.parse(sample_data)[0]
    assert job.tags == ("QA", "full_time", "python", "Typescript", "testing")


def test_parse_limpia_el_html(sample_data):
    desc = remotive.parse(sample_data)[0].description
    assert "<" not in desc
    assert "QA Engineer" in desc
    assert "alert" not in desc        # el contenido de <script> se descarta
    assert "blank.gif" not in desc    # el pixel de tracking no queda en el texto
    assert "\xa0" not in desc         # los espacios duros se normalizan


def test_parse_tolera_campos_vacios(sample_data):
    job = remotive.parse(sample_data)[1]
    assert job.company == ""      # company_name venía null
    assert job.description == ""
    assert job.tags == ("Customer Service",)  # job_type vacío no se agrega


def test_parse_respuesta_sin_jobs():
    assert remotive.parse({}) == []


# ---------- fetch() con sesión falsa ----------

def test_fetch_hace_una_sola_request(sample_data):
    session = FakeSession(FakeResponse(sample_data))
    jobs = remotive.fetch(session)
    assert session.calls == 1
    assert len(jobs) == 2


@pytest.mark.parametrize(
    "session",
    [
        FakeSession(FakeResponse(status=429)),                 # nos bloquearon
        FakeSession(FakeResponse(status=500)),                 # la API se cayó
        FakeSession(FakeResponse(payload=None)),               # respuesta que no es JSON
        FakeSession(error=requests.ConnectionError("sin red")),
        FakeSession(error=requests.Timeout("lento")),
    ],
    ids=["429", "500", "no-json", "sin-red", "timeout"],
)
def test_fetch_convierte_errores_en_source_error(session):
    with pytest.raises(SourceError, match="Remotive"):
        remotive.fetch(session)
