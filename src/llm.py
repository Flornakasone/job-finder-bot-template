"""
Cliente mínimo de Groq (API compatible con OpenAI) usando requests: sin dependencias nuevas.

- Respuesta en JSON validado por esquema (structured outputs, strict).
- Si Groq responde 429 (cupo por minuto), espera lo que pide `retry-after` y reintenta.
- Los errores nunca incluyen la API key ni el texto enviado.

Términos verificados (2026-11-03): Groq no usa inputs/outputs para entrenar modelos
(Services Agreement §4.2) y la cuenta tiene Zero Data Retention activado.
"""
import json
import time

import requests

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "openai/gpt-oss-20b"
TIMEOUT_SECONDS = 60
MAX_WAIT_SECONDS = 60      # nunca esperar más que esto por un 429


class LLMError(Exception):
    """
    Cualquier problema con el LLM. El mensaje nunca trae datos sensibles.
    fatal=True: no tiene sentido seguir con otros avisos (key inválida, sin cupo diario…).
    """

    def __init__(self, message: str, fatal: bool = False):
        super().__init__(message)
        self.fatal = fatal


# Qué hacemos con cada respuesta de Groq
#   200        -> OK
#   429        -> esperar retry-after y reintentar; si pide esperar más de MAX_WAIT (cupo
#                 diario agotado) o se acaban los reintentos -> fatal, cortar
#   401 / 403  -> key inválida o sin permiso -> fatal, cortar
#   400 / 413  -> request inválida o demasiado larga (ese aviso) -> saltear el aviso
#   5xx        -> problema de Groq -> saltear el aviso (si se repite, evaluate corta)
#   red / JSON roto -> saltear el aviso
FATAL_STATUS = {401, 403}


class GroqClient:
    def __init__(self, api_key: str, session=None, sleep=time.sleep,
                 max_retries: int = 3, model: str = MODEL):
        self._key = api_key
        self._http = session or requests
        self._sleep = sleep
        self._max_retries = max_retries
        self._model = model

    def complete_json(self, system: str, user: str, schema: dict) -> dict:
        payload = {
            "model": self._model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "reasoning_effort": "low",        # menos tokens de razonamiento = menos cupo
            "include_reasoning": False,       # solo queremos la respuesta final
            "max_completion_tokens": 1000,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "evaluacion", "strict": True, "schema": schema},
            },
        }
        headers = {"Authorization": f"Bearer {self._key}"}

        for attempt in range(self._max_retries + 1):
            try:
                resp = self._http.post(GROQ_URL, json=payload, headers=headers,
                                       timeout=TIMEOUT_SECONDS)
            except requests.RequestException as exc:
                raise LLMError(f"Groq: {type(exc).__name__}") from None

            if resp.status_code == 429:
                wait = _retry_after(resp)
                if wait > MAX_WAIT_SECONDS or attempt == self._max_retries:
                    break                     # cupo agotado: esperar no sirve
                self._sleep(wait)
                continue
            if resp.status_code in FATAL_STATUS:
                raise LLMError(f"Groq respondió {resp.status_code} (revisá GROQ_API_KEY)", fatal=True)
            if resp.status_code != 200:
                raise LLMError(f"Groq respondió {resp.status_code}")
            try:
                return json.loads(resp.json()["choices"][0]["message"]["content"])
            except (ValueError, KeyError, IndexError, TypeError):
                raise LLMError("Groq: respuesta con formato inesperado") from None

        raise LLMError("Groq: sin cupo (429)", fatal=True)


def _retry_after(resp) -> float:
    """Segundos que pide esperar el header retry-after. Sin header o inválido: 20 s."""
    try:
        return float(resp.headers.get("retry-after", 20))
    except (TypeError, ValueError):
        return 20.0
