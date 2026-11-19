"""
Dobles de prueba (test doubles) compartidos por los tests de todas las fuentes.
Simulan requests.Session para probar errores de red sin internet.
"""
import requests


class FakeResponse:
    def __init__(self, payload=None, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")

    def json(self):
        if self._payload is None:
            raise ValueError("no es JSON")
        return self._payload


class FakeSession:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.calls = response, error, 0
        self.last_params = None

    def get(self, url, **kwargs):
        self.calls += 1
        self.last_params = kwargs.get("params")
        assert kwargs.get("timeout"), "siempre hay que pasar timeout"
        if self.error:
            raise self.error
        return self.response
