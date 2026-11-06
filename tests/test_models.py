import dataclasses

import pytest

from src.models import Job


def make_job(**overrides) -> Job:
    """Crea una oferta válida; cada test cambia solo lo que necesita."""
    data = {
        "source": "Remotive",
        "source_id": "123",
        "title": "QA Engineer",
        "company": "Acme",
        "url": "https://remotive.com/remote-jobs/qa/qa-engineer-123",
    }
    data.update(overrides)
    return Job(**data)


def test_uid_es_estable():
    # La misma oferta en dos corridas distintas tiene el mismo uid
    assert make_job().uid == make_job().uid


def test_uid_cambia_si_cambia_el_id():
    assert make_job(source_id="123").uid != make_job(source_id="456").uid


def test_uid_distingue_fuentes():
    # El id 123 de Remotive no es la misma oferta que el id 123 de Jobicy
    assert make_job(source="Remotive").uid != make_job(source="Jobicy").uid


def test_uid_no_depende_de_mayusculas_en_la_fuente():
    assert make_job(source="Remotive").uid == make_job(source="remotive").uid


def test_uid_tiene_16_caracteres_hex():
    uid = make_job().uid
    assert len(uid) == 16
    int(uid, 16)  # falla si no es hexadecimal


@pytest.mark.parametrize("campo", ["source", "source_id", "title", "url"])
def test_falla_sin_campos_obligatorios(campo):
    with pytest.raises(ValueError, match=campo):
        make_job(**{campo: "  "})


def test_job_es_inmutable():
    job = make_job()
    with pytest.raises(dataclasses.FrozenInstanceError):
        job.title = "Otro"
