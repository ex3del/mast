"""Сторож роли диспетчера: вопрос человеку — текстом, запись в основной копии — только
в файлы роадмапа. Замер в docs/research/2026-09-23-dispatcher-load.md: 16 из 17 ожиданий
очереди дольше 5 мин — модальный `AskUserQuestion`; 21% вызовов диспетчера mast — правки
кода и README. Хук гоняется как на площадке: отдельный процесс, JSON на stdin."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "hooks" / "dispatcher.py"
SID = "11111111-2222-3333-4444-555555555555"


def run(payload, tmp_path, lang="ru", **env):
    full = {k: v for k, v in os.environ.items() if k != "MAST_ROLE"}
    full.update({"CLAUDE_PLUGIN_DATA": str(tmp_path / "data"),
                 "CLAUDE_PROJECT_DIR": str(tmp_path / "proj"), **env})
    r = subprocess.run([sys.executable, str(HOOK), lang], input=json.dumps(payload),
                       capture_output=True, text=True, env=full)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)["hookSpecificOutput"] if r.stdout.strip() else None


def start(tmp_path, title):
    run({"hook_event_name": "SessionStart", "source": "startup", "session_id": SID,
         "session_title": title, "cwd": str(tmp_path / "proj")}, tmp_path)


def tool(tmp_path, name, file_path=None, lang="ru", **env):
    tool_input = {"questions": []} if file_path is None else {"file_path": str(file_path)}
    return run({"hook_event_name": "PreToolUse", "session_id": SID, "tool_name": name,
                "tool_input": tool_input, "cwd": str(tmp_path / "proj")}, tmp_path, lang, **env)


@pytest.fixture
def proj(tmp_path):
    (tmp_path / "proj").mkdir()
    return tmp_path / "proj"


def four_calls(tmp_path, proj):
    """Четыре вызова из «Готово когда» пункта A-13."""
    return {
        "AskUserQuestion": tool(tmp_path, "AskUserQuestion"),
        "Edit README.md": tool(tmp_path, "Edit", proj / "README.md"),
        "Edit ROADMAP.md": tool(tmp_path, "Edit", proj / "ROADMAP.md"),
        "субагент в worktree": tool(tmp_path, "Edit", proj / ".claude/worktrees/agent-a1/README.md"),
    }


def test_диспетчер_четыре_вызова(tmp_path, proj):
    start(tmp_path, "mast-dispatch")
    got = four_calls(tmp_path, proj)
    assert got["AskUserQuestion"]["permissionDecision"] == "deny"
    assert "AskUserQuestion" in got["AskUserQuestion"]["permissionDecisionReason"]
    assert got["Edit README.md"]["permissionDecision"] == "deny"
    assert "`README.md`" in got["Edit README.md"]["permissionDecisionReason"]
    assert got["Edit ROADMAP.md"] is None
    assert got["субагент в worktree"] is None


def test_без_роли_ни_одного_отказа(tmp_path, proj):
    start(tmp_path, "A-13")
    assert set(four_calls(tmp_path, proj).values()) == {None}


def test_отказ_жёсткий_а_не_ask(tmp_path, proj):
    """Решение человека: `ask` модальный, как сам `AskUserQuestion`, в `--bg` отвечать
    некому, в Codex `ask` считается упавшим хуком — вызов проходит."""
    start(tmp_path, "mast-dispatch")
    for decision in four_calls(tmp_path, proj).values():
        assert decision is None or decision["permissionDecision"] == "deny"


@pytest.mark.parametrize("rel", ["ROADMAP.md", "TECH_DEBT.md", "docs/roadmap/DONE.md",
                                 "docs/roadmap/inbox/23.09-x.md", "docs/roadmap/A-1/STATUS.md"])
def test_файлы_роадмапа_диспетчер_правит(tmp_path, proj, rel):
    start(tmp_path, "mast-dispatch")
    assert tool(tmp_path, "Write", proj / rel) is None


@pytest.mark.parametrize("rel", ["README.md", "hooks/core.py", ".claude/rules/db.md",
                                 "docs/adr/A-1-x.md", "CLAUDE.md"])
def test_остальное_в_основной_копии_отклонено(tmp_path, proj, rel):
    start(tmp_path, "mast-dispatch")
    assert tool(tmp_path, "Write", proj / rel)["permissionDecision"] == "deny"


def test_вне_основной_копии_не_касается(tmp_path, proj):
    """Память, scratchpad, другой проект — не основная копия."""
    start(tmp_path, "mast-dispatch")
    assert tool(tmp_path, "Write", tmp_path / "memory" / "note.md") is None


def test_относительный_путь_считается_от_cwd(tmp_path, proj):
    start(tmp_path, "mast-dispatch")
    assert tool(tmp_path, "Edit", "README.md")["permissionDecision"] == "deny"
    assert tool(tmp_path, "Edit", "ROADMAP.md") is None


def test_проект_через_символьную_ссылку(tmp_path, proj):
    """На macOS `/tmp` — ссылка на `/private/tmp`: проект и файл приходят в разных написаниях."""
    link = tmp_path / "link"
    link.symlink_to(proj, target_is_directory=True)
    start(tmp_path, "mast-dispatch")
    got = tool(tmp_path, "Edit", proj / "README.md", CLAUDE_PROJECT_DIR=str(link))
    assert got["permissionDecision"] == "deny"


def test_роль_следует_за_именем(tmp_path, proj):
    start(tmp_path, "mast-dispatch")
    assert (tmp_path / "data" / f"{SID}.role").is_file()
    start(tmp_path, "mast")
    assert not (tmp_path / "data" / f"{SID}.role").exists()
    assert tool(tmp_path, "AskUserQuestion") is None


def test_имя_без_суффикса_не_диспетчер(tmp_path, proj):
    for title in ("dispatch", "mast-dispatcher", None):
        start(tmp_path, title)
        assert tool(tmp_path, "AskUserQuestion") is None, title


def test_запасной_путь_mast_role(tmp_path, proj):
    got = tool(tmp_path, "AskUserQuestion", MAST_ROLE="dispatcher")
    assert got["permissionDecision"] == "deny"


@pytest.mark.parametrize("lang, skill", [("ru", "mast-ru:managing-roadmap-items"),
                                         ("en", "mast:managing-roadmap-items")])
def test_причина_на_языке_своего_плагина(tmp_path, proj, lang, skill):
    start(tmp_path, "mast-dispatch")
    reason = tool(tmp_path, "Edit", proj / "README.md", lang=lang)["permissionDecisionReason"]
    assert f"`{skill}`" in reason
    assert ("основной копии" in reason) == (lang == "ru")
