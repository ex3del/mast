"""Сторож подсказки перезапуска диспетчера (A-24): после `mast merge` с контекстом выше порога
хук Bash отдаёт диспетчеру «перезапусти: `/clear`» в `additionalContext`, иначе молчит.

Хук гоняется как на площадке: отдельный процесс, вход PostToolUse на stdin, транскрипт —
файл по `transcript_path`. Контекст — `usage` последнего ответа модели в транскрипте."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "hooks" / "roadmap_watch.py"
ROADMAP = "# ROADMAP\n\n## A. Раздел\n"


def answer(context, advisor=False):
    """Запись ответа модели с контекстом `context`. С советником `usage` — сумма итераций."""
    it = {"type": "message", "input_tokens": 2, "cache_creation_input_tokens": 1000,
          "cache_read_input_tokens": context - 1002}
    usage = dict(it, iterations=[it])
    if advisor:
        before = dict(it, cache_read_input_tokens=context - 21002)
        usage = {k: before[k] + it[k] for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")}
        usage["iterations"] = [before, {"type": "advisor_message", "input_tokens": context - 20000}, it]
    return {"type": "assistant", "isSidechain": False,
            "message": {"id": "m", "content": [{"type": "tool_use", "name": "Bash"}], "usage": usage}}


def hint(tmp_path, context, command="mast merge A-1", role=True, rule=None, lang="ru", records=None, tail=""):
    """Текст подсказки или None. `tail` — сырой хвост транскрипта после записей."""
    project = tmp_path / "proj"
    project.mkdir(exist_ok=True)
    (project / "ROADMAP.md").write_text(ROADMAP, encoding="utf-8")
    if rule:
        (project / ".claude/rules").mkdir(parents=True, exist_ok=True)
        (project / ".claude/rules/dispatch.md").write_text(rule, encoding="utf-8")
    transcript = tmp_path / "s.jsonl"
    transcript.write_text("".join(json.dumps(r) + "\n" for r in records or [answer(context)]) + tail,
                          encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k != "MAST_ROLE"}
    env.update({"CLAUDE_PLUGIN_DATA": str(tmp_path / "data"), "CLAUDE_PROJECT_DIR": str(project)})
    if role:
        env["MAST_ROLE"] = "dispatcher"
    payload = {"hook_event_name": "PostToolUse", "session_id": "s-1", "transcript_path": str(transcript),
               "cwd": str(project), "tool_name": "Bash", "tool_input": {"command": command},
               "tool_response": {"stdout": "A-1 влит: `aaa..bbb`", "stderr": "", "interrupted": False}}
    r = subprocess.run([sys.executable, str(HOOK), lang], input=json.dumps(payload),
                       capture_output=True, text=True, env=env, cwd=project)
    assert r.returncode == 0 and not r.stderr, r.stderr
    if not r.stdout.strip():
        return None
    out = json.loads(r.stdout)["hookSpecificOutput"]
    assert out["hookEventName"] == "PostToolUse", out
    return out["additionalContext"]


def test_выше_порога_после_вливания_подсказка(tmp_path):
    text = hint(tmp_path, 600_000)
    assert text and "`/clear`" in text and "600 тыс." in text and "500 тыс." in text, text


def test_ниже_порога_молчит(tmp_path):
    assert hint(tmp_path, 400_000) is None


def test_сессия_без_роли_диспетчера_молчит(tmp_path):
    assert hint(tmp_path, 600_000, role=False) is None


def test_не_вливание_молчит(tmp_path):
    for command in ("git status", "mast status", "echo mast merge"):
        assert hint(tmp_path, 600_000, command=command) is None, command


def test_с_советником_контекст_последней_итерации(tmp_path):
    """`usage` с советником — сумма двух итераций основной модели: 350 тыс. дали бы ~680."""
    assert hint(tmp_path, 350_000, records=[answer(350_000, advisor=True)]) is None
    assert "`/clear`" in hint(tmp_path, 600_000, records=[answer(600_000, advisor=True)])


def test_порог_из_dispatch_md(tmp_path):
    rule = "# Модели\n\nПорог перезапуска: 50 тыс. токенов\n"
    assert "50 тыс." in hint(tmp_path, 60_000, rule=rule)
    assert hint(tmp_path, 40_000, rule=rule) is None


def test_последний_ответ_в_хвосте_большого_транскрипта(tmp_path):
    """Транскрипт диспетчера — десятки МБ: хвост читается с обрезанной первой строкой, после
    ответа — результат команды и недописанная запись."""
    filler = {"type": "user", "message": {"content": "x" * 100_000}}
    records = [answer(100_000)] + [filler] * 30 + [answer(600_000), {"type": "user", "message": {"content": "ok"}}]
    assert "`/clear`" in hint(tmp_path, 0, records=records, tail='{"type": "assistant", "message": {"usage')


def test_английский_плагин(tmp_path):
    text = hint(tmp_path, 600_000, lang="en", rule="Restart threshold: 500k tokens\n")
    assert "`/clear`" in text and "600k" in text and "restart" in text.lower(), text
