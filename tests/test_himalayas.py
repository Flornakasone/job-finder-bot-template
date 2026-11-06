"""
Tests de la fuente Himalayas (TDD: escritos antes que el código).
Nunca llaman a la API real.
"""
import json
from pathlib import Path

import pytest
import requests

from src.sources import SourceError, himalayas
from tests.fakes import FakeResponse, FakeSession

FIXTURE = Path(__file__).parent / "fixtures" / "himalayas_sample.json"


@pytest.fixture
def sample_data() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


# ---------- parse() ----------

def test_parse_saltea_ofertas_incompletas(sample_data):
    assert [j.source_id for j in himalayas.parse(sample_data)] == ["hm-3001", "hm-3002"]


def test_parse_usa_application_link_como_url(sample_data):
    # Lo exigen los términos de Himalayas
    job = himalayas.parse(sample_data)[0]
    assert job.url == "https://himalayas.app/companies/ejemplo/jobs/qa-analyst"
    assert job.source == "Himalayas"


def test_parse_decodifica_entidades_html(sample_data):
    job = himalayas.parse(sample_data)[0]
    assert job.title == "QA Analyst & Tester"
    assert job.company == "Ejemplo & Co"


def test_sin_restricciones_de_ubicacion_es_worldwide(sample_data):
    assert himalayas.parse(sample_data)[0].location == "Worldwide"


def test_restricciones_de_ubicacion_se_unen_con_comas(sample_data):
    assert himalayas.parse(sample_data)[1].location == "Argentina, Brazil"


def test_pubdate_unix_se_convierte_a_iso(sample_data):
    assert himalayas.parse(sample_data)[0].published_at.startswith("2026-10-29")


def test_pubdate_invalida_queda_vacia(sample_data):
    assert himalayas.parse(sample_data)[1].published_at == ""


def test_descripcion_limpia_o_excerpt(sample_data):
    jobs = himalayas.parse(sample_data)
    assert jobs[0].description == "Test payments."
    assert jobs[1].description == "Only an excerpt."


def test_tags_con_seniority_como_lista_o_texto(sample_data):
    # La doc de Himalayas es inconsistente: seniority puede ser lista o texto
    jobs = himalayas.parse(sample_data)
    assert jobs[0].tags == ("Quality Assurance", "Testing", "Mid-level", "Full Time")
    assert jobs[1].tags == ("Entry-level", "Contractor")


# ---------- fetch() ----------

class SessionPorQuery(FakeSession):
    """Responde distinto según la búsqueda: sirve para simular fallas parciales."""

    def __init__(self, responses):
        super().__init__()
        self.responses = responses  # query -> FakeResponse o excepción
        self.queries = []

    def get(self, url, **kwargs):
        self.calls += 1
        self.params_seen = getattr(self, "params_seen", []) + [kwargs["params"]]
        query = kwargs["params"]["q"]
        self.queries.append(query)
        r = self.responses.get(query, FakeResponse({"jobs": []}))
        if isinstance(r, Exception):
            raise r
        return r


def test_fetch_hace_una_busqueda_por_termino(sample_data):
    session = SessionPorQuery({"QA": FakeResponse(sample_data)})
    jobs = himalayas.fetch(session)
    assert session.queries == himalayas.QUERIES
    assert len(jobs) == 2


def test_fetch_sigue_si_falla_una_busqueda(sample_data):
    session = SessionPorQuery({
        "QA": requests.Timeout("lento"),
        "tester": FakeResponse(sample_data),
    })
    assert len(himalayas.fetch(session)) == 2


def test_fetch_falla_si_fallan_todas_las_busquedas():
    session = SessionPorQuery({q: requests.Timeout("lento") for q in himalayas.QUERIES})
    with pytest.raises(SourceError, match="Himalayas"):
        himalayas.fetch(session)


def test_location_restrictions_null_es_worldwide():
    # La API puede mandar null: la oferta no se tiene que perder
    data = {"jobs": [{
        "guid": "hm-9", "title": "QA Tester", "companyName": "X",
        "applicationLink": "https://himalayas.app/x",
        "locationRestrictions": None,
    }]}
    jobs = himalayas.parse(data)
    assert len(jobs) == 1
    assert jobs[0].location == "Worldwide"


@pytest.mark.parametrize(
    "restrictions, expected",
    [
        (["Brazil"], "Brazil"),                                   # real (contract check)
        (["Philippines", "Mexico"], "Philippines, Mexico"),       # real
        ([{"name": "Argentina"}], "Argentina"),                   # formato de la doc
        ([], "Worldwide"),
        (None, "Worldwide"),
    ],
)

def test_location_acepta_textos_y_objetos(restrictions, expected):
    data = {"jobs": [{
        "guid": "hm-1", "title": "QA Tester", "companyName": "X",
        "applicationLink": "https://himalayas.app/x",
        "locationRestrictions": restrictions,
    }]}
    jobs = himalayas.parse(data)
    assert len(jobs) == 1               # la oferta NO se pierde
    assert jobs[0].location == expected

def test_fetch_pide_solo_ofertas_abiertas_a_argentina():
    session = SessionPorQuery({})
    himalayas.fetch(session)
    assert all(p["country"] == "AR" for p in session.params_seen)