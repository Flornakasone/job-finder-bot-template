"""
Fuente: Himalayas (https://himalayas.app)

Términos de la API (himalayas.app/terms#api, verificados):
- Usar el `applicationLink` de la API como link para postularse.
- Mostrar el crédito "vía Himalayas" de forma visible.
- No reenviar las ofertas a otros job boards, agregadores, Google Jobs ni LinkedIn Jobs.
Sin API key hay un cupo compartido con todos los usuarios anónimos:
hacemos pocas búsquedas (una por término de QUERIES) una vez por día.

Contrato de toda fuente: NAME + fetch() -> list[Job]

EJERCICIO: completá los 3 TODO hasta que
`python -m pytest tests/test_himalayas.py -v` quede en verde.
"""
import html
from datetime import datetime, timezone

from src.models import Job
from src.sources import SourceError
from src.sources.http import get_json
from src.text import html_to_text

NAME = "Himalayas"
SEARCH_URL = "https://himalayas.app/jobs/api/search"
# Pocas búsquedas amplias; el filtro de rubro hace el resto
QUERIES = ["QA", "quality assurance", "tester", "customer support", "data annotation"]


def _location(item: dict) -> str:
    """locationRestrictions vacío = abierto a todo el mundo.
    La API real manda textos ("Brazil"); la doc dice objetos ({"name": "Brazil"}): aceptamos ambos."""
    names = []
    for place in item.get("locationRestrictions") or []:
        if isinstance(place, str):
            names.append(place.strip())
        elif isinstance(place, dict):
            names.append((place.get("name") or "").strip())
    names = [n for n in names if n]
    return ", ".join(names) if names else "Worldwide"


def _iso_date(ts) -> str:
    """pubDate viene en segundos Unix; lo pasamos a ISO como las otras fuentes."""
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError):
        return ""   


def _build_tags(item: dict) -> tuple[str, ...]:
    seniority = item.get("seniority") or []
    if isinstance(seniority, str):        # la doc es inconsistente: lista o texto
        seniority = [seniority]
    raw = [*(item.get("categories") or []), *seniority, item.get("employmentType")]
    seen, result = set(), []
    for tag in raw:
        if isinstance(tag, str) and tag.strip() and tag.strip().lower() not in seen:
            seen.add(tag.strip().lower())
            result.append(tag.strip())
    return tuple(result)


def parse(data: dict) -> list[Job]:
    jobs = []
    for item in data.get("jobs", []):
        try:
            jobs.append(
                Job(
                    source=NAME,
                    source_id=str(item["guid"]),
                    title=html.unescape(item["title"]).strip(),
                    company=html.unescape(item.get("companyName") or "").strip(),
                    url=item["applicationLink"],          # lo exigen sus términos
                    location=_location(item),
                    description=html_to_text(item.get("description")) or (item.get("excerpt") or ""),
                    published_at=_iso_date(item.get("pubDate")),
                    tags=_build_tags(item),
                )
            )
        except (KeyError, TypeError, AttributeError, ValueError):
            continue
    return jobs


def fetch(session=None) -> list[Job]:
    """Una búsqueda por término. Si TODAS fallan, SourceError; si falla alguna, sigue."""
    jobs, errors = [], 0
    for query in QUERIES:
        try:
            data = get_json(SEARCH_URL, NAME, params={"q": query, "country": "AR", "sort": "recent"}, session=session)            
            jobs.extend(parse(data))
        except SourceError:
            errors += 1
    if errors == len(QUERIES):
        raise SourceError(f"{NAME}: todas las búsquedas fallaron")
    return jobs


if __name__ == "__main__":
    ofertas = fetch()
    print(f"[ok] {NAME}: {len(ofertas)} ofertas")
    for job in ofertas[:3]:
        print(f" - {job.title} | {job.company} | {job.location}")
