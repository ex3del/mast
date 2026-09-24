"""Сторож защит сессий (A-21): три правила, которые держались прозой.

Файлы роадмапа правит только основная копия, планы superpowers пишутся в
`docs/roadmap/<X-N>/`, ветку пункта вливает только `mast merge`. Хуки гоняются как на
площадке: отдельный процесс, JSON на stdin, во временном git-проекте с worktree."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
EDIT_HOOK = ROOT / "hooks" / "dispatcher.py"
BASH_HOOK = ROOT / "hooks" / "roadmap_watch.py"
ROADMAP = """# ROADMAP

## A. Раздел

- **A-1** Пункт — 🔨 в работе · `worktree-A-1` · сессия `A-1` · с 24.09
  Мои пути: src/**
  Готово когда: 1 из 1.
"""
LEDGER = ["ROADMAP.md", "docs/roadmap/DONE.md", "TECH_DEBT.md"]


def git(cwd, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd,
                   check=True, capture_output=True)


@pytest.fixture
def proj(tmp_path):
    """Основная копия с роадмапом, worktree пункта A-1 и ветка субагента диспетчера."""
    main = tmp_path / "proj"
    for rel, text in {"ROADMAP.md": ROADMAP, "TECH_DEBT.md": "# TECH_DEBT\n",
                      "docs/roadmap/DONE.md": "# DONE\n", "src/x.py": "x = 1\n"}.items():
        (main / rel).parent.mkdir(parents=True, exist_ok=True)
        (main / rel).write_text(text, encoding="utf-8")
    git(main, "init", "-q", "-b", "main")
    git(main, "add", ".")
    git(main, "commit", "-qm", "init")
    git(main, "branch", "worktree-agent-a1")
    git(main, "worktree", "add", "-q", "-b", "worktree-A-1", ".claude/worktrees/A-1")
    return main


def hook(script, payload, tmp_path, lang="ru", project=None):
    env = {k: v for k, v in os.environ.items() if k != "MAST_ROLE"}
    env.update({"CLAUDE_PLUGIN_DATA": str(tmp_path / "data"),
                "CLAUDE_PROJECT_DIR": str(project or payload["cwd"])})
    return subprocess.run([sys.executable, str(script), lang], input=json.dumps(payload),
                          capture_output=True, text=True, env=env, cwd=payload["cwd"])


def edit(tmp_path, tool, path, cwd, lang="ru"):
    """Причина отказа Edit/Write или None."""
    key = "content" if tool == "Write" else "old_string"
    r = hook(EDIT_HOOK, {"hook_event_name": "PreToolUse", "session_id": "s-1", "tool_name": tool,
                         "tool_input": {"file_path": str(path), key: "x"}, "cwd": str(cwd)},
             tmp_path, lang)
    assert r.returncode == 0, r.stderr
    if not r.stdout.strip():
        return None
    out = json.loads(r.stdout)["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny", out
    return out["permissionDecisionReason"]


def bash(tmp_path, command, cwd, lang="ru"):
    """Причина отказа команды или None. Отказ — код 2 и причина в stderr, как у линта."""
    r = hook(BASH_HOOK, {"hook_event_name": "PreToolUse", "session_id": "s-1", "tool_name": "Bash",
                         "tool_input": {"command": command}, "cwd": str(cwd)}, tmp_path, lang)
    assert r.returncode in (0, 2), r.stderr
    return r.stderr if r.returncode == 2 else None


# Файлы роадмапа из worktree

@pytest.mark.parametrize("tool", ["Edit", "Write"])
@pytest.mark.parametrize("rel", LEDGER)
def test_файлы_роадмапа_из_worktree_отказ(tmp_path, proj, tool, rel):
    wt = proj / ".claude/worktrees/A-1"
    reason = edit(tmp_path, tool, wt / rel, wt)
    assert reason and f"`{rel}`" in reason and "SendMessage" in reason, reason


def test_относительный_путь_из_worktree_тоже_отказ(tmp_path, proj):
    wt = proj / ".claude/worktrees/A-1"
    assert edit(tmp_path, "Edit", "../ROADMAP.md", wt / "src")
    assert edit(tmp_path, "Edit", "ROADMAP.md", wt / "src") is None  # это src/ROADMAP.md


@pytest.mark.parametrize("rel", ["docs/roadmap/A-1/STATUS.md", "docs/roadmap/inbox/24.09-x.md",
                                 "src/x.py", "docs/ROADMAP.md", "README.md"])
def test_прочие_файлы_worktree_проходят(tmp_path, proj, rel):
    wt = proj / ".claude/worktrees/A-1"
    assert edit(tmp_path, "Edit", wt / rel, wt) is None


@pytest.mark.parametrize("rel", LEDGER)
def test_основная_копия_правит_роадмап(tmp_path, proj, rel):
    assert edit(tmp_path, "Edit", proj / rel, proj) is None


def test_диспетчеру_тоже_нельзя_в_роадмап_worktree(tmp_path, proj):
    """Защита стоит до проверки роли: субагент диспетчера в worktree правит код, а не роадмап."""
    hook(EDIT_HOOK, {"hook_event_name": "SessionStart", "source": "startup", "session_id": "s-1",
                     "session_title": "proj-dispatch", "cwd": str(proj)}, tmp_path)
    wt = proj / ".claude/worktrees/agent-a1"
    assert edit(tmp_path, "Edit", wt / "ROADMAP.md", proj)
    assert edit(tmp_path, "Edit", wt / "src/x.py", proj) is None


def test_коммит_файлов_роадмапа_из_worktree_отказ(tmp_path, proj):
    wt = proj / ".claude/worktrees/A-1"
    (wt / "ROADMAP.md").write_text(ROADMAP + "\n", encoding="utf-8")
    git(wt, "add", "ROADMAP.md")
    reason = bash(tmp_path, "git commit -m '[A-1] x'", wt)
    assert reason and "ROADMAP.md" in reason and "git restore" in reason, reason


def test_коммит_после_add_в_той_же_команде_отказ(tmp_path, proj):
    """PreToolUse видит состояние до команды: `git add … && git commit` — файл ещё не в индексе."""
    wt = proj / ".claude/worktrees/A-1"
    (wt / "TECH_DEBT.md").write_text("# TECH_DEBT\n\n- долг\n", encoding="utf-8")
    assert bash(tmp_path, "git add TECH_DEBT.md && git commit -m '[A-1] x'", wt / "src")


def test_коммит_прочих_файлов_из_worktree_проходит(tmp_path, proj):
    wt = proj / ".claude/worktrees/A-1"
    (wt / "src/x.py").write_text("x = 2\n", encoding="utf-8")
    git(wt, "add", "src/x.py")
    assert bash(tmp_path, "git commit -m '[A-1] x'", wt) is None


def test_коммит_роадмапа_в_основной_копии_проходит(tmp_path, proj):
    (proj / "ROADMAP.md").write_text(ROADMAP + "\n", encoding="utf-8")
    git(proj, "add", "ROADMAP.md")
    assert bash(tmp_path, "git commit -m '[A-1] взят'", proj) is None


# Планы superpowers

def test_план_superpowers_в_worktree_отказ_с_путём_пункта(tmp_path, proj):
    wt = proj / ".claude/worktrees/A-1"
    reason = edit(tmp_path, "Write", wt / "docs/superpowers/plans/2026-09-24-x.md", wt)
    assert reason and "`docs/roadmap/A-1/STATUS.md`" in reason, reason


def test_спека_superpowers_в_основной_копии_отказ(tmp_path, proj):
    reason = edit(tmp_path, "Write", proj / "docs/superpowers/specs/2026-09-24-x.md", proj)
    assert reason and "`docs/roadmap/<X-N>/" in reason, reason


def test_superpowers_без_роадмапа_проходит(tmp_path):
    bare = tmp_path / "bare"
    bare.mkdir()
    assert edit(tmp_path, "Write", bare / "docs/superpowers/plans/2026-09-24-x.md", bare) is None


# Вливание ветки пункта

@pytest.mark.parametrize("command", ["git merge worktree-A-1", "git merge --no-ff -m 'x' worktree-A-1",
                                     "cd /tmp && git -C proj merge worktree-A-1",
                                     "git fetch && git merge origin/worktree-A-1"])
def test_git_merge_ветки_пункта_отказ(tmp_path, proj, command):
    reason = bash(tmp_path, command, proj)
    assert reason and "`mast merge A-1`" in reason, reason


@pytest.mark.parametrize("command", ["git merge --ff-only worktree-agent-a1",
                                     "git merge-base --is-ancestor HEAD worktree-A-1",
                                     "git merge --abort",
                                     "git log --oneline main..worktree-A-1",
                                     "git commit --allow-empty -m 'не git merge worktree-A-1, а mast merge'",
                                     "git commit --allow-empty -F - <<'EOF'\nвлил:\ngit merge worktree-A-1\nEOF"])
def test_прочие_git_команды_проходят(tmp_path, proj, command):
    assert bash(tmp_path, command, proj) is None


@pytest.mark.parametrize("command", ["git status", "git merge-base --is-ancestor HEAD worktree-A-1",
                                     "git log --merges -1"])
def test_прочие_git_команды_на_быстром_пути(tmp_path, proj, command):
    """Медленный путь — импорт линта и защит — стоит ~8 мс на каждую git-команду (замер A-21)."""
    payload = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash",
                          "tool_input": {"command": command}, "cwd": str(proj)})
    r = subprocess.run([sys.executable, "-X", "importtime", str(BASH_HOOK), "ru"], input=payload,
                       capture_output=True, text=True, cwd=proj)
    assert r.returncode == 0 and "| json" not in r.stderr and "dispatcher" not in r.stderr


def test_английский_плагин_отказывает_по_английски(tmp_path, proj):
    reason = bash(tmp_path, "git merge worktree-A-1", proj, lang="en")
    assert reason and "`mast merge A-1`" in reason and "main copy" in reason, reason
    wt = proj / ".claude/worktrees/A-1"
    assert "main copy" in edit(tmp_path, "Edit", wt / "ROADMAP.md", wt, lang="en")
