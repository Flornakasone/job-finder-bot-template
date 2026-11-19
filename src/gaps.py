"""
Gaps: tecnologías que el aviso pide como OBLIGATORIAS y que no están en tus skills.

    gaps = (config/tech.txt que aparece en el aviso) − config/skills.txt

- Se evalúa oración por oración (igual que el language gate).
- Una oración con "plus", "nice to have", "deseable"… no cuenta: es deseable.
- Cuando aprendés algo, lo sumás a skills.txt y deja de ser gap.

Todo local: no llama a ningún servicio externo.
Decisión: docs/decisions/0001-match-en-dos-etapas.md
"""
import re

from src.filters import contains_phrase, normalize
from src.language import NICE_TO_HAVE

GAP_PENALTY = 10        # puntos que resta cada gap obligatorio
GAP_MAX_PENALTY = 40    # tope: un aviso no baja más que esto por gaps
DESIRABLE_PREFIX = "deseable: "


def split_sentences(text: str) -> list[str]:
    """Oraciones normalizadas y no vacías (mismo corte que el language gate)."""
    return [s.strip() for s in re.split(r"[.\n;•]+", normalize(text)) if s.strip()]


def is_soft(sentence: str) -> bool:
    """¿La oración lo pide como deseable? (palabra completa: 'plus' sí, 'surplus' no)."""
    return contains_phrase(sentence, NICE_TO_HAVE) is not None


def _drop_contained(terms: list[str]) -> list[str]:
    """Si encontró 'dynamics 365' y 'dynamics', se queda con el más largo."""
    return [t for t in terms if not any(t != other and t in other for other in terms)]


def find_gaps(description: str, tech: list[str], skills: list[str]) -> list[str]:
    """Tecnologías de `tech` pedidas como obligatorias que no están en `skills`."""
    known = {normalize(s) for s in skills}
    found = []
    for sentence in split_sentences(description):
        if is_soft(sentence):
            continue

        for term in tech:
            if normalize(term) not in known and normalize(term) not in found and contains_phrase(sentence, [term]):
                found.append(normalize(term))
            pass
    return _drop_contained(found)


def gap_penalty(gaps: list[str]) -> int:
    """GAP_PENALTY puntos por gap, con tope GAP_MAX_PENALTY."""
    return min(len(gaps) * GAP_PENALTY, GAP_MAX_PENALTY)  


def mark_desirable(text: str) -> str:
    """
    Marca cada oración como deseable (para secciones tipo 'desirable' de Get on Board).
    Respeta mayúsculas y tildes del original: la descripción se sigue leyendo bien.
    """
    sentences = [s.strip() for s in re.split(r"[.\n;•]+", text or "") if s.strip()]
    return "\n".join(DESIRABLE_PREFIX + s for s in sentences)