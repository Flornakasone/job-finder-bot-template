"""
Filtros duros: deciden si una oferta se descarta, ANTES del scoring.

Cada filtro devuelve un motivo de descarte (str) o None si la oferta pasa.
Son deterministas y no llaman a ningún servicio externo.

Reglas (lo personal se configura en me/settings.toml):
- Ubicación: remoto global, o en las ubicaciones que aceptás; presencial/híbrido solo en tu zona.
- Inglés: descartar si exige avanzado/fluido/C1/C2/nativo como obligatorio.
- Rubro: el título tiene que matchear alguna palabra de config/keywords.txt.
- Excluidos: afiliados, MLM, solo comisión, trading, pagar para postularse, estafas.
"""
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from src.models import Job
from src.paths import CONFIG_DIR, find_config


# ---------------------------------------------------------------- utilidades

def normalize(text: str) -> str:
    """Minúsculas y sin tildes: 'Atención' -> 'atencion'."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.lower()


def load_list(name: str, config_dir: Path | None = None) -> list[str]:
    """
    Lee un .txt de configuración: una entrada por línea, ignora vacías y comentarios.
    Sin config_dir, lo busca en me/ -> config/ -> templates/me/ (ver src/paths.py).
    """
    path = config_dir / name if config_dir else find_config(name)
    lines = path.read_text(encoding="utf-8").splitlines()
    return [normalize(l.strip()) for l in lines if l.strip() and not l.strip().startswith("#")]


def contains_phrase(text: str, phrases: list[str]) -> str | None:
    """
    Devuelve la primera frase encontrada como palabra completa, o None.
    Palabra completa: 'qa' matchea 'QA Engineer' pero NO 'Qatar'.
    """
    norm = normalize(text)
    for phrase in phrases:
        if re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", norm):
            return phrase
    return None


# ------------------------------------------------------------------ ubicación

# Ubicaciones que sirven para CUALQUIERA (remoto sin restricción de país).
# Las tuyas (país, región, ciudad) van en me/settings.toml -> [location] accepted.
# Ojo: "remote" NO está acá, porque "Remote - US" lo contiene y no nos sirve.
GLOBAL_LOCATIONS = ["worldwide", "anywhere", "global", "todo el mundo"]
# "Remote" sin nada más se acepta (no restringe país)
REMOTE_ONLY = {"remote", "remoto", "100% remote", "fully remote", "remote anywhere", "100% remoto"}

# Frases en la descripción que contradicen un "Worldwide"
LOCATION_RESTRICTIONS = [
    "us only", "usa only", "u.s. only", "us-only", "us based only",
    "must be located in the us", "must be based in the us",
    "must reside in the us", "must be a us citizen", "us citizens only",
    "eu only", "uk only", "must be based in europe", "must reside in europe",
    "authorized to work in the united states",
    "authorized to work in the us",
]


def check_location(job: Job, accepted: list[str] | None = None,
                   onsite_ok: list[str] | None = None) -> str | None:
    """
    accepted: ubicaciones tuyas además de las globales (ej. "argentina", "latam").
    onsite_ok: dónde aceptás presencial/híbrido (ej. "caba", "buenos aires").
    Sin parámetros, los lee de settings.
    """
    if accepted is None or onsite_ok is None:
        from src.settings import load_settings
        settings = load_settings()
        accepted = settings.accepted_locations if accepted is None else accepted
        onsite_ok = settings.onsite_locations if onsite_ok is None else onsite_ok
    accepted = [normalize(a) for a in accepted]
    onsite_ok = [normalize(o) for o in onsite_ok]

    location = normalize(job.location)
    if not location.strip():
        return "ubicación vacía"
    on_site = contains_phrase(location, ["presencial", "on-site", "onsite", "in-office"])
    if on_site and not contains_phrase(location, onsite_ok):
        return "presencial fuera de tu zona"
    if location.strip() not in REMOTE_ONLY and not contains_phrase(location, GLOBAL_LOCATIONS + accepted):
        return "ubicación no aceptada"
    restriction = contains_phrase(job.description, LOCATION_RESTRICTIONS)
    if restriction:
        return f"descripción restringe ubicación ({restriction})"
    return None


# --------------------------------------------------------------------- inglés

def check_english(job: Job) -> str | None:
    """Descarta solo si el language gate dice que el inglés avanzado es obligatorio."""
    # Import acá adentro: language.py importa normalize de este archivo,
    # y un import arriba de todo crearía un import circular.
    from src.language import english_requirement

    if english_requirement(job.description) == "excluyente":
        return "exige inglés avanzado"
    return None


# --------------------------------------------------------- rubro y excluidos

def check_role(job: Job, keywords: list[str]) -> str | None:
    if contains_phrase(job.title, keywords):
        return None
    return "rubro no buscado"


def check_excluded(job: Job, excluded: list[str]) -> str | None:
    found = contains_phrase(f"{job.title}\n{job.description}", excluded)
    return f"rubro excluido / estafa ({found})" if found else None

# ------------------------------------------------- región en el título

def title_region_patterns(regions: list[str]) -> list[str]:
    """
    Formas en que un título dice "solo para esta región":
      "QA - US", "QA (US)", "QA | USA", "QA, UK", "US only", "US-based", "UK based".
    """
    patterns = []
    for region in regions:
        r = re.escape(normalize(region))
        patterns += [
            rf"[-–—(|/,]\s*{r}\s*\)?\s*$",       # al final, después de un separador
            rf"\({r}\)",                           # entre paréntesis en cualquier lugar
            rf"(?<![a-z0-9]){r}[- ]?(only|based)(?![a-z0-9])",
            rf"^{r}[\s-]+(remote|based|only)\b",   # al principio: "US Remote ...", "US-based ..."
        ]
    return patterns


def check_title_region(job: Job, regions: list[str]) -> str | None:
    """Descarta si el título restringe el puesto a una región de la blocklist."""
    title = normalize(job.title)
    if any(re.search(p, title) for p in title_region_patterns(regions)):
        return "título restringido a otra región"
    return None

# ------------------------------------------------- idioma en el título

# Idiomas que suelen aparecer en títulos de avisos (inglés y español, sin tildes).
LANGUAGES = {
    "english": ["english", "ingles"],
    "spanish": ["spanish", "espanol", "castellano"],
    "portuguese": ["portuguese", "portugues", "brazilian"],
    "german": ["german", "aleman", "deutsch"],
    "french": ["french", "frances"],
    "italian": ["italian", "italiano"],
    "dutch": ["dutch", "neerlandes", "holandes"],
    "polish": ["polish speaker", "polish speaking", "polaco"],   # "polish" solo es también un verbo
    "russian": ["russian", "ruso"],
    "ukrainian": ["ukrainian", "ucraniano"],
    "turkish": ["turkish", "turco"],
    "arabic": ["arabic", "arabe"],
    "hebrew": ["hebrew", "hebreo"],
    "hindi": ["hindi"],
    "chinese": ["chinese", "mandarin", "cantonese", "chino"],
    "japanese": ["japanese", "japones"],
    "korean": ["korean", "coreano"],
    "vietnamese": ["vietnamese"],
    "thai": ["thai speaker", "thai speaking", "thai language"],
    "indonesian": ["indonesian", "bahasa"],
    "tagalog": ["tagalog", "filipino"],
    "swedish": ["swedish", "sueco"],
    "norwegian": ["norwegian", "noruego"],
    "danish": ["danish", "danes"],
    "finnish": ["finnish", "finlandes"],
    "greek": ["greek", "griego"],
    "czech": ["czech"],
    "romanian": ["romanian", "rumano"],
    "hungarian": ["hungarian", "hungaro"],
    "swahili": ["swahili"],
    "amharic": ["amharic"],
    "oromo": ["oromo"],
}


def check_title_language(job: Job, spoken: list[str]) -> str | None:
    """Descarta si el título pide un idioma que no está en `spoken` (vacío = no filtra)."""
    if not spoken:
        return None
    spoken_norm = {normalize(s) for s in spoken}
    for language, words in LANGUAGES.items():
        if language in spoken_norm or spoken_norm & set(words):
            continue                                   # este idioma lo hablás
        if contains_phrase(job.title, words):
            return "pide un idioma que no hablás"
    return None


# ------------------------------------------------------------------- pipeline

@dataclass
class FilterResult:
    kept: list[Job] = field(default_factory=list)
    rejected: Counter = field(default_factory=Counter)  # motivo -> cantidad (para logs)
    # (motivo, oferta): solo para depurar en local, nunca se loguea en Actions
    rejected_jobs: list[tuple[str, Job]] = field(default_factory=list)


def apply_filters(
    jobs: list[Job],
    keywords: list[str] | None = None,
    excluded: list[str] | None = None,
    title_regions: list[str] | None = None,
    spoken_languages: list[str] | None = None, 
) -> FilterResult:
    from src.settings import load_settings
    settings = load_settings()
    title_regions = settings.title_region_blocklist if title_regions is None else title_regions
    spoken_languages = settings.spoken_languages if spoken_languages is None else spoken_languages
    keywords = keywords if keywords is not None else load_list("keywords.txt")
    excluded = excluded if excluded is not None else load_list("excluded.txt")
    accepted, onsite_ok = settings.accepted_locations, settings.onsite_locations

    checks = [
        lambda j: check_role(j, keywords),
        lambda j: check_excluded(j, excluded),        
        lambda j: check_title_region(j, title_regions),
        lambda j: check_title_language(j, spoken_languages),
        lambda j: check_location(j, accepted, onsite_ok),
        check_english,
    ]
    result = FilterResult()
    for job in jobs:
        reason = next((r for check in checks if (r := check(job))), None)
        if reason:
            result.rejected[reason.split(" (")[0]] += 1
            result.rejected_jobs.append((reason, job))
        else:
            result.kept.append(job)
    return result


def _load_or_fetch(offline: bool) -> list[Job]:
    """
    Trae las ofertas reales y las guarda en .cache/jobs.json (ignorado por git).
    Con --offline las lee del cache: así podés iterar sin gastar requests.
    """
    import json
    from dataclasses import asdict

    from src.main import SOURCES          # todas las fuentes del bot (antes solo 2: #40)
    from src.sources import SourceError

    cache = CONFIG_DIR.parent / ".cache" / "jobs.json"
    if offline:
        data = json.loads(cache.read_text(encoding="utf-8"))
        return [Job(**{**d, "tags": tuple(d["tags"])}) for d in data]

    jobs = []
    for source in SOURCES:
        try:
            jobs += source.fetch()
        except SourceError as err:
            print(f"[error] {err}")
    cache.parent.mkdir(exist_ok=True)
    cache.write_text(json.dumps([asdict(j) for j in jobs], ensure_ascii=False), encoding="utf-8")
    return jobs


if __name__ == "__main__":
    # Prueba manual con datos reales:
    #   python -m src.filters                 -> trae de las APIs y guarda cache
    #   python -m src.filters --offline       -> usa el cache (sin requests)
    #   python -m src.filters --offline --show "rubro"   -> lista los descartados por ese motivo
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="usar .cache/jobs.json")
    parser.add_argument("--show", metavar="MOTIVO", help="listar descartados cuyo motivo contenga este texto")
    args = parser.parse_args()

    all_jobs = _load_or_fetch(args.offline)
    res = apply_filters(all_jobs)

    print(f"\nTraídas: {len(all_jobs)} | Pasan: {len(res.kept)}")
    print("Descartes por motivo:")
    for reason, count in res.rejected.most_common():
        print(f"  {count:4d}  {reason}")
    print("\nOfertas que pasan:")
    for job in res.kept:
        print(f"  - [{job.source}] {job.title} | {job.company} | {job.location}")

    if args.show:
        print(f"\nDescartadas por '{args.show}':")
        for reason, job in res.rejected_jobs:
            if args.show.lower() in reason.lower():
                print(f"  - [{job.source}] {job.title} | {job.location} -> {reason}")