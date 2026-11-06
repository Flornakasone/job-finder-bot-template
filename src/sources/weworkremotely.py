"""
Fuente: We Work Remotely (https://weworkremotely.com)

Términos (https://weworkremotely.com/remote-job-rss-feed, verificado 2026-11-05):
"Anyone can use the feed"; la condición es que los links acrediten a We Work
Remotely como fuente. El mensaje ya lo hace: link original + "(vía We Work Remotely)".

Se usa el feed general (todas las categorías): 1 sola request por corrida.
Formato del título: "Empresa: Puesto".

Contrato de toda fuente: NAME + fetch() -> list[Job]
"""
from email.utils import parsedate_to_datetime

from src.models import Job
from src.sources import rss
from src.text import html_to_text

NAME = "We Work Remotely"
FEED_URL = "https://weworkremotely.com/remote-jobs.rss"


def _split_title(raw: str) -> tuple[str, str]:
    """'Acme: QA Engineer' -> ('Acme', 'QA Engineer'). Sin ':' -> ('', título)."""
    company, sep, title = raw.partition(":")
    return (company.strip(), title.strip()) if sep and title.strip() else ("", raw.strip())


def _iso_date(rfc822: str) -> str:
    """'Wed, 05 Nov 2026 10:00:00 +0000' -> '2026-11-05T10:00:00+00:00'. Inválida: ''."""
    try:
        return parsedate_to_datetime(rfc822).isoformat()
    except (TypeError, ValueError, IndexError):
        return ""


def parse(root) -> list:
    jobs = []
    for item in rss.items(root):
        company, title = _split_title(rss.child_text(item, "title"))
        link = rss.child_text(item, "link")
        guid = rss.child_text(item, "guid") or link
        try:
            jobs.append(Job(
                source=NAME,
                source_id=guid,
                title=title,
                company=company,
                url=link,
                location=rss.child_text(item, "region"),
                description=html_to_text(rss.child_text(item, "description")),
                published_at=_iso_date(rss.child_text(item, "pubDate")),
                tags=tuple(t for t in (rss.child_text(item, "category"), rss.child_text(item, "type")) if t),
            ))
        except ValueError:
            continue
    return jobs


def fetch(session=None) -> list:
    return parse(rss.get_xml(FEED_URL, NAME, session=session))
