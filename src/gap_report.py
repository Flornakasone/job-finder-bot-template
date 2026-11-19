"""
Reporte semanal de gaps: qué tecnologías piden los avisos relevantes y vos no tenés.

Todos los días se anotan los gaps de las ofertas que pasaron los filtros
(no solo las enviadas): es la foto del mercado que te interesa.
Una vez por semana se manda el ranking a Telegram.

data/gap_stats.json guarda, por oferta (uid = hash, sin datos tuyos):
    {"<uid>": {"date": "2026-11-05", "gaps": ["playwright", "typescript"]}}
Cada oferta cuenta UNA vez aunque aparezca varios días. Se borra lo de más de 60 días.
"""
from collections import Counter
from datetime import date, timedelta

from src import store
from src.gaps import find_gaps
from src.models import Job

STATS_FILE = store.DATA_DIR / "gap_stats.json"
KEEP_DAYS = 60
TOP = 5

WEEKDAYS = {
    "monday": 0, "lunes": 0, "tuesday": 1, "martes": 1, "wednesday": 2, "miercoles": 2,
    "miércoles": 2, "thursday": 3, "jueves": 3, "friday": 4, "viernes": 4,
    "saturday": 5, "sabado": 5, "sábado": 5, "sunday": 6, "domingo": 6,
}


def load_stats(path=STATS_FILE) -> dict:
    return store._read_json(path, {})


def record(stats: dict, jobs: list[Job], today: date, tech: list[str], skills: list[str]) -> dict:
    """Devuelve stats NUEVO con las ofertas de hoy que no estaban (no modifica el original)."""
    updated = dict(stats)
    for job in jobs:
        if job.uid not in updated:
            updated[job.uid] = {"date": today.isoformat(),
                                "gaps": find_gaps(job.description, tech, skills)}
    return updated


def prune(stats: dict, today: date, keep_days: int = KEEP_DAYS) -> dict:
    limit = (today - timedelta(days=keep_days)).isoformat()
    return {uid: e for uid, e in stats.items() if e.get("date", "") >= limit}


def summarize(stats: dict, today: date, days: int = 7) -> tuple[int, Counter]:
    """(cantidad de ofertas de los últimos `days` días, Counter de gaps)."""
    since = (today - timedelta(days=days - 1)).isoformat()
    recent = [e for e in stats.values() if since <= e.get("date", "") <= today.isoformat()]
    return len(recent), Counter(g for e in recent for g in e.get("gaps", []))


def build_report(n_jobs: int, gaps: Counter, today: date, top: int = TOP) -> str | None:
    if not n_jobs:
        return None
    since = (today - timedelta(days=6)).strftime("%d/%m")
    lines = [f"📊 Semana {since}–{today.strftime('%d/%m')} · gaps en {n_jobs} avisos relevantes"]
    if not gaps:
        lines.append("Ningún aviso pidió como obligatorio algo que no tengas. 🎉")
        return "\n".join(lines)
    for i, (tech, count) in enumerate(gaps.most_common(top), start=1):
        lines.append(f"{i}. {tech} — {count} {'aviso' if count == 1 else 'avisos'}")
    first, count = gaps.most_common(1)[0]
    lines.append(f"\n💡 Si sumás {first} a tus skills, {count} avisos dejan de restarte puntos.")
    return "\n".join(lines)


def is_report_day(today: date, weekday: str) -> bool:
    """weekday: 'monday', 'lunes'… Vacío o desconocido = nunca."""
    return WEEKDAYS.get((weekday or "").strip().lower()) == today.weekday()
