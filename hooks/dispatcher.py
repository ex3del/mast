#!/usr/bin/env python3
"""Роль диспетчера держит хук, а не проза: вопрос человеку — текстом, запись — в роадмап.

SessionStart: сессия с именем `<проект>-dispatch` получает файл роли по своему
`session_id` — имя (`session_title`) приходит во вход SessionStart, а в PreToolUse его
нет. Запасной путь — `MAST_ROLE=dispatcher` в окружении сессии.

PreToolUse у диспетчера: `AskUserQuestion` — отказ (модальный вопрос держит всю очередь:
в `reinhold-dispatch` 16 из 17 ожиданий дольше 5 мин); Edit/Write в основной копии вне
файлов роадмапа — отказ. Отказ жёсткий, а не `ask`: `ask` тоже модальный, в `--bg`
отвечать некому. Запись через Bash хук не видит осознанно — список команд обходится.
"""
import json
import os
import sys
from pathlib import Path

from core import pick_language
from plugin_names import PLUGIN

# Что диспетчер правит сам — пути от корня основной копии
OWN_FILES = {("ROADMAP.md",), ("TECH_DEBT.md",)}
OWN_DIR = ("docs", "roadmap")
# Worktree — уже не основная копия: там правит субагент с `isolation: worktree`
WORKTREES = (".claude", "worktrees")

ASK = {
    "ru": "MAST: диспетчер не задаёт модальных вопросов — `AskUserQuestion` держит вливания "
          "и входящие от сессий, пока человек не ответит. Спроси обычным сообщением: факты, "
          "2–3 варианта, рекомендация; вопрос по пункту — ещё и слотом "
          "`· ждёт человека: <вопрос>` в конце его строки в `ROADMAP.md`.",
    "en": "MAST: the dispatcher doesn't ask modal questions — `AskUserQuestion` holds merges "
          "and incoming session messages until the human answers. Ask in a plain message: "
          "facts, 2–3 options, your recommendation; for a question about an item also add "
          "the slot `· waiting on human: <question>` at the end of its line in `ROADMAP.md`.",
}
EDIT = {
    "ru": "MAST: диспетчер в основной копии правит только `ROADMAP.md`, `docs/roadmap/**` и "
          "`TECH_DEBT.md`, а `{path}` — не из них. Мелочь — субагентом `Agent` с "
          "`isolation: \"worktree\"`, его ветку вливаешь сам; работа со своим критерием — "
          "пункт роадмапа, скилл `{p}:managing-roadmap-items`.",
    "en": "MAST: in the main copy the dispatcher edits only `ROADMAP.md`, `docs/roadmap/**` "
          "and `TECH_DEBT.md`, and `{path}` isn't one of them. A small fix — via an `Agent` "
          "subagent with `isolation: \"worktree\"`, you merge its branch yourself; work with "
          "its own criterion — a roadmap item, skill `{p}:managing-roadmap-items`.",
}


def role_file(session_id):
    return Path(os.environ["CLAUDE_PLUGIN_DATA"]) / f"{session_id}.role"


def remember(payload):
    """Роль следует за именем на каждом старте: переименованная сессия её теряет."""
    path = role_file(payload["session_id"])
    if (payload.get("session_title") or "").endswith("-dispatch"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    else:
        path.unlink(missing_ok=True)


def is_dispatcher(payload):
    return os.environ.get("MAST_ROLE") == "dispatcher" or role_file(payload["session_id"]).exists()


def refusal(payload, lang):
    """Причина отказа или None. Пути сравниваются после resolve: на macOS проект в
    `/tmp/...` и файл в `/private/tmp/...` — один и тот же каталог."""
    if payload["tool_name"] == "AskUserQuestion":
        return ASK[lang]
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload["cwd"]).resolve()
    path = (Path(payload["cwd"]) / payload["tool_input"]["file_path"]).resolve()
    try:
        rel = path.relative_to(project).parts
    except ValueError:
        return None  # вне основной копии: память, scratchpad, другой проект
    if rel in OWN_FILES or rel[:2] in (OWN_DIR, WORKTREES):
        return None
    return EDIT[lang].format(path=Path(*rel).as_posix(), p=PLUGIN[lang])


def main():
    lang = pick_language(sys.argv[1:])
    payload = json.load(sys.stdin)
    if payload["hook_event_name"] == "SessionStart":
        remember(payload)
    elif is_dispatcher(payload):
        reason = refusal(payload, lang)
        if reason:
            print(json.dumps({"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
