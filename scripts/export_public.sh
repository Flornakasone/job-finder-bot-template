#!/usr/bin/env bash
# Exporta una copia PÚBLICA y limpia del bot, lista para subir al repo template.
#
# - Copia SOLO los archivos que git versiona (nada de .venv, .cache, __pycache__).
# - Saca lo personal: me/, data/.
# - NO copia el historial de git (el historial privado tiene tus datos viejos).
# - Busca datos personales con los patrones de me/private_patterns.txt
#   (salvo en LICENSE, que lleva tu nombre a propósito como autora)
#   (ese archivo vive en me/, así que nunca se exporta).
# - Corre los tests sobre la copia: si algo depende de tus datos, falla acá.
#
# Uso:  bash scripts/export_public.sh ../job-finder-bot-template
set -euo pipefail

DEST="${1:?Uso: bash scripts/export_public.sh <carpeta destino>}"
PATTERNS="me/private_patterns.txt"

if [[ -e "$DEST" ]]; then
  echo "✗ $DEST ya existe. Borrala o elegí otra carpeta." >&2; exit 1
fi
if [[ ! -f "$PATTERNS" ]]; then
  echo "✗ Falta $PATTERNS (una palabra por línea: tu nombre, email, empresas…)" >&2; exit 1
fi

echo "1/4 Copiando archivos versionados (sin me/ ni data/)…"
mkdir -p "$DEST"
git ls-files -z | while IFS= read -r -d '' f; do
  case "$f" in
    me/*|data/*) continue ;;
  esac
  mkdir -p "$DEST/$(dirname "$f")"
  cp "$f" "$DEST/$f"
done

echo "2/4 Buscando datos personales…"
if grep -rniF --exclude=LICENSE -f <(grep -v "^#" "$PATTERNS" | grep -v "^$") "$DEST" ; then
  echo "✗ Encontré datos personales (arriba). Corregilos en el repo privado y volvé a exportar." >&2
  rm -rf "$DEST"; exit 1
fi
echo "   ✓ ninguno"

echo "3/4 Corriendo los tests sobre la copia (sin me/, usa templates/me/)…"
( cd "$DEST" && python3 -m pytest -q ) || { echo "✗ Fallan tests en la copia pública." >&2; exit 1; }

echo "4/4 Listo: $DEST"
echo "   Siguiente: cd $DEST && git init && git add . && git commit -m 'feat: v1.0'"
