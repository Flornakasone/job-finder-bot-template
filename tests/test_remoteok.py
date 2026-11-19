"""
Tests de la fuente Remote OK. Nunca llaman a la API real.

Dos tipos de tests:
- Con datos armados acá: casos puntuales (aviso legal, ofertas rotas, HTML).
- Con el fixture REAL (remoteok_sample.json, sacado del feed): contract check.
  Si Remote OK cambia el formato, estos tests lo detectan.
"""
import json
from pathlib import Path

import pytest
import requests

from src.sources import SourceError, remoteok
from tests.fakes import FakeResponse, FakeSession

FIXTURE = Path(__file__).parent / "fixtures" / "remoteok_sample.json"

LEGAL = {"last_updated": 1730000000, "legal": "Please link back to the URL on Remote OK..."}
JOB = {
    "id": "1092345", "position": "QA Engineer", "company": "Acme",
    "url": "https://remoteOK.com/remote-jobs/remote-qa-engineer-acme-1092345",
    "location": "Worldwide", "description": "<p>Testing de <b>APIs</b></p>",
    "date": "2026-11-04T10:00:00+00:00", "tags": ["qa", "testing"],
}


# -------------------------------------------------- datos armados acá

def test_mapea_los_campos():
    job = remoteok.parse([LEGAL, JOB])[0]
    assert (job.source, job.source_id, job.title, job.company) == ("Remote OK", "1092345", "QA Engineer", "Acme")
    assert job.url == JOB["url"]
    assert job.location == "Worldwide"
    assert job.description == "Testing de APIs"          # sin HTML
    assert job.tags == ("qa", "testing")


def test_el_aviso_legal_no_es_una_oferta():
    assert remoteok.parse([LEGAL]) == []


@pytest.mark.parametrize(
    "broken",
    [
        {**JOB, "id": None},                               # id null
        {k: v for k, v in JOB.items() if k != "id"},       # sin id
        {**JOB, "position": ""},                           # sin título
        {**JOB, "url": None},                              # sin link
        "no soy un dict",
    ],
)
def test_ofertas_incompletas_se_saltean(broken):
    assert [j.source_id for j in remoteok.parse([LEGAL, broken, JOB])] == ["1092345"]


def test_campos_opcionales_null_no_rompen():
    job = remoteok.parse([{**JOB, "company": None, "location": None, "tags": None,
                           "description": None, "date": None}])[0]
    assert (job.company, job.location, job.tags, job.description, job.published_at) == ("", "", (), "", "")


@pytest.mark.parametrize("data", [{}, None, "texto", {"jobs": []}])
def test_respuesta_que_no_es_lista_devuelve_vacio(data):
    assert remoteok.parse(data) == []


# ------------------------------------------------------- fetch() y red

def test_fetch_usa_la_api_y_parsea():
    session = FakeSession(FakeResponse([LEGAL, JOB]))
    assert [j.source_id for j in remoteok.fetch(session=session)] == ["1092345"]


@pytest.mark.parametrize(
    "session",
    [FakeSession(error=requests.Timeout()), FakeSession(FakeResponse(status=503)),
     FakeSession(FakeResponse(payload=None))],
)
def test_errores_de_red_son_SourceError(session):
    with pytest.raises(SourceError):
        remoteok.fetch(session=session)


# ------------------------------------- contract check con el feed REAL

@pytest.fixture
def real_jobs():
    return remoteok.parse(json.loads(FIXTURE.read_text(encoding="utf-8")))


def test_contrato_el_feed_real_trae_ofertas(real_jobs):
    assert len(real_jobs) >= 3


def test_contrato_todos_los_links_son_de_remote_ok(real_jobs):
    assert all(j.url.lower().startswith("https://remoteok.com/") for j in real_jobs)


def test_contrato_todas_tienen_titulo_y_descripcion_sin_html(real_jobs):
    for job in real_jobs:
        assert job.title
        assert "<p>" not in job.description and "<br" not in job.description
