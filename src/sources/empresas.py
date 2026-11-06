"""
Fuente: portales de empleo de empresas y consultoras (ATS).

Lee config/empresas.txt, una empresa por línea:

    Nombre | ats | dirección

    ats         dirección                         endpoint público que se lee
    greenhouse  slug (boards.greenhouse.io/SLUG)  boards-api.greenhouse.io/v1/boards/SLUG/jobs
    lever       slug (jobs.lever.co/SLUG)         api.lever.co/v0/postings/SLUG
    ashby       slug (jobs.ashbyhq.com/SLUG)      api.ashbyhq.com/posting-api/job-board/SLUG
    teamtailor  URL del sitio de empleos          URL/jobs.rss

Son las APIs/feeds PÚBLICOS que cada ATS ofrece para mostrar ofertas en otros sitios:
no piden login ni credenciales. Teamtailor: "all of the data is publicly available"
(support.teamtailor.com, guía del RSS). 1 request por empresa por corrida.

Una empresa que falla no frena a las demás. Si fallan TODAS, SourceError.
Contrato de toda fuente: NAME + fetch() -> list[Job]
"""
import html
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from src.models import Job
from src.paths import find_config
from src.sources import SourceError, rss
from src.sources.http import get_json
from src.text import html_to_text

NAME = "Portales de empresas"
SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]{0,80}$", re.IGNORECASE)   # nada de "/", "?", ".."


@dataclass(frozen=True)
class Company:
    name: str
    ats: str
    address: str


# --------------------------------------------------------------- config

def parse_company_line(line: str) -> Company:
    """'CDA | teamtailor | https://cda.teamtailor.com' -> Company. Inválida: ValueError."""
    parts = [p.strip() for p in line.split("|")]
    if len(parts) != 3 or not all(parts):
        raise ValueError("formato: Nombre | ats | dirección")
    name, ats, address = parts[0], parts[1].lower(), parts[2]
    if ats not in READERS:
        raise ValueError(f"ats desconocido: {ats} (opciones: {', '.join(READERS)})")
    if ats == "teamtailor":
        if not re.match(r"^https://[a-z0-9.-]+(/[a-z0-9._/-]*)?$", address, re.IGNORECASE):
            raise ValueError("teamtailor: la dirección tiene que ser una URL https")
    elif not SLUG.match(address):
        raise ValueError(f"{ats}: la dirección tiene que ser el slug, sin / ni ?")
    return Company(name, ats, address.rstrip("/"))


def load_companies(path: Path | None = None) -> tuple[list[Company], list[str]]:
    """Devuelve (empresas válidas, errores por línea). Sin archivo: ([], [])."""
    if path is None:
        try:
            path = find_config("empresas.txt")
        except FileNotFoundError:
            return [], []
    if not path.exists():
        return [], []
    companies, errors = [], []
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            companies.append(parse_company_line(line))
        except ValueError as err:
            errors.append(f"empresas.txt línea {n}: {err}")
    return companies, errors


# --------------------------------------------------------------- helpers

def _with_modality(place: str, modality: str) -> str:
    """Normaliza la modalidad al formato que entienden los filtros de ubicación."""
    m = (modality or "").lower().replace("-", "").replace("_", "")
    if m in ("remote", "fully"):
        return f"{place} (Remote)" if place else "Remote"
    if m == "hybrid":
        return f"{place} (Híbrido)" if place else ""
    if m in ("onsite", "none"):
        return f"{place} (Presencial)" if place else ""
    return place


def _ms_to_iso(ms) -> str:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        return ""


def _jobs(build, items, company: Company) -> list[Job]:
    """Aplica `build` a cada ítem y saltea los incompletos sin romper."""
    out = []
    for item in items or []:
        try:
            out.append(build(item, company))
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
    return out


# ------------------------------------------------------------ greenhouse

def _greenhouse_job(item: dict, company: Company) -> Job:
    return Job(
        source="Greenhouse", source_id=str(item["id"]), title=item.get("title") or "",
        company=company.name, url=item.get("absolute_url") or "",
        location=(item.get("location") or {}).get("name") or "",
        # Greenhouse manda el HTML "escapado" (&lt;p&gt;): primero se des-escapa
        description=html_to_text(html.unescape(item.get("content") or "")),
        published_at=item.get("first_published") or item.get("updated_at") or "",
    )


def parse_greenhouse(data: dict, company: Company) -> list[Job]:
    return _jobs(_greenhouse_job, (data or {}).get("jobs"), company)


def fetch_greenhouse(company: Company, session=None) -> list[Job]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{company.address}/jobs"
    return parse_greenhouse(get_json(url, f"Greenhouse {company.name}", {"content": "true"}, session), company)


# ----------------------------------------------------------------- lever

def _lever_job(item: dict, company: Company) -> Job:
    sections = [item.get("descriptionPlain") or ""]
    for block in item.get("lists") or []:            # requisitos, responsabilidades…
        sections.append(f"{block.get('text', '')}\n{html_to_text(block.get('content'))}")
    sections.append(item.get("additionalPlain") or "")
    place = (item.get("categories") or {}).get("location") or ""
    return Job(
        source="Lever", source_id=str(item["id"]), title=item.get("text") or "",
        company=company.name, url=item.get("hostedUrl") or "",
        location=_with_modality(place, item.get("workplaceType")),
        description="\n".join(s.strip() for s in sections if s and s.strip()),
        published_at=_ms_to_iso(item.get("createdAt")),
    )


def parse_lever(data: list, company: Company) -> list[Job]:
    return _jobs(_lever_job, data if isinstance(data, list) else [], company)


def fetch_lever(company: Company, session=None) -> list[Job]:
    url = f"https://api.lever.co/v0/postings/{company.address}"
    return parse_lever(get_json(url, f"Lever {company.name}", {"mode": "json"}, session), company)


# ----------------------------------------------------------------- ashby

def _ashby_job(item: dict, company: Company) -> Job:
    if item.get("isListed") is False:
        raise ValueError("oferta no publicada")
    places = [item.get("location") or ""] + [
        (s or {}).get("location") or "" for s in item.get("secondaryLocations") or []]
    place = ", ".join(p for p in places if p)
    modality = item.get("workplaceType") or ("remote" if item.get("isRemote") else "")
    return Job(
        source="Ashby", source_id=str(item["id"]), title=item.get("title") or "",
        company=company.name, url=item.get("jobUrl") or "",
        location=_with_modality(place, modality),
        description=item.get("descriptionPlain") or html_to_text(item.get("descriptionHtml")),
        published_at=item.get("publishedAt") or "",
    )


def parse_ashby(data: dict, company: Company) -> list[Job]:
    return _jobs(_ashby_job, (data or {}).get("jobs"), company)


def fetch_ashby(company: Company, session=None) -> list[Job]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{company.address}"
    return parse_ashby(get_json(url, f"Ashby {company.name}", None, session), company)


# ------------------------------------------------------------ teamtailor

def _teamtailor_locations(item) -> str:
    """
    Ciudad y país de cada <tt:location>, sin repetir. Si no hay, el nombre de la sede.
    (La dirección y el código postal no se usan: no aportan al filtro.)
    """
    places, names = [], []
    for el in item.iter():
        tag, text = rss.local(el.tag), (el.text or "").strip()
        if not text:
            continue
        if tag in ("city", "country") and text not in places:
            places.append(text)
        elif tag == "name" and text not in names:
            names.append(text)
    return ", ".join(places or names)


def _teamtailor_job(item, company: Company) -> Job:
    link = rss.child_text(item, "link")
    try:
        published = parsedate_to_datetime(rss.child_text(item, "pubDate")).isoformat()
    except (TypeError, ValueError, IndexError):
        published = ""
    return Job(
        source="Teamtailor", source_id=rss.child_text(item, "guid") or link,
        title=rss.child_text(item, "title"), company=company.name, url=link,
        location=_with_modality(_teamtailor_locations(item), rss.child_text(item, "remoteStatus")),
        description=html_to_text(rss.child_text(item, "description")),
        published_at=published,
    )


def parse_teamtailor(root, company: Company) -> list[Job]:
    return _jobs(_teamtailor_job, rss.items(root), company)


def fetch_teamtailor(company: Company, session=None) -> list[Job]:
    root = rss.get_xml(f"{company.address}/jobs.rss", f"Teamtailor {company.name}", session)
    return parse_teamtailor(root, company)


# ------------------------------------------------------------------ fetch

READERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
    "teamtailor": fetch_teamtailor,
}


def fetch(session=None, companies: list[Company] | None = None) -> list[Job]:
    if companies is None:
        companies, errors = load_companies()
        for err in errors:
            print(f"[aviso] {err}")      # solo la línea mal escrita: no tiene datos tuyos
    jobs, failed = [], 0
    for company in companies:
        try:
            jobs += READERS[company.ats](company, session=session)
        except SourceError:
            failed += 1                    # una empresa caída no frena a las demás
    if companies and failed == len(companies):
        raise SourceError(f"{NAME}: no respondió ninguna de {failed} empresas")
    return jobs
