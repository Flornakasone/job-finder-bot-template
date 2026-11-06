"""
Deduplicación y memoria del bot.

Dos archivos en data/ (se commitean en el repo privado):

- seen.json     -> qué ofertas ya te mandé. Solo hashes + fecha, nada legible.
                   {"<hash>": "2026-10-29", ...}
- history.json  -> las ofertas enviadas, con sus datos públicos (título,
                   empresa, link...). Lo usan después Notion y el dashboard.
                   No contiene ningún dato tuyo.

Regla clave: una oferta se marca como vista SOLO después de enviarla bien
por Telegram (eso lo hace la tarea 6). Si el envío falla, en la próxima
corrida se vuelve a intentar.
"""
import json
import os
import tempfile
from dataclasses import asdict
from datetime import date, timedelta
from hashlib import sha256
from pathlib import Path

from src.filters import normalize
from src.models import Job

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SEEN_FILE = DATA_DIR / "seen.json"
HISTORY_FILE = DATA_DIR / "history.json"
LAST_RUN_FILE = DATA_DIR / "last_run.json"

SEEN_MAX_AGE_DAYS = 120   # después de esto un hash se olvida (el archivo no crece infinito)
HISTORY_MAX_ITEMS = 500   # últimas N ofertas enviadas


# ------------------------------------------------------------------ claves

def fingerprint(job: Job) -> str | None:
    """
    Huella de "la misma oferta publicada en dos lados":
    hash de empresa + título normalizados.
    Si no hay empresa devuelve None: "QA Engineer" a secas no alcanza
    para decir que dos ofertas son la misma.
    """
    company = normalize(job.company).strip()
    title = " ".join(normalize(job.title).split())
    if not company:
        return None
    return sha256(f"{company}|{title}".encode("utf-8")).hexdigest()[:16]


def keys_of(job: Job) -> list[str]:
    """Todas las claves con las que se reconoce una oferta ya vista."""
    fp = fingerprint(job)
    return [job.uid] + ([fp] if fp else [])


# --------------------------------------------------------------- lectura

def _read_json(path: Path, default):
    """Archivo inexistente o vacío -> default. JSON roto -> error claro."""
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # Mejor frenar que mandarte 200 ofertas repetidas
        raise RuntimeError(f"{path.name} está corrupto; revisalo antes de seguir") from None


def load_seen(path: Path = SEEN_FILE) -> dict[str, str]:
    return _read_json(path, {})


def load_history(path: Path = HISTORY_FILE) -> list[dict]:
    return _read_json(path, [])


# ---------------------------------------------------------------- lógica

def filter_new(jobs: list[Job], seen: dict[str, str]) -> list[Job]:
    """
    Devuelve solo las ofertas que no se mandaron nunca, sin repetidos
    dentro de la misma corrida (ej. la misma oferta en dos fuentes).
    Conserva el orden original.
    """
    result, batch_keys = [], set()
    for job in jobs:
        keys = keys_of(job)
        if any(k in seen or k in batch_keys for k in keys):
            continue
        batch_keys.update(keys)
        result.append(job)
    return result


def mark_seen(jobs: list[Job], seen: dict[str, str], today: date) -> dict[str, str]:
    """Devuelve un seen NUEVO con las ofertas agregadas (no modifica el original)."""
    updated = dict(seen)
    for job in jobs:
        for key in keys_of(job):
            updated.setdefault(key, today.isoformat())
    return updated


def prune_seen(seen: dict[str, str], today: date, max_age_days: int = SEEN_MAX_AGE_DAYS) -> dict[str, str]:
    """Olvida los hashes más viejos que max_age_days."""
    limit = (today - timedelta(days=max_age_days)).isoformat()
    return {k: d for k, d in seen.items() if d >= limit}


def add_to_history(history: list[dict], jobs: list[Job], today: date,
                   max_items: int = HISTORY_MAX_ITEMS) -> list[dict]:
    """Agrega las ofertas enviadas (datos públicos) y conserva las últimas max_items."""
    new_rows = []
    for job in jobs:
        row = asdict(job)
        row.pop("description")      # no hace falta guardar el texto entero
        row["tags"] = list(job.tags)
        row["uid"] = job.uid
        row["sent_at"] = today.isoformat()
        new_rows.append(row)
    return (history + new_rows)[-max_items:]


# --------------------------------------------------------------- escritura

def save_json(path: Path, data) -> None:
    """
    Escritura atómica: escribe en un archivo temporal y lo reemplaza.
    Si el proceso se corta a la mitad, el archivo viejo queda intacto.
    sort_keys + indent -> diffs de git prolijos.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


# ------------------------------------------------------- idempotencia diaria

def already_sent_today(today: date, path: Path = LAST_RUN_FILE) -> bool:
    """True si el resumen de `today` ya se mandó (lo usa la 2.ª y 3.ª corrida del día)."""
    return _read_json(path, {}).get("last_sent") == today.isoformat()


def mark_sent_today(today: date, path: Path = LAST_RUN_FILE) -> None:
    """Se llama SOLO después de un envío exitoso."""
    save_json(path, {"last_sent": today.isoformat()})
