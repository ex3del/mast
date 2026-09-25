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

PreToolUse у любой сессии — защиты, которые держались прозой (A-21): файлы роадмапа в
worktree, Write в `docs/superpowers/` в проекте с `ROADMAP.md`; в Bash — коммит этих
файлов из worktree и `git merge` ветки пункта (`shell_refusal`, зовёт `roadmap_watch.py`).
Здесь, а не отдельным хуком: каждый хук — старт python3, ~10 мс, а Edit/Write уже ~19 мс
при потолке 20. Место в пути определяется по сегментам `.claude/worktrees/<имя>/`, а не
по `CLAUDE_PROJECT_DIR`: чему он равен у сессии в worktree, зависит от способа старта.

SessionStart печатает справку, ≤ 1500 символов: ядро одно на всех, а роль и пункт после
`/compact` модель не вспоминает сама. Диспетчеру — вывод `mast status`, сессии в
`.claude/worktrees/X-N` — строка её пункта из `ROADMAP.md` основной копии (в копии
worktree критерий мог устареть) и путь к `STATUS.md`. Остальным — ничего. Справка — на
любом старте, не только после `compact`: `session_title` приходит и на `clear`.
"""
import json
import os
import re
import sys
from pathlib import Path

from core import pick_language
from plugin_names import PLUGIN

# Что диспетчер правит сам — пути от корня основной копии
OWN_FILES = {("ROADMAP.md",), ("TECH_DEBT.md",)}
OWN_DIR = ("docs", "roadmap")
# Worktree — уже не основная копия: там правит субагент с `isolation: worktree`
WORKTREES = (".claude", "worktrees")
# Файлы роадмапа от корня копии: в worktree их не правит никто
LEDGER = {("ROADMAP.md",), ("TECH_DEBT.md",), ("docs", "roadmap", "DONE.md")}
SUPERPOWERS = ("docs", "superpowers")
# Шаблоны — строками: `re` компилирует их при первом вызове, а не на каждом Edit/Write (0,2 мс)
ID = r"[A-Z]-\d+"
# `git <подкоманда>`: глобальные опции (`-C <путь>`, `-c k=v`, `--no-pager`) пропускаются
GIT = r"(?<![\w-])git(?:\s+(?:-[Cc]\s+\S+|--?[\w.-]+(?:=\S+)?))*\s+{}(?=\s|$)([^;&|\n)]*)"
HEREDOC = r"(?ms)<<-?\s*(['\"]?)(\w+)\1([^\n]*)\n.*?^[ \t]*\2[ \t]*$"
QUOTED = r"'[^']*'|\"(?:\\.|[^\"\\])*\""
ITEM_BRANCH = r"(?:^|[\s/])worktree-([A-Z]-\d+)(?![\w-])"

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
LEDGER_EDIT = {
    "ru": "MAST: `{rel}` правит только основная копия, а эта правка — в worktree `{w}`: в ветке "
          "она даст конфликт при rebase, и `mast merge` ветку не вольёт. Строку пункта, долг, "
          "находку — сообщением диспетчеру (`SendMessage` сессии `<проект>-dispatch`), тезис и "
          "долг для архива — в тело последнего коммита; скилл `{p}:managing-roadmap-items`.",
    "en": "MAST: only the main copy edits `{rel}`, and this edit is in worktree `{w}`: on the "
          "branch it conflicts at rebase, and `mast merge` won't merge the branch. The item "
          "line, debt, a finding — as a message to the dispatcher (`SendMessage` to the "
          "`<project>-dispatch` session), the thesis and debt for the archive — in the body of "
          "the last commit; skill `{p}:managing-roadmap-items`.",
}
LEDGER_COMMIT = {
    "ru": "MAST: коммит из worktree `{w}` несёт {f} — их правит только основная копия, и "
          "`mast merge` такую ветку не вольёт. Верни файлы: `git restore --staged --worktree "
          "-- {c}`; запись для них — сообщением диспетчеру или в тело последнего коммита.",
    "en": "MAST: the commit from worktree `{w}` carries {f} — only the main copy edits them, "
          "and `mast merge` won't merge such a branch. Restore them: `git restore --staged "
          "--worktree -- {c}`; their entries go in a message to the dispatcher or in the body "
          "of the last commit.",
}
PLANS = {
    "ru": "MAST: в проекте с `ROADMAP.md` планы и спеки superpowers не пишутся в "
          "`docs/superpowers/`: план пункта — `docs/roadmap/{i}/STATUS.md`, спека — рядом, в "
          "`docs/roadmap/{i}/`. Запиши туда.",
    "en": "MAST: in a project with `ROADMAP.md` superpowers plans and specs don't go to "
          "`docs/superpowers/`: the item plan is `docs/roadmap/{i}/STATUS.md`, a spec sits "
          "next to it in `docs/roadmap/{i}/`. Write it there.",
}
MERGE = {
    "ru": "MAST: ветку пункта вливает `mast merge {i}` из основной копии — он проверяет ветку, "
          "вливает fast-forward и одним коммитом переносит тезис в `DONE.md`, убирает строку и "
          "заносит долг, потом убирает worktree; `git merge` оставил бы роадмап наполовину.",
    "en": "MAST: an item branch is merged by `mast merge {i}` from the main copy — it checks "
          "the branch, fast-forwards, moves the thesis to `DONE.md`, drops the line and records "
          "debt in one commit, then removes the worktree; `git merge` would leave the roadmap "
          "half-done.",
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


def worktree(parts):
    """(корень worktree, его имя, путь внутри) по сегментам `.claude/worktrees/<имя>/` или None."""
    for i in range(len(parts) - 2):
        if parts[i:i + 2] == WORKTREES:
            return Path(*parts[:i + 3]), parts[i + 2], parts[i + 3:]
    return None


def guard(payload, lang):
    """Защиты Edit/Write для любой сессии: причина отказа или None."""
    file_path = payload["tool_input"].get("file_path")
    if not file_path:
        return None
    # normpath, а не resolve: хватает сегментов пути, а хук стреляет на каждую правку
    parts = Path(os.path.normpath(os.path.join(payload["cwd"], file_path))).parts
    wt = worktree(parts)
    if wt and wt[2] in LEDGER:
        return LEDGER_EDIT[lang].format(rel=Path(*wt[2]).as_posix(), w=wt[1], p=PLUGIN[lang])
    if payload["tool_name"] != "Write":
        return None
    for i in range(len(parts) - 1):
        if parts[i:i + 2] == SUPERPOWERS and Path(*parts[:i], "ROADMAP.md").is_file():
            return PLANS[lang].format(i=wt[1] if wt and re.fullmatch(ID, wt[1]) else "<X-N>")
    return None


def git_calls(command, sub):
    """Аргументы каждого `git <sub>` в команде оболочки. Тела heredoc и строки в кавычках
    вырезаны: сообщение коммита, где упомянут `git merge`, — не вливание."""
    command = re.sub(QUOTED, "''", re.sub(HEREDOC, r"\3", command))
    return [m.group(1) for m in re.finditer(GIT.format(sub), command)]


def shell_refusal(payload, lang):
    """Защиты Bash для любой сессии: `git merge` ветки пункта, коммит файлов роадмапа из
    worktree. Причина отказа или None."""
    command = payload["tool_input"].get("command", "")
    for args in git_calls(command, "merge"):
        m = re.search(ITEM_BRANCH, args)
        if m:
            return MERGE[lang].format(i=m.group(1))
    wt = worktree(Path(payload["cwd"]).parts)
    if not wt or not git_calls(command, "commit"):
        return None
    import subprocess
    # Не только индекс: `git add … && git commit` одной командой, а хук видит состояние до неё
    out = subprocess.run(["git", "-C", str(wt[0]), "status", "--porcelain", "--",
                          *(Path(*f).as_posix() for f in LEDGER)],
                         capture_output=True, text=True, encoding="utf-8").stdout
    files = sorted({line[3:] for line in out.splitlines()})
    if not files:
        return None
    return LEDGER_COMMIT[lang].format(w=wt[1], f=", ".join(f"`{f}`" for f in files), c=" ".join(files))


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
    else:
        reason = guard(payload, lang) or is_dispatcher(payload) and refusal(payload, lang)
        if reason:
            print(json.dumps({"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
