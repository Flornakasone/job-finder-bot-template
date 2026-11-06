"""
Formato común de una oferta de empleo.

Cada fuente (Remotive, Jobicy, ...) trae los datos con su propio formato.
La función fetch() de cada fuente los convierte a `Job`, así el resto del
bot (filtros, scoring, deduplicación, mensaje) trabaja siempre igual.
"""
from dataclasses import dataclass, field
from hashlib import sha256


@dataclass(frozen=True)  # frozen: una vez creada, la oferta no se modifica por error
class Job:
    source: str          # nombre de la fuente, ej. "Remotive" (se muestra como "vía X")
    source_id: str       # id de la oferta dentro de esa fuente
    title: str
    company: str
    url: str             # link original de la fuente (lo exigen sus términos)
    location: str = ""   # texto libre, ej. "Worldwide", "LATAM", "USA only"
    description: str = ""  # texto plano, sin HTML
    published_at: str = ""  # fecha ISO 8601, ej. "2026-10-22T10:00:00"
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self):
        # Validación mínima: sin estos datos la oferta no sirve
        for name in ("source", "source_id", "title", "url"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"Job sin '{name}'")

    @property
    def uid(self) -> str:
        """
        Identificador único y estable para deduplicar.
        Es un hash de fuente + id: no guarda nada legible de la oferta
        y es igual en todas las corridas.
        """
        raw = f"{self.source.lower()}:{self.source_id}"
        return sha256(raw.encode("utf-8")).hexdigest()[:16]
