"""
Fuentes de empleo. Cada módulo de esta carpeta cumple el mismo contrato:

    NAME: str                  # nombre que se muestra como "vía X"
    fetch() -> list[Job]       # trae y normaliza las ofertas

Si algo falla, fetch() lanza SourceError y el bot sigue con las demás.
"""


class SourceError(Exception):
    """Una fuente no respondió bien. Su mensaje nunca trae datos sensibles."""
