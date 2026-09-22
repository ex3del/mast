"""Сторож разводки хуков в обоих плагинах: без него опечатка в матчере или в
путях не уронит ни один тест, а ядро молча перестанет вкладываться в сессии."""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PLUGINS = {"en": ROOT / "plugins" / "en", "ru": ROOT / "plugins" / "ru"}
LANGS = sorted(PLUGINS)


def load(lang):
    return json.loads((PLUGINS[lang] / "hooks" / "hooks.json").read_text(encoding="utf-8"))


def all_hook_entries(data):
    """Каждый объект хука (`{"type": "command", ...}`) из всех событий."""
    return [h for entries in data["hooks"].values() for entry in entries for h in entry["hooks"]]


@pytest.mark.parametrize("lang", LANGS)
def test_hooks_json_валиден(lang):
    data = load(lang)
    assert set(data["hooks"]) == {"SessionStart", "PostToolUse"}
    assert all_hook_entries(data), "ни одного хука не зарегистрировано"


@pytest.mark.parametrize("lang", LANGS)
def test_session_start_покрывает_все_события(lang):
    events = set()
    for entry in load(lang)["hooks"]["SessionStart"]:
        events |= set(entry["matcher"].split("|"))
    assert {"startup", "resume", "clear", "compact"} <= events


@pytest.mark.parametrize("lang", LANGS)
def test_ядру_передан_язык_своего_плагина(lang):
    """Код хуков общий на оба плагина, поэтому язык приходит аргументом из разводки."""
    start = [h for h in all_hook_entries(load(lang)) if "core.py" in " ".join(h.get("args", []))]
    assert start, f"{lang}: ядро не подключено к SessionStart"
    for h in start:
        assert h["args"][-1] == lang, f"{lang}: языком передано {h['args'][-1]}"


@pytest.mark.parametrize("lang", LANGS)
def test_настройка_ядро_везде_доезжает_до_хука(lang):
    """`${user_config.*}` подставляется только в `env` exec-формы — не в командную
    строку. Потеряется подстановка — настройка молча перестанет работать."""
    start = [h for h in all_hook_entries(load(lang)) if "core.py" in " ".join(h.get("args", []))]
    for h in start:
        assert h.get("env", {}).get("MAST_ALWAYS_CORE") == "${user_config.always_core}", h


@pytest.mark.parametrize("lang", LANGS)
def test_линту_передан_язык_своего_плагина(lang):
    """Иначе имя скилла в жалобе линта угадывается по языку роадмапа: русский файл
    под английским плагином отсылал бы к скиллу, которого у пользователя нет."""
    lint = [h for h in all_hook_entries(load(lang)) if "roadmap_lint.py" in " ".join(h.get("args", []))]
    assert lint, f"{lang}: линт не подключён к PostToolUse"
    for h in lint:
        assert h["args"][-1] == lang, f"{lang}: языком передано {h['args'][-1]}"


@pytest.mark.parametrize("lang", LANGS)
def test_post_tool_use_ловит_роадмап_и_архив(lang):
    ifs = [h.get("if", "") for h in all_hook_entries(load(lang)) if "if" in h]
    for tool in ("Edit", "Write"):
        assert any(tool in i and "ROADMAP.md" in i for i in ifs), ifs
        assert any(tool in i and "DONE.md" in i for i in ifs), ifs


@pytest.mark.parametrize("lang", LANGS)
def test_все_пути_в_аргументах_через_claude_plugin_root_и_существуют(lang):
    args = [a for h in all_hook_entries(load(lang)) for a in h.get("args", [])]
    paths = [a for a in args if "/" in a]
    assert paths, "в hooks.json не нашлось ни одного пути"
    for arg in paths:
        assert arg.startswith("${CLAUDE_PLUGIN_ROOT}/"), arg
        rel = arg[len("${CLAUDE_PLUGIN_ROOT}/"):]
        target = (PLUGINS[lang] / rel).resolve()
        assert target.is_file(), f"{arg}: файла {target} нет"
        # Внутри плагина, а не в корне репозитория: в кэш едет только он сам
        assert target.parent == PLUGINS[lang] / "hooks", f"{arg}: файл вне каталога плагина"


@pytest.mark.parametrize("lang", LANGS)
def test_нет_home_и_claude_в_аргументах(lang):
    raw = (PLUGINS[lang] / "hooks" / "hooks.json").read_text(encoding="utf-8")
    assert "$HOME" not in raw
    assert "~/.claude" not in raw
