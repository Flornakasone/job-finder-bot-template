from src.language import english_label

"""
Arma el texto del resumen diario para Telegram.

Por ahora (Etapa 3) cada oferta muestra título, empresa, ubicación y link.
El % de match, el inglés y la línea "Aporto" se suman en la Etapa 4.
Texto plano, sin Markdown: así ningún título raro rompe el formato.
"""
from datetime import date

from src.filters import normalize
from src.models import Job

MAX_LEN = 4000  # Telegram corta en 4096; dejamos margen


def location_label(location: str) -> str:
    """Traduce la ubicación cruda a algo legible y corto."""
    loc = normalize(location)
    if any(w in loc for w in ("worldwide", "anywhere", "global", "todo el mundo")):
        return "Remoto global"
    if any(w in loc for w in ("latam", "latin america", "america latina", "latinoamerica", "south america")):
        return "Remoto LATAM"
    places = [p.strip() for p in location.split(",") if p.strip()]
    if len(places) > 3:
        # Mostrar Argentina primero si está; si no, el primero de la lista
        main = next((p for p in places if normalize(p) == "argentina"), places[0])
        return f"{main} + {len(places) - 1} países"
    return location or "Sin ubicación"

def score_badge(score: int | None) -> str:
    """🟢 70+ · 🟡 50-69 · 🟠 menos de 50 · 🔹 sin scoring."""
    if score is None:
        return "🔹"
    emoji = "🟢" if score >= 70 else "🟡" if score >= 50 else "🟠"
    return f"{emoji} {score}% |"

def format_job(job: Job, score: int | None = None, evaluation=None) -> str:
    company = f" – {job.company}" if job.company else ""
    lines = [
        f"{score_badge(score)} {job.title}{company}",
        f"📍 {location_label(job.location)}",
        f"🗣 Inglés: {english_label(job.description)}",
    ]
    if evaluation:   # evaluación con IA (#16): solo si Groq respondió para esta oferta
        lines += [
            f"🧭 {evaluation.label}",
            f"✅ Cumplo: {evaluation.aporto}",
            f"⚠️ Falta: {evaluation.falta}",
        ]
    # "vía X" + link original: lo exigen los términos de las fuentes
    lines.append(f"🔗 {job.url} (vía {job.source})")
    return "\n".join(lines)


def build_messages(jobs: list[Job], today: date, total_checked: int,
                   scores: dict[str, int] | None = None,
                   evaluations: dict | None = None) -> list[str]:
    fecha = today.strftime("%d/%m")
    if not jobs:
        return [f"🗂 {fecha} · Hoy no hay ofertas nuevas que pasen tus filtros.\n"
                f"Revisé {total_checked} ofertas."]

    header = f"🗂 {fecha} · {len(jobs)} ofertas nuevas (de {total_checked} revisadas)"
    scores, evaluations = scores or {}, evaluations or {}
    blocks = [format_job(j, scores.get(j.uid), evaluations.get(j.uid)) for j in jobs]
    messages, current = [], header
    for block in blocks:
        candidate = f"{current}\n\n{block}"
        if len(candidate) > MAX_LEN:
            messages.append(current)
            current = block
        else:
            current = candidate
    messages.append(current)
    return messages
    