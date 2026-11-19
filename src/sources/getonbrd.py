"""
Fuente: Get on Board (https://www.getonbrd.com)

API pública oficial ("open to anyone", sin autenticación). Uso personal:
pocas búsquedas una vez por día, link original a su sitio y "vía Get on Board".

Contract check (30/10/2026) contra la API real:
- Formato JSON:API: data[].id + data[].attributes + data[].links.public_url
- La empresa y la ubicación vienen solo como ids salvo que se pidan con `expand`.
  Ojo: `expand` tiene que ir url-encodeado (requests lo hace solo).
- `countries` dice "Remote" aunque la oferta sea solo para algunos países:
  la ubicación real depende de `remote_modality`:
    fully_remote -> abierta a todo el mundo
    remote_local -> remota solo para los países de location_tenants
    hybrid       -> híbrida en las ciudades de location_cities
    no_remote    -> presencial
- published_at viene en segundos Unix.

Contrato de toda fuente: NAME + fetch() -> list[Job]

"""
import html
from datetime import datetime, timezone

from src.models import Job
from src.sources import SourceError
from src.sources.http import get_json
from src.text import html_to_text
from src.gaps import mark_desirable

NAME = "Get on Board"
SEARCH_URL = "https://www.getonbrd.com/api/v0/search/jobs"
QUERIES = ["qa", "tester", "analista funcional", "soporte", "customer support"]
PARAMS = {
    "per_page": 100,  # verificado: acepta 100
    "expand": '["company","location_tenants","location_cities"]',
}
# Partes del aviso que leen los filtros (benefits queda afuera: "clases de inglés"
# no es un requisito y confundiría al filtro de inglés)
DESCRIPTION_FIELDS = ("description", "functions", "desirable", "projects")


def _names(relation) -> list[str]:
    """Saca los nombres de una relación expandida: {"data": [{"attributes": {"name": ...}}]}."""
    data = (relation or {}).get("data") or []
    if isinstance(data, dict):          # company viene como objeto, no lista
        data = [data]
    names = []
    for item in data:
        if isinstance(item, dict):
            name = ((item.get("attributes") or {}).get("name") or "").strip()
            if name:
                names.append(name)
    return names


def _location(attrs: dict) -> str:
    """
    Arma la ubicación según remote_modality (NO según `countries`).
    Ante cualquier duda devuelve "" y el filtro de ubicación la descarta.
    """
    modality = attrs.get("remote_modality")
    tenants = _names(attrs.get("location_tenants"))   # ej. ["Mexico", "Colombia"]
    cities = _names(attrs.get("location_cities"))     # ej. ["Buenos Aires"]
    places = ", ".join(cities + tenants)
    if modality == "fully_remote":
        return "Worldwide"
    elif modality == "remote_local":
        return ", ".join(tenants)
    elif modality == "hybrid":
        return f"{places} (Híbrido)" if places else ""
    elif modality == "no_remote":
        return f"{places} (Presencial)" if places else ""
    else:
        return ""


def _description(attrs: dict) -> str:
    parts = []
    for field in DESCRIPTION_FIELDS:
        text = html_to_text(attrs.get(field))
        if field == "desirable":
            text = mark_desirable(text)   # cada oración queda marcada como "deseable: ..."
        parts.append(text)
    return "\n".join(p for p in parts if p)

        
    # return "\n".join(p for p in parts if p)


def _iso_date(ts) -> str:
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError):
        return ""


def parse(data: dict) -> list[Job]:
    jobs = []
    for item in data.get("data", []):
        try:
            attrs = item["attributes"]
            company = _names(attrs.get("company"))
            jobs.append(
                Job(
                    source=NAME,
                    source_id=str(item["id"]),
                    title=html.unescape(attrs["title"]).strip(),
                    company=company[0] if company else "",
                    url=item["links"]["public_url"],
                    location=_location(attrs),
                    description=_description(attrs),
                    published_at=_iso_date(attrs.get("published_at")),
                    tags=tuple(t for t in (attrs.get("category_name"), attrs.get("remote_modality")) if t),
                )
            )
        except (KeyError, TypeError, AttributeError, ValueError):
            continue
    return jobs


def fetch(session=None) -> list[Job]:
    jobs, errors = [], 0
    for query in QUERIES:
        try:
            data = get_json(SEARCH_URL, NAME, params={"query": query, **PARAMS}, session=session)
            jobs.extend(parse(data))
        except SourceError:
            errors += 1
    if errors == len(QUERIES):
        raise SourceError(f"{NAME}: todas las búsquedas fallaron")
    return jobs


if __name__ == "__main__":
    ofertas = fetch()
    print(f"[ok] {NAME}: {len(ofertas)} ofertas")
    for job in ofertas[:5]:
        print(f" - {job.title} | {job.company} | {job.location}")
