"""Tests de deduplicación e historial. Usan tmp_path: nunca tocan data/ real."""
import json
from datetime import date
from datetime import timedelta

import pytest

from src.models import Job
from src.store import (
    add_to_history,
    filter_new,
    fingerprint,
    keys_of,
    load_history,
    load_seen,
    mark_seen,
    prune_seen,
    save_json,
)

TODAY = date(2026, 10, 29)


def make_job(**overrides) -> Job:
    data = {
        "source": "Remotive",
        "source_id": "1",
        "title": "QA Engineer",
        "company": "Acme",
        "url": "https://example.com/1",
        "description": "Texto largo de la oferta",
    }
    data.update(overrides)
    return Job(**data)


# --------------------------------------------------------------- fingerprint

def test_fingerprint_ignora_mayusculas_tildes_y_espacios():
    a = make_job(title="QA  Engineer", company="Acmé")
    b = make_job(title="qa engineer", company="ACME", source="Jobicy", source_id="99")
    assert fingerprint(a) == fingerprint(b)


def test_fingerprint_distingue_empresas():
    assert fingerprint(make_job(company="Acme")) != fingerprint(make_job(company="Otra"))


def test_sin_empresa_no_hay_fingerprint():
    # "QA Engineer" sin empresa no alcanza para decir que dos ofertas son iguales
    assert fingerprint(make_job(company="")) is None
    assert keys_of(make_job(company="")) == [make_job(company="").uid]


# --------------------------------------------------------------- filter_new

def test_oferta_nueva_pasa():
    assert filter_new([make_job()], seen={}) == [make_job()]


def test_oferta_ya_enviada_no_pasa():
    seen = mark_seen([make_job()], {}, TODAY)
    assert filter_new([make_job()], seen) == []


def test_misma_oferta_en_dos_fuentes_pasa_una_sola_vez():
    remotive = make_job(source="Remotive", source_id="1")
    jobicy = make_job(source="Jobicy", source_id="777")
    assert filter_new([remotive, jobicy], seen={}) == [remotive]


def test_misma_oferta_ya_enviada_desde_otra_fuente_no_pasa():
    seen = mark_seen([make_job(source="Remotive", source_id="1")], {}, TODAY)
    assert filter_new([make_job(source="Jobicy", source_id="777")], seen) == []


def test_mismo_titulo_sin_empresa_en_dos_fuentes_pasan_las_dos():
    a = make_job(source="Remotive", source_id="1", company="")
    b = make_job(source="Jobicy", source_id="2", company="")
    assert filter_new([a, b], seen={}) == [a, b]


def test_conserva_el_orden():
    jobs = [make_job(source_id=str(i), company=f"C{i}") for i in range(5)]
    assert filter_new(jobs, seen={}) == jobs


# --------------------------------------------------------------- mark_seen

def test_mark_seen_guarda_solo_hashes_y_fecha():
    seen = mark_seen([make_job()], {}, TODAY)
    assert set(seen.values()) == {"2026-10-29"}
    texto = json.dumps(seen)
    assert "Acme" not in texto and "QA" not in texto  # nada legible


def test_mark_seen_no_modifica_el_original():
    original = {}
    mark_seen([make_job()], original, TODAY)
    assert original == {}


def test_mark_seen_conserva_la_primera_fecha():
    seen = mark_seen([make_job()], {}, date(2026, 10, 1))
    seen = mark_seen([make_job()], seen, TODAY)
    assert set(seen.values()) == {"2026-10-01"}


# --------------------------------------------------------------- history

def test_history_guarda_datos_publicos_sin_descripcion():
    history = add_to_history([], [make_job()], TODAY)
    row = history[0]
    assert row["title"] == "QA Engineer"
    assert row["url"] == "https://example.com/1"
    assert row["sent_at"] == "2026-10-29"
    assert row["uid"] == make_job().uid
    assert "description" not in row


def test_history_conserva_las_ultimas_n():
    jobs = [make_job(source_id=str(i)) for i in range(10)]
    history = add_to_history([], jobs, TODAY, max_items=3)
    assert [r["source_id"] for r in history] == ["7", "8", "9"]


# --------------------------------------------------------------- archivos

def test_archivo_inexistente_o_vacio_devuelve_vacio(tmp_path):
    assert load_seen(tmp_path / "no-existe.json") == {}
    (tmp_path / "vacio.json").write_text("", encoding="utf-8")
    assert load_history(tmp_path / "vacio.json") == []


def test_archivo_corrupto_frena_con_error_claro(tmp_path):
    roto = tmp_path / "seen.json"
    roto.write_text("{esto no es json", encoding="utf-8")
    with pytest.raises(RuntimeError, match="corrupto"):
        load_seen(roto)


def test_guardar_y_leer_ida_y_vuelta(tmp_path):
    path = tmp_path / "data" / "seen.json"   # la carpeta no existe todavía
    seen = mark_seen([make_job()], {}, TODAY)
    save_json(path, seen)
    assert load_seen(path) == seen
    assert not list(path.parent.glob("*.tmp"))  # no quedan temporales


# --------------------------------------------------------------- prune_seen

@pytest.mark.parametrize(
    "dias, se_conserva",
    [
        (10, True),
        (119, True),    # límite - 1
        (120, True),    # límite exacto
        (121, False),   # límite + 1
        (200, False),
    ],
)
def test_prune_seen_valores_limite(dias, se_conserva):
    seen = {make_job().uid: (TODAY - timedelta(days=dias)).isoformat()}
    pruned = prune_seen(seen, TODAY, max_age_days=120)
    assert (pruned == seen) is se_conserva


def test_seen_vacio_devuelve_vacio():
    assert prune_seen({}, TODAY, max_age_days=120) == {}