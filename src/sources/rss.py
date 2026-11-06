"""
Lectura de feeds RSS/XML compartida (We Work Remotely, Teamtailor).

Seguridad: el XML es texto de terceros.
- Se usa xml.etree de la librería estándar: no resuelve entidades externas (XXE)
  y con expat >= 2.4.1 (Python 3.12 en Actions lo trae) está protegido contra
  "billion laughs". Por eso no sumamos dependencias.
- Igual se limita el tamaño de la respuesta.
"""
import xml.etree.ElementTree as ET

import requests

from src.sources import SourceError
from src.sources.http import HEADERS, TIMEOUT_SECONDS

MAX_BYTES = 10_000_000   # un feed de empleos no pesa 10 MB; si pesa más, algo raro pasa


def local(tag: str) -> str:
    """'{http://namespace}location' -> 'location' (ignora los namespaces del XML)."""
    return tag.rsplit("}", 1)[-1]


def get_xml(url: str, source_name: str, session=None) -> ET.Element:
    """GET + parseo. Cualquier problema -> SourceError sin datos sensibles."""
    http = session or requests
    try:
        resp = http.get(url, headers=HEADERS, timeout=TIMEOUT_SECONDS)
        resp.raise_for_status()
        content = resp.content
    except requests.RequestException as exc:
        raise SourceError(f"{source_name}: {type(exc).__name__}") from None
    if len(content) > MAX_BYTES:
        raise SourceError(f"{source_name}: respuesta demasiado grande")
    try:
        return ET.fromstring(content)
    except ET.ParseError:
        raise SourceError(f"{source_name}: XML inválido") from None


def items(root: ET.Element) -> list[ET.Element]:
    """Todos los <item> del feed, estén donde estén."""
    return [el for el in root.iter() if local(el.tag) == "item"]


def child_text(item: ET.Element, name: str) -> str:
    """Texto del primer hijo con ese nombre (sin namespace). Vacío si no está."""
    for child in item:
        if local(child.tag) == name:
            return (child.text or "").strip()
    return ""
