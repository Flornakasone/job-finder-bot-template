"""
Dónde vive cada configuración.

    me/             TUS datos (keywords, skills, empresas, settings…). En tu repo privado.
    config/         lo que sirve para cualquiera (excluded.txt: estafas, MLM…).
    templates/me/   ejemplos para arrancar. Los usa el bot si todavía no armaste me/.

Orden de búsqueda de un archivo: me/ -> config/ -> templates/me/
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ME_DIR = ROOT / "me"
CONFIG_DIR = ROOT / "config"
TEMPLATE_DIR = ROOT / "templates" / "me"
SEARCH_ORDER = (ME_DIR, CONFIG_DIR, TEMPLATE_DIR)


def find_config(name: str, search=SEARCH_ORDER) -> Path:
    """Primer lugar donde existe `name`. Si no está en ninguno: FileNotFoundError."""
    for folder in search:
        path = folder / name
        if path.exists():
            return path
    raise FileNotFoundError(f"No encontré {name} en me/, config/ ni templates/me/")


def using_template(me_dir: Path = ME_DIR) -> bool:
    """True si todavía no armaste tu carpeta me/ (el bot corre con los ejemplos)."""
    return not me_dir.is_dir()
