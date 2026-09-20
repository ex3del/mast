"""Сторож `hooks/hooks.json`: без него опечатка в матчере или в путях
не уронит ни один тест, а ядро молча перестанет вкладываться в сессии."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOKS_JSON = ROOT / "hooks" / "hooks.json"


def load():
    return json.loads(HOOKS_JSON.read_text(encoding="utf-8"))


def all_hook_entries(data):
    """Каждый объект хука (`{"type": "command", ...}`) из всех событий."""
    return [h for entries in data["hooks"].values() for entry in entries for h in entry["hooks"]]


def test_hooks_json_валиден():
    load()


def test_session_start_покрывает_все_события():
    data = load()
    events = set()
    for entry in data["hooks"]["SessionStart"]:
        events |= set(entry["matcher"].split("|"))
    assert {"startup", "resume", "clear", "compact"} <= events


def test_post_tool_use_ловит_edit_и_write_по_roadmap():
    data = load()
    ifs = [h.get("if", "") for h in all_hook_entries(data) if "if" in h]
    assert any("Edit" in i and "ROADMAP.md" in i for i in ifs), ifs
    assert any("Write" in i and "ROADMAP.md" in i for i in ifs), ifs


def test_все_пути_в_аргументах_через_claude_plugin_root_и_существуют():
    data = load()
    args = [a for h in all_hook_entries(data) for a in h.get("args", [])]
    assert args, "в hooks.json не нашлось ни одного args"
    for arg in args:
        assert arg.startswith("${CLAUDE_PLUGIN_ROOT}/"), arg
        rel = arg[len("${CLAUDE_PLUGIN_ROOT}/"):]
        assert (ROOT / rel).is_file(), f"{arg}: файла {ROOT / rel} нет"


def test_нет_home_и_claude_в_аргументах():
    raw = HOOKS_JSON.read_text(encoding="utf-8")
    assert "$HOME" not in raw
    assert "~/.claude" not in raw
