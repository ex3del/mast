"""Страховка на случай, если .githooks/pre-commit не установлен."""
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = "plugins/en/.claude-plugin/plugin.json"
METHOD = ["hooks", "locales", "plugins"]


def _последний_коммит(*пути):
    """Unix-время последнего коммита, тронувшего эти пути; 0 — таких нет."""
    out = subprocess.run(
        ["git", "log", "-1", "--format=%ct", "--", *пути],
        cwd=ROOT, capture_output=True, text=True,
    )
    return int(out.stdout.strip() or 0)


def test_хук_отказывает_если_версию_проверить_нечем():
    """Без `python3` проверить версию нельзя, и хук обязан отказать: молчаливый
    пропуск выпускает релиз, которого никто не получит. Поведение до починки
    воспроизводилось вручную — PATH без python3 давал exit 0."""
    text = (ROOT / ".githooks" / "pre-commit").read_text(encoding="utf-8")
    guard = re.search(r"command -v python3.*?\{(.*?)\}", text, re.S)
    assert guard, "в хуке нет проверки наличия python3"
    assert "exit 1" in guard.group(1), "хук без python3 пропускает коммит вместо отказа"


def test_версия_поднята_не_раньше_последней_правки_метода():
    if _последний_коммит(MANIFEST) == 0:
        pytest.skip("нет истории git")
    assert _последний_коммит(MANIFEST) >= _последний_коммит(*METHOD), (
        "метод менялся позже манифеста: обновление не доедет до пользователей, "
        f"подними version в {MANIFEST}"
    )
