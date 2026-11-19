"""
% de match entre cada oferta y tu perfil (secret PROFILE_TEXT).

    match = 50% semántico + 30% skills + 20% rol   (menos 10 si el inglés es "revisar")

- Semántico: similitud entre el texto de la oferta y tu perfil, con un modelo
  multilingüe que corre DENTRO de GitHub Actions (fastembed/ONNX, sin torch).
  Tu perfil nunca sale de GitHub.
- Skills: cuántas de tus skills (me/skills.txt) menciona la oferta.
- Rol: prioridad de roles de me/settings.toml ([[roles]]); si no hay, ROLE_GROUPS.

Todo recibe el "embedder" por parámetro: los tests usan uno falso y no
necesitan descargar el modelo.
"""
import math
import os

from src.filters import contains_phrase, load_list, normalize
from src.gaps import find_gaps, gap_penalty
from src.language import english_requirement
from src.models import Job

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MODEL_CACHE_DIR = ".cache/fastembed"   # GitHub Actions lo cachea entre corridas

WEIGHTS = {"semantic": 0.5, "skills": 0.3, "role": 0.2}

# Calibración: con este modelo la similitud entre textos rara vez baja de ~0.15
# o pasa de ~0.65. Se reescala a 0-1 para que el % sea legible.
# Son supuestos iniciales: se ajustan mirando datos reales (ver --dry-run).
SIM_FLOOR, SIM_CEIL = 0.15, 0.75

SKILLS_FOR_FULL = 5          # con 5 skills tuyas mencionadas, el puntaje de skills es 100%
ENGLISH_REVIEW_PENALTY = 10  # "revisar" no descarta, pero baja en el ranking

# Prioridad de roles POR DEFECTO (si me/settings.toml no tiene [[roles]]).
# La tuya va en me/settings.toml. Gana el primer grupo que matchea el título.
ROLE_GROUPS = [
    (1.0, ["qa", "quality assurance", "tester", "testing", "test", "sdet", "automation engineer", "llm", "ai evaluation", "model evaluation", "ai tutor", "ai quality", "red teaming", "data quality"]),
    (0.8, ["analista funcional", "functional analyst", "business analyst", "fintech",
           "payments", "reconciliation", "conciliacion", "operations analyst"]),
    (0.6, ["data annotation", "annotator", "anotador", "ai trainer", "ai training",
           "evaluator", "evaluador", "rater", "labeling", "etiquetado"]),
    (0.4, ["support", "soporte", "customer", "atencion al cliente", "help desk", "service"]),
]


# ------------------------------------------------------------------ piezas

def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def rescale(similarity: float) -> float:
    """Lleva la similitud del modelo a 0-1 (recortando los extremos)."""
    value = (similarity - SIM_FLOOR) / (SIM_CEIL - SIM_FLOOR)
    return min(max(value, 0.0), 1.0)


def skill_score(text: str, skills: list[str]) -> float:
    found = sum(1 for skill in skills if contains_phrase(text, [skill]))
    return min(found / SKILLS_FOR_FULL, 1.0)


def role_score(title: str, groups=None) -> float:
    """
    Devuelve el valor del PRIMER grupo cuyas palabras aparezcan en el título.
    Si ninguno matchea, 0.0. Sin `groups`, usa ROLE_GROUPS.
    """
    for value, keywords in groups or ROLE_GROUPS:
        if contains_phrase(title, keywords):
            return value
    return 0.0


def job_text(job: Job) -> str:
    # Título 2 veces: pesa más que el resto. La descripción se recorta para que sea rápido.
    return f"{job.title}\n{job.title}\n{job.description[:2000]}"


def score_jobs(jobs: list[Job], profile_text: str, embedder,
               skills: list[str] | None = None, tech: list[str] | None = None,
               role_groups=None) -> dict[str, int]:
    """Devuelve {uid: % de match} para cada oferta. Un solo llamado al modelo para todas."""
    if not jobs:
        return {}
    skills = skills if skills is not None else load_list("skills.txt")
    tech = tech if tech is not None else load_list("tech.txt")
    if role_groups is None:
        from src.settings import load_settings
        role_groups = load_settings().role_groups or ROLE_GROUPS
    vectors = embedder.embed([profile_text] + [job_text(j) for j in jobs])
    profile_vec, job_vecs = vectors[0], vectors[1:]

    scores = {}
    for job, vec in zip(jobs, job_vecs):
        raw = (
            WEIGHTS["semantic"] * rescale(cosine(profile_vec, vec))
            + WEIGHTS["skills"] * skill_score(f"{job.title}\n{job.description}", skills)
            + WEIGHTS["role"] * role_score(job.title, role_groups)
        )
        pct = round(raw * 100)
        if english_requirement(job.description) == "revisar":
            pct -= ENGLISH_REVIEW_PENALTY
        pct -= gap_penalty(find_gaps(job.description, tech, skills))
        scores[job.uid] = min(max(pct, 0), 100)
    return scores


# ------------------------------------------------------------- modelo real

class FastEmbedder:
    """Embeddings locales con fastembed. El modelo se descarga una vez (~220 MB) y se cachea."""

    def __init__(self, model_name: str = MODEL_NAME, cache_dir: str = MODEL_CACHE_DIR):
        from fastembed import TextEmbedding   # import acá: los tests no lo necesitan
        self._model = TextEmbedding(model_name, cache_dir=cache_dir)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [list(map(float, v)) for v in self._model.embed(texts)]


def default_scorer(jobs: list[Job]) -> dict[str, int] | None:
    """
    Lo que usa el bot de verdad. Si no hay PROFILE_TEXT (ej. en los tests o en
    tu compu sin el secret), devuelve None y el bot ordena por fecha como antes.
    """
    profile = os.environ.get("PROFILE_TEXT", "").strip()
    if not profile or not jobs:
        return None
    return score_jobs(jobs, profile, FastEmbedder())