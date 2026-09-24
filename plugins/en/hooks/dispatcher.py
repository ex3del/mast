#!/usr/bin/env python3
# Сгенерировано tools/sync_plugins.py из hooks/dispatcher.py — правь там, здесь затрётся
"""Роль диспетчера держит хук, а не проза: вопрос человеку — текстом, запись — в роадмап.

SessionStart: сессия с именем `<проект>-dispatch` получает файл роли по своему
`session_id` — имя (`session_title`) приходит во вход SessionStart, а в PreToolUse его
нет. Запасной путь — `MAST_ROLE=dispatcher` в окружении сессии.

PreToolUse у диспетчера: `AskUserQuestion` — отказ (модальный вопрос держит всю очередь:
в `reinhold-dispatch` 16 из 17 ожиданий дольше 5 мин); Edit/Write в основной копии вне
файлов роадмапа — отказ. Отказ жёсткий, а не `ask`: `ask` тоже модальный, в `--bg`
отвечать некому. Запись через Bash хук не видит осознанно — список команд обходится.

SessionStart печатает справку, ≤ 1500 символов: ядро одно на всех, а роль и пункт после
`/compact` модель не вспоминает сама. Диспетчеру — вывод `mast status`, сессии в
`.claude/worktrees/X-N` — строка её пункта из `ROADMAP.md` основной копии (в копии
worktree критерий мог устареть) и путь к `STATUS.md`. Остальным — ничего. Справка — на
любом старте, не только после `compact`: `session_title` приходит и на `clear`.
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


# Справка на старте сессии; потолок — чтобы сверка с десятками вопросов не съела контекст
LIMIT = 1500
ROLE = {
    "ru": "MAST: эта сессия — диспетчер роадмапа, роль — скиллы `{p}:worktree-flow` и "
          "`{p}:managing-roadmap-items`. `mast status` на старте сессии:\n{s}",
    "en": "MAST: this session is the roadmap dispatcher, the role is in skills `{p}:worktree-flow` "
          "and `{p}:managing-roadmap-items`. `mast status` at session start:\n{s}",
}
ITEM = {
    "ru": "MAST: эта сессия ведёт пункт {i} по скиллу `{p}:managing-roadmap-items`. Его строка — "
          "из `{r}` основной копии, копия в worktree могла отстать:\n{l}\n{plan}",
    "en": "MAST: this session drives item {i} per skill `{p}:managing-roadmap-items`. Its line is "
          "from the main copy's `{r}`, the worktree's copy may lag behind:\n{l}\n{plan}",
}
PLAN = {"ru": "План и журнал — `{s}`.", "en": "Plan and log — `{s}`."}
NO_PLAN = {"ru": "`{s}` не заведён — ход работы в `git log --grep='\\[{i}\\]'`.",
           "en": "`{s}` isn't created — the work so far is in `git log --grep='\\[{i}\\]'`."}
CUT = {"ru": "\n… обрезано до {n} символов", "en": "\n… cut to {n} characters"}


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


def item_lines(body):
    """Шапка, «Мои пути» и «Готово когда» с продолжением — дословно: описание пункта
    длинное и после `/compact` не нужно, а критерий пересказом не заменяется."""
    from mast import PATHS
    from roadmap_lint import CRIT_HEADER, FIELD
    lines, crit = body.splitlines(), False
    keep = lines[:1]
    for line in lines[1:]:
        crit = bool(CRIT_HEADER.match(line)) or crit and not FIELD.match(line)
        if crit or PATHS.match(line):
            keep.append(line)
    return "\n".join(keep)


def brief(payload, lang):
    """Справка сессии или пустая строка. Импорт ленивый: хук стреляет на каждый
    Edit/Write, а `mast` с линтом нужны только на старте."""
    import mast
    from roadmap_lint import parse
    p, cwd = PLUGIN[lang], Path(payload["cwd"]).resolve()
    if is_dispatcher(payload):
        mast.LANG = lang
        os.chdir(cwd)
        try:
            text = ROLE[lang].format(p=p, s=mast.status())
        except mast.Refusal:
            return ""  # не git или нет ROADMAP.md — сверять нечего
    else:
        if cwd.parts[-3:-1] != WORKTREES or not mast.ID.match(cwd.name):
            return ""
        item, roadmap = cwd.name, cwd.parents[2] / "ROADMAP.md"
        row = parse(mast.read(roadmap))[0].get(item)
        if not row:
            return ""
        plan = f"docs/roadmap/{item}/STATUS.md"
        text = ITEM[lang].format(i=item, p=p, r=roadmap, l=item_lines(row["body"]),
                                 plan=(PLAN if (cwd / plan).is_file() else NO_PLAN)[lang].format(s=plan, i=item))
    cut = CUT[lang].format(n=LIMIT)
    return text if len(text) <= LIMIT else text[:LIMIT - len(cut)] + cut


def main():
    lang = pick_language(sys.argv[1:])
    payload = json.load(sys.stdin)
    if payload["hook_event_name"] == "SessionStart":
        remember(payload)
        text = brief(payload, lang)
        if text:
            # Байтами: вывод — UTF-8 при любой кодировке окружения
            sys.stdout.buffer.write(text.encode("utf-8") + b"\n")
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
