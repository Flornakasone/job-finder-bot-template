"""
Language gate: qué nivel de inglés pide cada oferta.

Devuelve un nivel, no solo sí/no:
    "excluyente" -> pide inglés avanzado/fluido/C1+/nativo como obligatorio: se descarta
    "revisar"    -> lo pide con palabras ambiguas ("excelente nivel", "strong English
                    skills"): pasa, pero te avisa para que lo leas vos
    "intermedio" -> pide intermedio / B1 / B2
    "deseable"   -> lo menciona como plus
    ""           -> no dice nada

Cada oración se evalúa por separado: el "plus" de una oración no
suaviza el "required" de otra. Si hay varias, gana la más exigente.
"""
import re

from src.filters import normalize

# Exigencias claras de inglés avanzado
ADVANCED_ENGLISH = [
    r"fluent (\w+ ){0,3}english", r"english fluency", r"fluency in english",
    r"advanced english", r"native english", r"english native",
    r"native[- ]level english", r"(english|ingles)[^.\n]{0,30}\bc[12]\b",
    r"\bc[12]\b[^.\n]{0,30}(english|ingles)", r"bilingual",
    r"ingles (\w+ ){0,2}(avanzado|fluido|nativo|bilingue)",
    r"(avanzado|fluido|nativo) (de |en )?(el )?ingles",
]

# Formas ambiguas: puede ser intermedio o avanzado según la empresa
AMBIGUOUS_ENGLISH = [
    r"(dominio|manejo) (del idioma |de )?ingles",
    r"(excelente|muy buen) (nivel de )?ingles",
    r"(strong|excellent|solid|great) (written and verbal |verbal and written |written |verbal |spoken )?english",
    r"english (communication |language )?skills",
    r"proficien(t|cy) (in )?english",
    r"professional (working )?(english|proficiency)",
    r"business english",
]

INTERMEDIATE_ENGLISH = [
    r"(english|ingles)[^.\n]{0,25}\b(intermedio|intermediate|b1|b2)\b",
    r"\b(intermedio|intermediate|b1|b2)\b[^.\n]{0,25}(english|ingles)",
]

# Tu perfil: inglés ESCRITO avanzado (C1), conversación intermedia.
# Si piden avanzado solo por escrito, no se descarta: pasa como "revisar".
WRITTEN = ["written", "writing", "escrito", "escritura", "redaccion"]
SPOKEN = ["spoken", "verbal", "oral", "conversation", "speaking", "conversacion", "hablado"]

NICE_TO_HAVE = [
    "plus", "nice to have", "nice-to-have", "preferred", "is a bonus", "bonus",
    "desirable", "deseable", "valorable", "se valora", "no excluyente",
]

# Prioridad: si hay varias oraciones, gana la de mayor número
PRIORITY = {"": 0, "deseable": 1, "intermedio": 2, "revisar": 3, "excluyente": 4}


def _matches(patterns: list[str], sentence: str) -> bool:
    return any(re.search(p, sentence) for p in patterns)


def sentence_level(sentence: str) -> str:
    """Nivel que pide UNA oración (ya normalizada)."""
    soft = any(word in sentence for word in NICE_TO_HAVE)
    if _matches(ADVANCED_ENGLISH, sentence):
        if soft:
            return "deseable"
        written_only = any(w in sentence for w in WRITTEN) and not any(w in sentence for w in SPOKEN)
        return "revisar" if written_only else "excluyente"
    if _matches(AMBIGUOUS_ENGLISH, sentence):
        return "deseable" if soft else "revisar"
    if _matches(INTERMEDIATE_ENGLISH, sentence):
        return "intermedio"
    return ""


def strongest(levels: list[str]) -> str:
    """
    Devuelve el nivel más exigente de la lista según PRIORITY.
    Lista vacía o sin niveles -> "".
    """
    levels = [level for level in levels if level in PRIORITY]
    if not levels:
        return ""
    return max(levels, key=lambda level: PRIORITY[level])


def english_requirement(description: str) -> str:
    sentences = re.split(r"[.\n;•]+", normalize(description))
    return strongest([sentence_level(s) for s in sentences])


def looks_english(text: str) -> bool:
    """Heurística simple: ¿el aviso está escrito en inglés?"""
    words = re.findall(r"[a-z]+", normalize(text))
    en = sum(w in {"the", "and", "with", "you", "our", "will", "for", "are"} for w in words)
    es = sum(w in {"el", "la", "los", "las", "con", "para", "que", "del", "una"} for w in words)
    return en > es


def english_label(description: str) -> str:
    """Texto para el mensaje de Telegram."""
    level = english_requirement(description)
    labels = {
        "excluyente": "excluyente",            # no debería llegar: el filtro la descarta
        "revisar": "revisar el requisito ⚠️",
        "intermedio": "intermedio",
        "deseable": "deseable",
    }
    if level in labels:
        return labels[level]
    return "no indica nivel (aviso en inglés)" if looks_english(description) else "no menciona"
