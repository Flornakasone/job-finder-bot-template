"""
Integrity gate: limpia los avisos ANTES de usarlos y marca los que traen
instrucciones dirigidas a una IA (prompt injection).

Por qué: un aviso es texto de terceros. Puede traer
- caracteres invisibles que esconden palabras ("multi​nivel" no matchea "multinivel")
- instrucciones para una IA ("ignore previous instructions", "if you are an AI, …")
  Algunas son trampas que ponen las empresas para detectar postulaciones hechas con IA.

Reglas:
- `sanitize` se aplica a TODOS los avisos, antes de los filtros.
- Un aviso con `injection_signals` no se le manda nunca a un LLM (issue #16).
- Los logs solo muestran conteos: nunca el texto del aviso.

Todo local, sin servicios externos. Decisión: docs/decisions/0001-match-en-dos-etapas.md
"""
import re
from dataclasses import replace

from src.filters import normalize
from src.models import Job

# Caracteres que no se ven pero están: ancho cero, controles de dirección (bidi),
# BOM y "tag characters" (se usan para esconder texto en Unicode).
INVISIBLE = re.compile(
    "[​-‏‪-‮⁠-⁤⁦-⁩﻿\U000e0000-\U000e007f]"
)

# Frases típicas de inyección, en inglés y español (texto ya normalizado).
INJECTION_PATTERNS = [
    r"ignore (all |any )?(the )?(previous|prior|above|earlier) (instructions|prompts?)",
    r"disregard (all |any )?(the )?(previous|prior|above) (instructions|prompts?)",
    r"forget (all |your )?(previous |prior )?instructions",
    r"ignora (todas )?(las )?instrucciones (anteriores|previas)",
    r"olvida (todas )?(tus|las) instrucciones",
    r"system prompt",
    r"if you are an? (ai|llm|language model|chatbot|gpt)",
    r"si (sos|eres) (una )?(ia|inteligencia artificial)",
    r"(ai|llm) (assistant|agent)s? (reading|processing) this",
    r"<\|im_start\|>|\[inst\]|### instruction",
]


def strip_invisible(text: str) -> str:
    """Saca los caracteres invisibles. El resto del texto queda igual."""
    return INVISIBLE.sub("", text or "")




def injection_signals(text: str) -> list[str]:
    """Patrones de INJECTION_PATTERNS que aparecen en el texto (vacío = limpio)."""
    norm = normalize(strip_invisible(text))
    return [pattern for pattern in INJECTION_PATTERNS if re.search(pattern, norm)]  


def sanitize(job: Job) -> Job:
    """Mismo aviso, sin caracteres invisibles en título, empresa y descripción."""
    return replace(
        job,
        title=strip_invisible(job.title),
        company=strip_invisible(job.company),
        description=strip_invisible(job.description),
    )


def is_safe_for_llm(job: Job) -> bool:
    """¿Se le puede mandar este aviso a un LLM? (lo usa el issue #16)."""
    return not injection_signals(job.title) and not injection_signals(job.description)
