"""
Envío de mensajes a Telegram.

Diseño de seguridad:
- El bot SOLO envía (sendMessage). Nunca llama a getUpdates ni usa webhooks,
  así que cualquier mensaje que alguien le mande al bot se ignora.
- Solo envía al chat_id que está en el secreto TELEGRAM_CHAT_ID.
- Los errores nunca incluyen el token: las excepciones de `requests`
  pueden traer la URL completa (que contiene el token), por eso no se imprimen.
"""
import os
import sys

import requests

API_URL = "https://api.telegram.org/bot{token}/sendMessage"
TIMEOUT_SECONDS = 15
MAX_LEN = 4096  # límite de caracteres por mensaje de Telegram


class NotifierError(Exception):
    """Error de envío. Su mensaje nunca contiene datos sensibles."""


def _get_config() -> tuple[str, str]:
    token = os.environ.get("TELEGRAM_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise NotifierError("Faltan las variables TELEGRAM_TOKEN o TELEGRAM_CHAT_ID")
    return token, chat_id


def send_message(text: str) -> None:
    """Envía `text` a tu chat. Lanza NotifierError si algo falla."""
    token, chat_id = _get_config()
    try:
        resp = requests.post(
            API_URL.format(token=token),
            json={
                "chat_id": chat_id,
                "text": text[:MAX_LEN],
                "disable_web_page_preview": True,
            },
            timeout=TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        # str(exc) puede incluir la URL con el token -> solo mostramos el tipo de error.
        # "from None" evita que el traceback original (con la URL) aparezca en el log.
        raise NotifierError(f"Error de red al enviar ({type(exc).__name__})") from None

    if resp.status_code != 200:
        # La descripción de Telegram (ej. "chat not found") no incluye el token.
        try:
            detail = resp.json().get("description", "")
        except ValueError:
            detail = ""
        raise NotifierError(f"Telegram respondió {resp.status_code}: {detail}")


if __name__ == "__main__":
    # Uso: python -m src.notifier "texto"   (sin texto manda "hola")
    message = sys.argv[1] if len(sys.argv) > 1 else "hola"
    try:
        send_message(message)
    except NotifierError as err:
        print(f"[error] {err}", file=sys.stderr)
        sys.exit(1)
    print("[ok] mensaje enviado")
