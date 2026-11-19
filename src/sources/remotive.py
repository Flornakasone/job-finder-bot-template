"""
Fuente: Remotive (https://remotive.com)

Términos de uso (verificados en su repo oficial):
- Linkear a la URL de Remotive y mencionarla como fuente.
- Máximo recomendado: 4 requests por día. Más de 2 por minuto -> bloqueo.
- Las ofertas llegan con 24 h de demora.
Este módulo hace 1 sola request por corrida.

Contrato de toda fuente: NAME + fetch() -> list[Job]
"""
from src.models import Job
from src.sources.http import get_json
from src.text import html_to_text

NAME = "Remotive"
API_URL = "https://remotive.com/api/remote-jobs"


def _build_tags(item: dict) -> tuple[str, ...]:
    """
    Junta category, job_type y la lista `tags` (campo que la API real trae
    aunque no está en la documentación). Limpia espacios y saca repetidos.
    """
    raw = [item.get("category"), item.get("job_type"), *(item.get("tags") or [])]
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
    """
    Convierte la respuesta JSON de Remotive en una lista de Job.
    Separado de fetch() para poder testearlo sin internet.
    Las ofertas mal formadas se saltean en vez de romper todo.
    """
    jobs = []
    for item in data.get("jobs", []):
        try:
            jobs.append(
                Job(
                    source=NAME,
                    source_id=str(item["id"]),
                    title=item["title"].strip(),
                    company=(item.get("company_name") or "").strip(),
                    url=item["url"],
                    location=(item.get("candidate_required_location") or "").strip(),
                    description=html_to_text(item.get("description")),
                    published_at=item.get("publication_date") or "",
                    tags=_build_tags(item),
                )
            )
        except (KeyError, TypeError, AttributeError, ValueError):
            continue  # oferta incompleta: la salteamos
    return jobs


def fetch(session=None) -> list[Job]:
    """Trae todas las ofertas activas de Remotive (1 request)."""
    return parse(get_json(API_URL, NAME, session=session))


if __name__ == "__main__":
    # Prueba manual: python -m src.sources.remotive
    ofertas = fetch()
    print(f"[ok] {NAME}: {len(ofertas)} ofertas")
    for job in ofertas[:3]:
        print(f" - {job.title} | {job.company} | {job.location}")
