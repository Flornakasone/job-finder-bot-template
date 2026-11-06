"""
Tests de la fuente Get on Board (TDD: escritos antes que el código).
El fixture copia la estructura REAL vista en el contract check (JSON:API + expand).
Nunca llaman a la API real.
"""
import json
from pathlib import Path

import pytest
import requests

from src.filters import check_location
from src.sources import SourceError, getonbrd
from tests.fakes import FakeResponse

FIXTURE = Path(__file__).parent / "fixtures" / "getonbrd_sample.json"


@pytest.fixture
def jobs() -> dict:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {j.source_id: j for j in getonbrd.parse(data)}


# ---------- parse(): campos básicos ----------

def test_parse_saltea_ofertas_incompletas(jobs):
    assert "roto-sin-link" not in jobs
    assert "roto-sin-titulo" not in jobs
    assert len(jobs) == 8


def test_parse_mapea_los_campos(jobs):
    job = jobs["qa-fully-remote"]
    assert job.source == "Get on Board"
    assert job.title == "QA Analyst & Tester"            # entidades HTML decodificadas
    assert job.company == "Improving"                    # sale del company expandido
    assert job.url == "https://www.getonbrd.com/jobs/qa-fully-remote"
    assert job.published_at.startswith("2026-")


def test_fecha_invalida_queda_vacia(jobs):
    assert jobs["qa-sin-fecha"].published_at == ""


def test_descripcion_junta_las_secciones_menos_beneficios(jobs):
    desc = jobs["qa-fully-remote"].description
    for texto in ("Testing de APIs", "Diseñar casos de prueba", "Postman", "Proyecto fintech"):
        assert texto in desc
    # "Clases de inglés avanzado" es un beneficio, no un requisito:
    # si entrara, el filtro de inglés descartaría la oferta por error
    assert "inglés" not in desc


# ---------- _location(): la ubicación sale de remote_modality ----------

@pytest.mark.parametrize(
    "source_id, expected",
    [
        ("qa-fully-remote", "Worldwide"),
        ("go-engineer-microservices-improving-remote", "Mexico, Costa Rica, Colombia"),  # real
        ("qa-remote-argentina", "Argentina, Chile"),
        ("qa-hibrido-baires", "Buenos Aires (Híbrido)"),
        ("qa-hibrido-santiago", "Santiago (Híbrido)"),
        ("qa-presencial-baires", "Buenos Aires (Presencial)"),
        ("qa-modalidad-nueva", ""),          # valor desconocido: más seguro descartar
    ],
)
def test_location_segun_remote_modality(jobs, source_id, expected):
    assert jobs[source_id].location == expected


# ---------- integración con el filtro de ubicación ----------

@pytest.mark.parametrize(
    "source_id, pasa",
    [
        ("qa-fully-remote", True),
        ("qa-remote-argentina", True),
        ("qa-hibrido-baires", True),
        ("go-engineer-microservices-improving-remote", False),  # "Remote" engañoso (real)
        ("qa-hibrido-santiago", False),
        ("qa-presencial-baires", True),
        ("qa-modalidad-nueva", False),
    ],
)
def test_filtro_de_ubicacion_con_ofertas_de_get_on_board(jobs, source_id, pasa):
    assert (check_location(jobs[source_id]) is None) is pasa


# ---------- fetch() ----------

class SessionPorQuery:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.params_seen = []

    def get(self, url, **kwargs):
        assert kwargs.get("timeout"), "siempre hay que pasar timeout"
        params = kwargs["params"]
        self.params_seen.append(params)
        r = self.responses.get(params["query"], FakeResponse({"data": []}))
        if isinstance(r, Exception):
            raise r
        return r


def test_fetch_hace_una_busqueda_por_termino_con_expand():
    session = SessionPorQuery()
    getonbrd.fetch(session)
    assert [p["query"] for p in session.params_seen] == getonbrd.QUERIES
    for p in session.params_seen:
        assert p["per_page"] == 100
        assert "company" in p["expand"] and "location_tenants" in p["expand"]


def test_fetch_sigue_si_falla_una_busqueda():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    session = SessionPorQuery({"qa": requests.Timeout("lento"), "tester": FakeResponse(data)})
    assert len(getonbrd.fetch(session)) == 8


def test_fetch_falla_si_fallan_todas():
    session = SessionPorQuery({q: requests.Timeout("lento") for q in getonbrd.QUERIES})
    with pytest.raises(SourceError, match="Get on Board"):
        getonbrd.fetch(session)

def test_seccion_desirable_no_cuenta_como_gap():
    # Get on Board separa lo deseable en su propio campo: no tiene que restar
    from src.gaps import find_gaps
    from src.sources.getonbrd import _description

    attrs = {"description": "<p>QA manual.</p>", "desirable": "<p>Experiencia con Cypress.</p>"}
    assert find_gaps(_description(attrs), ["cypress"], []) == []


def test_requisito_en_description_si_cuenta_como_gap():
    from src.gaps import find_gaps
    from src.sources.getonbrd import _description

    attrs = {"description": "<p>Experiencia con Cypress.</p>", "desirable": ""}
    assert find_gaps(_description(attrs), ["cypress"], []) == ["cypress"]
