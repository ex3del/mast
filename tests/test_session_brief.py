"""Справка на старте сессии: после `/compact` роль и пункт модель не вспоминает сама.

Хук гоняется как на площадке — `dispatcher.py` отдельным процессом, JSON `SessionStart`
на stdin; проект и заглушка `claude` — из `test_mast_status.py`. Роль и пункт хук
узнаёт так же, как живьём: имя сессии (`session_title`) и cwd в `.claude/worktrees/X-N`.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from test_mast_merge import ROOT, env  # noqa: F401 — env нужен как фикстура
from test_mast_status import Status, agent

HOOK = ROOT / "hooks" / "dispatcher.py"
LIMIT = 1500


def brief(cwd, title, tmp_path, env, lang="ru"):  # noqa: F811
    """Вывод хука на `/compact`: то, что площадка добавит в контекст сессии."""
    payload = {"hook_event_name": "SessionStart", "source": "compact", "session_id": "s1",
               "session_title": title, "cwd": str(cwd)}
    full = {k: v for k, v in env.items() if k != "MAST_ROLE"}
    full.update(CLAUDE_PLUGIN_DATA=str(tmp_path / "data"), CLAUDE_PROJECT_DIR=str(cwd))
    r = subprocess.run([sys.executable, str(HOOK), lang], input=json.dumps(payload), cwd=cwd,
                       capture_output=True, text=True, encoding="utf-8", env=full)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


@pytest.fixture
def p(tmp_path, env):  # noqa: F811
    return Status(tmp_path, env)


def test_сессия_пункта_получает_строку_из_основной_копии_и_план(p, tmp_path):
    """Критерий поменяли в main после старта пункта: в копии worktree он старый."""
    p.item("B-1")
    p.write(p.worktree("B-1"), {"docs/roadmap/B-1/STATUS.md": "# B-1\n"})
    new = "  Готово когда: отчёт на 500 строк < 2 с,\n    пиковая память < 300 МБ."
    p.commit({"ROADMAP.md": p.read("ROADMAP.md").replace("  Готово когда: отчёт на 500 строк < 3 с.", new)},
             "[B-1] критерий изменён")
    out = brief(p.worktree("B-1"), "B-1", tmp_path, p.env)
    assert "- **B-1** Экспорт PDF — 🔨 в работе · `worktree-B-1` · сессия `B-1` · с 20.09" in out
    assert "  Мои пути: reports/**\n" + new in out, out
    assert "`docs/roadmap/B-1/STATUS.md`" in out and "не заведён" not in out
    assert "`mast-ru:managing-roadmap-items`" in out
    assert "B-2" not in out
    assert len(out) <= LIMIT


def test_без_status_md_указан_журнал_в_коммитах(p, tmp_path):
    p.item("B-2")
    out = brief(p.worktree("B-2"), "B-2", tmp_path, p.env)
    assert "`docs/roadmap/B-2/STATUS.md` не заведён" in out and "--grep='\\[B-2\\]'" in out, out


def test_диспетчер_получает_mast_status(p, tmp_path):
    p.item("B-1")
    p.agents(agent("B-1", p.worktree("B-1"), "aaaa1111"))
    out = brief(p.root, "p-dispatch", tmp_path, p.env)
    assert p.status().strip() in out, out
    assert "`mast-ru:worktree-flow`" in out


@pytest.mark.parametrize("where, title", [("root", "plain"), ("agent", "plain"), ("root", None)])
def test_без_роли_и_вне_worktree_пункта_справки_нет(p, tmp_path, where, title):
    """Worktree субагента (`agent-…`) — не пункт."""
    cwd = p.root
    if where == "agent":
        cwd = p.root / ".claude" / "worktrees" / "agent-a1b2"
        p.git("worktree", "add", "-q", str(cwd))
    assert brief(cwd, title, tmp_path, p.env) == ""


def test_worktree_пункта_без_строки_молчит(p, tmp_path):
    """Сирота: пункт влит или снят, а worktree остался — показывать нечего."""
    p.git("worktree", "add", "-q", str(p.worktree("B-9")))
    assert brief(p.worktree("B-9"), "B-9", tmp_path, p.env) == ""


def test_английский_плагин(p, tmp_path):
    p.item("B-1")
    out = brief(p.worktree("B-1"), "B-1", tmp_path, p.env, lang="en")
    assert "`mast:managing-roadmap-items`" in out and "основной копии" not in out, out


def test_длинная_сверка_обрезана_до_потолка(p, tmp_path):
    """Вопросов к человеку может накопиться сколько угодно — справка не растёт с ними."""
    rows = "".join(f"\n- **C-{n}** Пункт {n} — запланирован · — · ждёт человека: {'вопрос ' * 20}\n"
                   f"  Готово когда: {n} < 1 с.\n" for n in range(1, 21))
    p.commit({"ROADMAP.md": p.read("ROADMAP.md") + "\n## C. Много\n" + rows}, "[C-1] заведены")
    out = brief(p.root, "p-dispatch", tmp_path, p.env)
    assert len(out) <= LIMIT and out.endswith("обрезано до 1500 символов"), len(out)


def test_строка_любого_пункта_нашего_роадмапа_влезает_в_потолок(tmp_path):
    """Справка пункта читает только файлы: git и `claude` ей не нужны."""
    text = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")
    (tmp_path / "ROADMAP.md").write_text(text, encoding="utf-8")
    items = [l.split("**")[1] for l in text.splitlines() if l.startswith("- **")]
    assert items
    for item in items:
        wt = tmp_path / ".claude" / "worktrees" / item
        wt.mkdir(parents=True)
        out = brief(wt, item, tmp_path, os.environ)
        assert f"**{item}**" in out and len(out) <= LIMIT, (item, len(out))
