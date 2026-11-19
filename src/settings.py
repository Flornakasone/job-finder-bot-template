"""
Lee settings.toml (me/ -> config/ -> templates/me/): lo configurable del bot.

tomllib viene con Python 3.11+: no suma dependencias.
Si falta una clave, se usa el valor por defecto (así un fork arranca con lo mínimo).
"""
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from src.paths import find_config


@dataclass(frozen=True)
class Settings:
    top_n: int = 10
    min_score: int = 0
    title_region_blocklist: list[str] = field(default_factory=list)
    spoken_languages: list[str] = field(default_factory=list)
    weekly_gaps_day: str = ""        # "" = sin reporte semanal
    accepted_locations: list[str] = field(default_factory=list)
    onsite_locations: list[str] = field(default_factory=list)
    # [(peso, [palabras]), ...] en orden de prioridad: gana el primer grupo que matchea
    role_groups: list[tuple[float, list[str]]] = field(default_factory=list)


def load_settings(path: Path | None = None) -> Settings:
    """Lee settings.toml (me/ -> config/ -> templates/me/). Sin archivo: valores por defecto."""
    if path is None:
        try:
            path = find_config("settings.toml")
        except FileNotFoundError:
            return Settings()
    if not path.exists():
        return Settings()
    with path.open("rb") as f:          # tomllib pide el archivo en modo binario
        data = tomllib.load(f)
    ranking, filters = data.get("ranking", {}), data.get("filters", {})
    report = data.get("report", {})
    location = data.get("location", {})
    defaults = Settings()
    return Settings(
        top_n=int(ranking.get("top_n", defaults.top_n)),
        min_score=int(ranking.get("min_score", defaults.min_score)),
        title_region_blocklist=list(filters.get("title_region_blocklist", [])),
        spoken_languages=list(filters.get("spoken_languages", [])),
        weekly_gaps_day=str(report.get("weekly_gaps_day", "")),
        accepted_locations=list(location.get("accepted", [])),
        onsite_locations=list(location.get("onsite_ok", [])),
        role_groups=[(float(g["weight"]), list(g["words"])) for g in data.get("roles", [])],
    )
