"""Страховка на случай, если .githooks/pre-commit не установлен."""
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ".claude-plugin/plugin.json"
METHOD = ["hooks", "skills", "commands", "locales", ".mcp.json"]


def _последний_коммит(*пути):
    """Unix-время последнего коммита, тронувшего эти пути; 0 — таких нет."""
    out = subprocess.run(
        ["git", "log", "-1", "--format=%ct", "--", *пути],
        cwd=ROOT, capture_output=True, text=True,
    )
    return int(out.stdout.strip() or 0)


def test_версия_поднята_не_раньше_последней_правки_метода():
    if _последний_коммит(MANIFEST) == 0:
        pytest.skip("нет истории git")
    assert _последний_коммит(MANIFEST) >= _последний_коммит(*METHOD), (
        "метод менялся позже манифеста: обновление не доедет до пользователей, "
        f"подними version в {MANIFEST}"
    )
