"""
Request HTTP compartida por todas las fuentes.
Centraliza timeout, User-Agent y manejo de errores en un solo lugar.
"""
import requests

from src.sources import SourceError

TIMEOUT_SECONDS = 30
HEADERS = {"User-Agent": "job-finder-bot/0.1 (uso personal)"}


def get_json(
    url: str,
    source_name: str,
    params: dict | None = None,
    session: requests.Session | None = None,
):
    """
    Hace un GET y devuelve el JSON.
    Cualquier problema (red, timeout, HTTP 4xx/5xx, respuesta que no es JSON)
    se convierte en SourceError con un mensaje sin datos sensibles.
    """
    http = session or requests
    try:
        resp = http.get(url, params=params, headers=HEADERS, timeout=TIMEOUT_SECONDS)
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise SourceError(f"{source_name}: {type(exc).__name__}") from None
