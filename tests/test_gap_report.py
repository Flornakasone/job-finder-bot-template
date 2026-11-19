"""Tests del reporte semanal de gaps."""
from collections import Counter
from datetime import date

import pytest

from src import gap_report
from src.models import Job

THU = date(2026, 11, 5)       # jueves
MON = date(2026, 11, 9)       # lunes
TECH = ["playwright", "cypress", "typescript"]
SKILLS = ["sql"]


def make_job(i, description="") -> Job:
    return Job(source="Test", source_id=str(i), title=f"QA {i}", company="Acme",
               url=f"https://example.com/{i}", description=description)


def test_record_anota_los_gaps_de_cada_oferta():
    job = make_job(1, "Requisito: Playwright y TypeScript.")
    stats = gap_report.record({}, [job], THU, TECH, SKILLS)
    assert stats == {job.uid: {"date": "2026-11-05", "gaps": ["playwright", "typescript"]}}


def test_una_oferta_cuenta_una_sola_vez_aunque_vuelva_otro_dia():
    job = make_job(1, "Playwright.")
    stats = gap_report.record({}, [job], THU, TECH, SKILLS)
    stats = gap_report.record(stats, [job], MON, TECH, SKILLS)
    assert stats[job.uid]["date"] == "2026-11-05"        # se queda con el primer día
    assert len(stats) == 1


def test_record_no_modifica_el_original():
    original = {}
    gap_report.record(original, [make_job(1, "Cypress.")], THU, TECH, SKILLS)
    assert original == {}


def test_prune_borra_lo_viejo():
    stats = {"viejo": {"date": "2026-09-01", "gaps": []}, "nuevo": {"date": "2026-11-01", "gaps": []}}
    assert set(gap_report.prune(stats, THU, keep_days=60)) == {"nuevo"}


def test_summarize_cuenta_solo_los_ultimos_7_dias():
    stats = {
        "a": {"date": "2026-11-09", "gaps": ["playwright", "cypress"]},
        "b": {"date": "2026-11-03", "gaps": ["playwright"]},          # 7 días contando hoy: entra
        "c": {"date": "2026-11-02", "gaps": ["typescript"]},         # 8 días atrás: no entra
    }
    n, gaps = gap_report.summarize(stats, MON)
    assert n == 2
    assert gaps == Counter({"playwright": 2, "cypress": 1})


def test_build_report_ranking_y_sugerencia():
    text = gap_report.build_report(12, Counter({"playwright": 7, "cypress": 3, "typescript": 1}), MON)
    assert text.startswith("📊 Semana 03/11–09/11 · gaps en 12 avisos relevantes")
    assert "1. playwright — 7 avisos" in text
    assert "3. typescript — 1 aviso" in text                          # singular
    assert "Si sumás playwright a tus skills, 7 avisos dejan de restarte puntos." in text


def test_build_report_respeta_el_top():
    gaps = Counter({f"t{i}": 10 - i for i in range(8)})
    assert "6." not in gap_report.build_report(20, gaps, MON, top=5)


def test_build_report_sin_gaps_lo_celebra():
    assert "🎉" in gap_report.build_report(5, Counter(), MON)


def test_build_report_sin_avisos_no_manda_nada():
    assert gap_report.build_report(0, Counter(), MON) is None


@pytest.mark.parametrize(
    "day, today, expected",
    [("lunes", MON, True), ("Monday", MON, True), ("lunes", THU, False),
     ("jueves", THU, True), ("", MON, False), ("feriado", MON, False)],
)
def test_is_report_day(day, today, expected):
    assert gap_report.is_report_day(today, day) is expected
