"""Живой прогон `/mast-ru:init-project --check` (A-25) на установленном плагине: фикстура
ML-проекта `tests/fixtures/prod/` с тремя внешними системами — сначала без каркаса, потом
с каркасом, собранным из шаблонов того же плагина.

Обычный `pytest` файл пропускает: платно (две сессии `claude -p` модели по умолчанию).

  MAST_LIVE=1 python3 -m pytest tests/test_init_live.py -v -s

Каталог проекта — `MAST_LIVE_DIR` (по умолчанию `/private/tmp/mast-check-a25`): в нём уже
поставлен `mast-ru` через `tools/serve_marketplace.py` (`--scope local`, CLAUDE.md), репозитория
ещё нет. Шаблоны каркаса — из `installPath` этой установки в `installed_plugins.json`; установки
`--scope local` нет — из установки `--scope user`.

Что предложено, сверяется механически: строка `Прод:` — из вывода команды, список файлов —
вторым ходом той же сессии, ответом `ФАЙЛЫ: …`. Дерево git сверяется после обоих ходов.
"""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures" / "prod"
DIR = Path(os.environ.get("MAST_LIVE_DIR", "/private/tmp/mast-check-a25"))
CLAUDE_HOME = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
# Внешние системы фикстуры — по признаку в шаблоне: хост, бакет, инструмент
SYSTEMS = ("gpu01", "data-bucket", "clearml")
# Каркас целиком: пять базовых артефактов, правила Context7 и моделей — файл и его шаблон
SCAFFOLD = {"CLAUDE.md": "CLAUDE.template.md", "ROADMAP.md": "ROADMAP.template.md",
            ".claude/rules/example.md": "rule.template.md",
            ".claude/rules/context7.md": "context7.rule.template.md",
            ".claude/rules/dispatch.md": "dispatch.rule.template.md"}
# Строка настройки в выводе — и в блоке diff (`+`), и в кавычках
PROD = re.compile(r"^[+\s`]*Прод:\s*(.+?)`?\s*$", re.M)
FILES = re.compile(r"ФАЙЛЫ:\s*(.*)")
ASK = ("Не меняя файлов, ответь одной строкой без форматирования: ФАЙЛЫ: <пути файлов и "
       "каталогов, которые ты предложил создать или изменить, через запятую>")

pytestmark = pytest.mark.skipif(os.environ.get("MAST_LIVE") != "1", reason="живой замер — MAST_LIVE=1")


def sh(*args, stdin=None):
    r = subprocess.run(args, cwd=DIR, input=stdin, capture_output=True, text=True)
    assert r.returncode == 0, f"{args}: {r.stdout}{r.stderr}"
    return r.stdout


def git(*args):
    return sh("git", "-c", "user.name=t", "-c", "user.email=t@t", *args)


def status():
    return git("status", "--porcelain", "--untracked-files=all")


def claude(prompt, *args):
    """Ход `claude -p`; промпт — через stdin. Возвращает (сессия, текст ответа)."""
    out = json.loads(sh("claude", "-p", "--output-format", "json", *args, stdin=prompt))
    print(f"[{out['session_id']}] ${out.get('total_cost_usd', 0):.2f}")
    return out["session_id"], out.get("result", "")


def templates():
    """Шаблоны установленного `mast-ru`: запись `--scope local` для DIR, иначе `--scope user`."""
    data = json.loads((CLAUDE_HOME / "plugins" / "installed_plugins.json").read_text(encoding="utf-8"))
    found = [e for k, v in data["plugins"].items() if k.startswith("mast-ru@") for e in v]
    found = ([e for e in found if e.get("projectPath") == os.path.realpath(DIR)]
             or [e for e in found if e["scope"] == "user"])
    assert found, f"mast-ru не установлен для {DIR} — см. докстринг"
    print(f"плагин: {found[0]['installPath']}")
    return Path(found[0]["installPath"]) / "locales" / "ru" / "templates"


def check():
    """Прогон `--check` и вопрос о предложенном. Возвращает (шаблоны `Прод:`, файлы, изменения дерева)."""
    before = status()
    sid, out = claude("/mast-ru:init-project --check")
    prod = {p.strip(" `") for line in PROD.findall(out) for p in line.split(",") if p.strip(" `")}
    _, answer = claude(ASK, "--resume", sid)
    m = FILES.search(answer)
    files = {f.strip(" `").rstrip("/") for f in m.group(1).split(",") if f.strip(" `")} if m else None
    changed = status() != before
    print(f"Прод: {sorted(prod)}\nФАЙЛЫ: {sorted(files) if files is not None else answer!r}\n"
          f"дерево изменено: {changed}")
    return prod, files, changed


def named(prod):
    """(названные системы, шаблоны сверх найденного)."""
    return ({s for s in SYSTEMS if any(s in p for p in prod)},
            {p for p in prod if not any(s in p for s in SYSTEMS)})


@pytest.fixture
def project():
    assert not (DIR / ".git").exists(), f"{DIR} уже репозиторий — проба берёт чистый каталог"
    shutil.copytree(FIX, DIR, dirs_exist_ok=True)
    git("init", "-q", "-b", "main")
    # Настройки установки плагина — не файлы проекта, где бы ни стоял глобальный ignore
    with open(DIR / ".git" / "info" / "exclude", "a", encoding="utf-8") as f:
        f.write(".claude/settings.local.json\n")
    git("add", "-A")
    git("commit", "-qm", "init")
    return DIR


def test_прод_из_файлов_проекта_и_каркас_без_лишнего(project):
    # Без каркаса: строка `Прод:` из описи, дерево не тронуто
    bare = check()

    # Каркас целиком из шаблонов того же плагина — предложить остаётся только `.claude/mast.md`
    t = templates()
    for dest, name in SCAFFOLD.items():
        (DIR / dest).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(t / name, DIR / dest)
    (DIR / "docs" / "roadmap").mkdir(parents=True, exist_ok=True)
    (DIR / "docs" / "roadmap" / ".gitkeep").touch()
    with open(DIR / ".gitignore", "a", encoding="utf-8") as f:
        f.write(".claude/worktrees/\n")
    git("add", "-A")
    git("commit", "-qm", "каркас")
    full = check()

    # Сначала итог обоих сценариев, потом отказ: замер «было» нужен целиком
    runs = (("без каркаса", bare), ("с каркасом", full))
    for name, (prod, files, changed) in runs:
        systems, extra = named(prod)
        print(f"{name}: систем {len(systems)} из {len(SYSTEMS)}, сверх — {sorted(extra)}, "
              f"файлы — {files}, дерево изменено — {changed}")
    for name, (prod, files, changed) in runs:
        systems, extra = named(prod)
        assert systems == set(SYSTEMS) and not extra, f"{name}: {prod}"
        assert not changed, f"{name}: --check изменил дерево"
    assert bare[1] is not None and ".claude/mast.md" in bare[1], bare[1]
    assert full[1] == {".claude/mast.md"}, full[1]
