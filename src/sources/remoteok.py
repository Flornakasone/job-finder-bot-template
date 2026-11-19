"""
Fuente: Remote OK (https://remoteok.com)

Términos de uso (aviso "legal" que viene como primer elemento del feed):
- Linkear a la URL de la oferta en Remote OK (link normal, sin nofollow).
- Mencionar a Remote OK como fuente. El nombre se puede usar; el logo no.
- Si no se atribuye, pueden suspender el acceso a la API.
El mensaje de Telegram ya cumple: link original + "(vía Remote OK)".

El feed trae solo las 100 ofertas más nuevas, sin búsqueda ni paginación:
1 sola request por corrida.

Contrato de toda fuente: NAME + fetch() -> list[Job]
"""
from src.models import Job
from src.sources.http import get_json
from src.text import html_to_text

NAME = "Remote OK"
API_URL = "https://remoteok.com/api"


def parse(data) -> list[Job]:
    """
    Convierte el feed en una lista de Job.
    El primer elemento no es una oferta: es el aviso legal (tiene la clave "legal").
    Ofertas incompletas (sin id, título o link) se saltean sin romper.
    """
    if not isinstance(data, list):
        return []
    jobs = []
    for item in data:
        if not isinstance(item, dict) or "legal" in item:
            continue
        if item.get("id") in (None, ""):
            continue                       # sin id no se puede deduplicar
        try:
            jobs.append(Job(
                source=NAME,
                source_id=str(item["id"]),
                title=(item.get("position") or "").strip(),
                company=(item.get("company") or "").strip(),
                url=item.get("url") or "",            # link en Remote OK: lo piden sus términos
                location=(item.get("location") or "").strip(),
                description=html_to_text(item.get("description")),
                published_at=item.get("date") or "",
                tags=tuple(t for t in (item.get("tags") or []) if isinstance(t, str)),
            ))
        except (KeyError, ValueError):
            continue
    return jobs


def fetch(session=None) -> list[Job]:
    return parse(get_json(API_URL, NAME, session=session))
