"""
Fuente: Jobicy (https://jobicy.com)

Términos de uso (verificados en su repo oficial):
- Mantener a Jobicy como fuente y conservar su URL original.
- No consultar más de una vez por hora; con algunas veces por día alcanza.
Este módulo hace 1 sola request por corrida (máximo 200 ofertas).

Contrato de toda fuente: NAME + fetch() -> list[Job]

EJERCICIO: completá los TODO hasta que `python -m pytest tests/test_jobicy.py -v`
dé todo en verde. Usá src/sources/remotive.py como guía.

Campos de cada oferta en la API de Jobicy:
  id (int), url, jobTitle, companyName, jobGeo (ubicación), jobLevel (texto),
  jobIndustry (lista), jobType (lista), jobDescription (HTML),
  jobExcerpt (resumen corto), pubDate (fecha ISO)
"""
import html

from src.models import Job
from src.sources.http import get_json
from src.text import html_to_text

NAME = "Jobicy"
API_URL = "https://jobicy.com/api/v2/remote-jobs"
PARAMS = {"count": 200}  # máximo permitido por la API


def _build_tags(item: dict) -> tuple[str, ...]:
    """
    Junta jobIndustry + jobType (listas) + jobLevel (texto),
    sin espacios sobrantes, sin vacíos y sin repetidos.
    """
    raw = [*(item.get("jobIndustry") or []), *(item.get("jobType") or []), item.get("jobLevel")]
    seen, result = set(), []
    for tag in raw:
        if not isinstance(tag, str):
            continue
        clean = tag.strip()
        if clean and clean.lower() not in seen:
            seen.add(clean.lower())
            result.append(clean)
    return tuple(result)


def parse(data: dict) -> list[Job]:
    """Convierte la respuesta JSON de Jobicy en una lista de Job."""
    jobs = []
    for item in data.get("jobs", []):
        try:
            jobs.append(
                Job(
                    source=NAME,
                    source_id=str(item["id"]),
                    title=html.unescape(item["jobTitle"].strip()),
                    company=html.unescape((item.get("companyName") or "").strip()),
                    url=item["url"],
                    location=(item.get("jobGeo") or "").strip(),
                    description=html_to_text(item.get("jobDescription") or item.get("jobExcerpt")),
                    published_at=item.get("pubDate") or "",
                    tags=_build_tags(item),
                )
            )
        except (KeyError, TypeError, AttributeError, ValueError):
            continue  # oferta incompleta: la salteamos
    return jobs


def fetch(session=None) -> list[Job]:
    """Trae hasta 200 ofertas remotas de Jobicy (1 request)."""
    return parse(get_json(API_URL, NAME, session=session, params=PARAMS))


if __name__ == "__main__":
    # Prueba manual: python -m src.sources.jobicy
    ofertas = fetch()
    print(f"[ok] {NAME}: {len(ofertas)} ofertas")
    for job in ofertas[:3]:
        print(f" - {job.title} | {job.company} | {job.location}")
