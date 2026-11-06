"""
Tests de main() (la línea de comandos que corre GitHub Actions).
- Humo: arranca y termina bien con --dry-run --offline (#47).
- Privacidad: ningún secreto ni el perfil aparecen en lo que imprime (#22).
"""
import sys

import pytest

from src import main as main_module
from src.models import Job

SECRETS = {
    "TELEGRAM_TOKEN": "123456:TOKEN_SECRETO",
    "TELEGRAM_CHAT_ID": "987654321",
    "PROFILE_TEXT": "PERFIL_PRIVADO_CANARY",
    "LLM_PROFILE": "PERFIL_GENERALIZADO_PRIVADO",
    "GROQ_API_KEY": "gsk_CLAVE_SECRETA",
}


def jobs():
    return [Job(source="Remotive", source_id=str(i), title=f"QA Analyst {i}", company="Acme",
                url=f"https://remotive.com/remote-jobs/qa/{i}", location="Worldwide",
                description="Testing funcional y APIs con Postman. Requisito: Cypress.")
            for i in range(1, 4)]


class FakeEmbedder:
    def __init__(self, *a, **kw):
        pass

    def embed(self, texts):
        return [[1.0, 0.5] for _ in texts]


class FakeGroq:
    def __init__(self, *a, **kw):
        pass

    def complete_json(self, system, user, schema):
        return {"verdict": "GO", "aporto": "QA y APIs", "falta": "Cypress"}


@pytest.fixture
def cli(monkeypatch):
    """Corre main() con argumentos, sin internet, sin modelo y sin Groq real."""
    monkeypatch.setattr("src.filters._load_or_fetch", lambda offline: jobs())
    monkeypatch.setattr("src.scoring.FastEmbedder", FakeEmbedder)
    monkeypatch.setattr("src.evaluate.GroqClient", FakeGroq)
    monkeypatch.setattr("src.evaluate.PAUSE_SECONDS", 0)

    def run_cli(*args):
        monkeypatch.setattr(sys, "argv", ["main", *args])
        return main_module.main()
    return run_cli


def test_humo_dry_run_offline_termina_bien(cli, capsys):
    assert cli("--dry-run", "--offline") == 0
    out = capsys.readouterr().out
    assert "[resumen] traídas=3" in out


def test_offline_sin_dry_run_es_un_error(cli, capsys):
    assert cli("--offline") == 2
    assert "--offline solo se puede usar con --dry-run" in capsys.readouterr().err


def test_ningun_secreto_ni_perfil_aparece_en_la_salida(cli, capsys, monkeypatch):
    for name, value in SECRETS.items():
        monkeypatch.setenv(name, value)
    assert cli("--dry-run", "--offline") == 0
    out, err = capsys.readouterr()
    assert "evaluadas_ia=3" in out                  # el camino con perfil y Groq sí se ejecutó
    for name, value in SECRETS.items():
        assert value not in out + err, f"{name} apareció en la salida"
