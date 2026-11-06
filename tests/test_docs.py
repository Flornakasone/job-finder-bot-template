"""
Tests de la documentación: si alguien suma un secreto al workflow y se olvida
de documentarlo en SETUP.md, un usuario nuevo se queda trabado. Esto lo evita.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "daily.yml"
SETUP = ROOT / "SETUP.md"


def test_todos_los_secretos_del_workflow_estan_en_setup():
    secrets = set(re.findall(r"secrets\.([A-Z_]+)", WORKFLOW.read_text(encoding="utf-8")))
    setup = SETUP.read_text(encoding="utf-8")
    missing = sorted(s for s in secrets if s not in setup)
    assert not missing, f"Secretos sin documentar en SETUP.md: {missing}"


def test_setup_menciona_todos_los_archivos_del_template():
    setup = SETUP.read_text(encoding="utf-8")
    for name in ("keywords.txt", "skills.txt", "tech.txt", "empresas.txt", "settings.toml"):
        assert name in setup, f"{name} no está explicado en SETUP.md"
