"""Utilidades de texto compartidas por todas las fuentes."""
import re
from html.parser import HTMLParser


# Estilos que esconden texto: lo lee una máquina, pero una persona no lo ve
HIDDEN_STYLES = [r"display\s*:\s*none", r"visibility\s*:\s*hidden",
                 r"font-size\s*:\s*0(?![.\d])", r"opacity\s*:\s*0(?![.\d])"]


def is_hidden(attrs: list[tuple[str, str | None]]) -> bool:
    """¿Este elemento HTML está escondido? (atributo hidden, aria-hidden o estilo)."""
    values = {name: (value or "").lower() for name, value in attrs}
    if "hidden" in values or values.get("aria-hidden") == "true":
        return True
    style = values.get("style", "")
    return any(re.search(p, style) for p in HIDDEN_STYLES)


class _TextExtractor(HTMLParser):
    """Junta solo el texto VISIBLE de un HTML: ignora <script>, <style> y elementos escondidos."""

    _SKIP = {"script", "style"}
    _BLOCK = {"p", "br", "li", "div", "h1", "h2", "h3", "h4", "ul", "ol", "tr"}
    # Tags que no tienen cierre: no cuentan para la profundidad
    _VOID = {"br", "img", "hr", "input", "meta", "link", "wbr", "area", "base", "col", "source"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0   # > 0 = estamos adentro de algo que no se ve

    def handle_starttag(self, tag, attrs):
        if tag in self._VOID:
            if tag in self._BLOCK and not self._skip_depth:
                self.parts.append("\n")
            return
        if self._skip_depth or tag in self._SKIP or is_hidden(attrs):
            self._skip_depth += 1          # todo lo de adentro también queda escondido
        elif tag in self._BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag not in self._VOID and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if not self._skip_depth:
            self.parts.append(data)


def html_to_text(raw: str | None) -> str:
    """Convierte la descripción HTML de una oferta en texto plano y prolijo."""
    if not raw:
        return ""
    parser = _TextExtractor()
    parser.feed(raw)  # convert_charrefs=True ya traduce &amp;, &nbsp;, etc.
    text = "".join(parser.parts)
    text = re.sub(r"[ \t\xa0]+", " ", text)      # espacios repetidos -> uno
    text = re.sub(r"\n\s*\n+", "\n", text)       # líneas vacías repetidas -> una
    return text.strip()
