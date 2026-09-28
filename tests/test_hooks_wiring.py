"""Сторож разводки хуков в обоих плагинах: без него опечатка в матчере или в
путях не уронит ни один тест, а ядро молча перестанет вкладываться в сессии."""
import json
import sys
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
    assert set(data["hooks"]) == {"SessionStart", "PreToolUse", "PostToolUse"}
    assert all_hook_entries(data), "ни одного хука не зарегистрировано"


@pytest.mark.parametrize("lang", LANGS)
def test_hooks_json_без_повторных_ключей(lang):
    """Два пункта добавили по ключу `PreToolUse`, git склеил их текстом без
    конфликта, а JSON берёт последний — группа одного из пунктов пропала молча
    (rebase A-12 на A-13)."""
    def no_dups(pairs):
        keys = [k for k, _ in pairs]
        assert len(keys) == len(set(keys)), f"{lang}: повторный ключ в {keys}"
        return dict(pairs)

    json.loads((PLUGINS[lang] / "hooks" / "hooks.json").read_text(encoding="utf-8"),
               object_pairs_hook=no_dups)


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
    lint = [h for h in all_hook_entries(load(lang)) if "hooks/roadmap_" in " ".join(h.get("args", []))]
    assert lint, f"{lang}: линт не подключён к PostToolUse"
    for h in lint:
        assert h["args"][-1] == lang, f"{lang}: языком передано {h['args'][-1]}"


@pytest.mark.parametrize("lang", LANGS)
def test_хук_диспетчера_видит_старт_и_его_вызовы(lang):
    """Роль узнаётся на старте, а запреты стоят на PreToolUse: потеряется одно — хук
    молча перестанет отказывать, и диспетчер снова повесит очередь на модальном вопросе."""
    need = {"SessionStart": {"startup", "resume", "clear", "compact"},
            "PreToolUse": {"AskUserQuestion", "Edit", "Write"}}
    for event, matchers in need.items():
        found = [(e["matcher"], h) for e in load(lang)["hooks"][event] for h in e["hooks"]
                 if "dispatcher.py" in " ".join(h.get("args", []))]
        assert found, f"{lang}: dispatcher.py не подключён к {event}"
        assert matchers <= {m for matcher, _ in found for m in matcher.split("|")}, event
        assert all(h["args"][-1] == lang for _, h in found), f"{lang}: чужой язык в {event}"


@pytest.mark.parametrize("lang", LANGS)
def test_post_tool_use_ловит_роадмап_и_архив(lang):
    ifs = [h.get("if", "") for h in all_hook_entries(load(lang)) if "if" in h]
    for tool in ("Edit", "Write"):
        assert any(tool in i and "ROADMAP.md" in i for i in ifs), ifs
        assert any(tool in i and "DONE.md" in i for i in ifs), ifs


def shell_hooks(lang, event):
    """Хуки линта на вызовы оболочки: Bash, а на Windows без Git Bash — PowerShell."""
    return [h for entry in load(lang)["hooks"].get(event, []) for h in entry["hooks"]
            if {"Bash", "PowerShell"} <= set(entry["matcher"].split("|"))
            and "roadmap_watch.py" in " ".join(h.get("args", []))]


@pytest.mark.parametrize("lang", LANGS)
def test_post_tool_use_ловит_правку_через_оболочку(lang):
    """Без `if`: команда, переписавшая роадмап, может быть любой — `sed -i`,
    `perl -i`, скрипт. Что роадмап изменён, хук узнаёт по самому файлу."""
    hooks = shell_hooks(lang, "PostToolUse")
    assert hooks and all("if" not in h for h in hooks), hooks


@pytest.mark.parametrize("lang", LANGS)
def test_pre_tool_use_проверяет_коммит(lang):
    """`git *`, а не `git commit *`: шаблон длиннее имени команды площадка
    зовёт на любой команде с `$()` или `$VAR` — это 30% вызовов Bash против 21%
    у всех git-команд (замер A-12), и `git -C <путь> commit` он не ловит."""
    assert [h.get("if") for h in shell_hooks(lang, "PreToolUse")][:2] == ["Bash(git *)", "PowerShell(git *)"]


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


@pytest.mark.parametrize("lang", LANGS)
def test_прод_фильтр_на_каждое_слово(lang):
    """Хук прод-команд зовётся только фильтром `if` на слова `prod.FILTER`: без `if` он
    стрелял бы на каждый Bash у всех пользователей, а пропущенное слово — дыра в отказе."""
    sys.path.insert(0, str(ROOT / "hooks"))
    import prod
    pre = [h for entry in load(lang)["hooks"]["PreToolUse"] if "Bash" in entry["matcher"] for h in entry["hooks"]]
    assert all(h.get("if") for h in pre), f"{lang}: обработчик Bash без if стреляет на каждую команду"
    watch = {h["if"] for h in pre if h["args"][0].endswith("/hooks/roadmap_watch.py")}
    for tool in ("Bash", "PowerShell"):
        for word in prod.FILTER:
            rule = f"{tool}({word})" if word.endswith("*") else f"{tool}({word} *)"
            assert rule in watch, f"{lang}: нет обработчика {rule}"
