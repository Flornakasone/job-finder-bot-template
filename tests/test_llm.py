"""Tests del cliente de Groq, sin internet: la sesión HTTP es falsa."""
import json

import pytest
import requests

from src.llm import LLMError, GroqClient

SCHEMA = {"type": "object"}


class FakeResp:
    def __init__(self, status=200, content=None, headers=None, body=None):
        self.status_code = status
        self.headers = headers or {}
        self._body = body if body is not None else {
            "choices": [{"message": {"content": json.dumps(content or {"ok": True})}}]
        }

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class FakeSession:
    """Devuelve las respuestas en orden y guarda lo que se le mandó."""

    def __init__(self, *responses, error=None):
        self.responses, self.error, self.calls = list(responses), error, []

    def post(self, url, **kwargs):
        assert kwargs.get("timeout"), "siempre hay que pasar timeout"
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.responses.pop(0)


def make_client(session, **kw):
    waits = []
    client = GroqClient("gsk_SECRETA", session=session, sleep=waits.append, **kw)
    return client, waits


def test_devuelve_el_json_de_la_respuesta():
    client, _ = make_client(FakeSession(FakeResp(content={"verdict": "GO"})))
    assert client.complete_json("sys", "user", SCHEMA) == {"verdict": "GO"}


def test_manda_esquema_estricto_y_razonamiento_bajo():
    session = FakeSession(FakeResp())
    client, _ = make_client(session)
    client.complete_json("sys", "user", SCHEMA)
    payload = session.calls[0]["json"]
    assert payload["response_format"]["json_schema"]["strict"] is True
    assert payload["reasoning_effort"] == "low"
    assert session.calls[0]["headers"]["Authorization"] == "Bearer gsk_SECRETA"


def test_429_espera_lo_que_pide_retry_after_y_reintenta():
    session = FakeSession(FakeResp(429, headers={"retry-after": "7"}), FakeResp(content={"a": 1}))
    client, waits = make_client(session)
    assert client.complete_json("s", "u", SCHEMA) == {"a": 1}
    assert waits == [7.0]


def test_429_que_pide_esperar_mucho_corta_sin_esperar():
    # retry-after de 1 hora = cupo diario agotado: esperar 60 s no lo arregla
    session = FakeSession(FakeResp(429, headers={"retry-after": "3600"}), FakeResp())
    client, waits = make_client(session)
    with pytest.raises(LLMError) as exc:
        client.complete_json("s", "u", SCHEMA)
    assert exc.value.fatal
    assert waits == []
    assert len(session.calls) == 1      # no gastó otra request


def test_429_sin_header_espera_20_segundos():
    client, waits = make_client(FakeSession(FakeResp(429), FakeResp()))
    client.complete_json("s", "u", SCHEMA)
    assert waits == [20]


def test_429_repetido_se_rinde_al_cuarto_intento():
    # max_retries=3 por defecto: 1 intento + 3 reintentos = 4 requests y 3 esperas
    session = FakeSession(*[FakeResp(429) for _ in range(4)])
    client, waits = make_client(session)
    with pytest.raises(LLMError, match="sin cupo") as exc:
        client.complete_json("s", "u", SCHEMA)
    assert exc.value.fatal
    assert len(session.calls) == 4
    assert waits == [20, 20, 20]


# Mapa de errores: cada respuesta -> ¿corta todo (fatal) o solo saltea ese aviso?
ERROR_CASES = [
    pytest.param(FakeResp(401), True, id="401-key-invalida"),
    pytest.param(FakeResp(403), True, id="403-sin-permiso"),
    pytest.param(FakeResp(400), False, id="400-request-invalida"),
    pytest.param(FakeResp(413), False, id="413-aviso-muy-largo"),
    pytest.param(FakeResp(500), False, id="500-error-de-groq"),
    pytest.param(FakeResp(503), False, id="503-groq-caido"),
    pytest.param(FakeResp(body=ValueError("no es JSON")), False, id="respuesta-no-json"),
    pytest.param(FakeResp(body={"choices": []}), False, id="respuesta-vacia"),
    pytest.param(FakeResp(body={"choices": [{"message": {"content": "hola"}}]}), False,
                 id="contenido-no-json"),
]


@pytest.mark.parametrize("response, fatal", ERROR_CASES)
def test_mapa_de_errores(response, fatal):
    client, _ = make_client(FakeSession(response))
    with pytest.raises(LLMError) as exc:
        client.complete_json("s", "u", SCHEMA)
    assert exc.value.fatal is fatal


@pytest.mark.parametrize("response, fatal", ERROR_CASES)
def test_ningun_error_muestra_la_key(response, fatal):
    client, _ = make_client(FakeSession(response))
    with pytest.raises(LLMError) as exc:
        client.complete_json("s", "u", SCHEMA)
    assert "gsk_SECRETA" not in str(exc.value)


def test_error_de_red_no_filtra_la_key():
    session = FakeSession(error=requests.ConnectionError("https://x?key=gsk_SECRETA"))
    client, _ = make_client(session)
    with pytest.raises(LLMError) as exc:
        client.complete_json("s", "u", SCHEMA)
    assert "gsk_SECRETA" not in str(exc.value)
    assert exc.value.__cause__ is None      # tampoco en el traceback encadenado


def test_la_key_va_solo_en_el_header_nunca_en_la_url_ni_en_el_body():
    session = FakeSession(FakeResp())
    client, _ = make_client(session)
    client.complete_json("s", "u", SCHEMA)
    call = session.calls[0]
    assert "gsk_SECRETA" not in str(call["json"])
