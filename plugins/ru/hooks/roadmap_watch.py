#!/usr/bin/env python3
# Сгенерировано tools/sync_plugins.py из hooks/roadmap_watch.py — правь там, здесь затрётся
"""Быстрый вход Bash-хуков линта роадмапа: PostToolUse на каждый вызов Bash и
PreToolUse перед git-командами — там же защиты сессий на коммит и `git merge`, а после
`mast merge` — подсказка перезапуска диспетчеру. PreToolUse перед командами внешних
инструментов (`prod.FILTER`) у основного потока диспетчера — отказ на прод (`prod.py`).

Хук стреляет на каждый Bash в любом проекте, поэтому здесь только то, что укладывается
в старт интерпретатора: ни git, ни `json`, `re`, `subprocess`. `import subprocess` и один
`git diff` вместе стоят ~12 мс сверх старта (замер A-12). `roadmap_lint` зовём, только
когда есть что проверять: перед коммитом или если роадмап с прошлого вызова изменился.
"""
import os
import sys
import zlib

FILES = ("ROADMAP.md", os.path.join("docs", "roadmap", "DONE.md"))


def fingerprint(project):
    """Размер и время правки роадмапа и архива. Содержимое не годится: «сломал через
    Bash → починил Edit → сломал снова» вернуло бы прежний текст, и хук промолчал бы."""
    out = []
    for rel in FILES:
        try:
            s = os.stat(os.path.join(project, rel))
            out.append(f"{s.st_size}:{s.st_mtime_ns}")
        except OSError:
            out.append("-")
    return " ".join(out)


def changed(project):
    """Отпечаток разошёлся с прошлым вызовом в этом проекте. Новый пишется сразу, до
    линта: иначе одна и та же жалоба повторялась бы на каждом Bash, пока файл не закоммитят.
    Площадка без `CLAUDE_PLUGIN_DATA` — отпечаток хранить негде, линтуем каждый раз."""
    data = os.environ.get("CLAUDE_PLUGIN_DATA")
    if not data:
        return True
    cache = os.path.join(data, f"roadmap-{zlib.crc32(project.encode()):08x}")
    key = fingerprint(project)
    try:
        with open(cache, encoding="utf-8") as f:
            if f.read() == key:
                return False
    except OSError:
        pass
    os.makedirs(data, exist_ok=True)
    with open(cache, "w", encoding="utf-8") as f:
        f.write(key)
    return True


def dispatcher_thread(raw):
    """Основной поток диспетчера — по байтам входа, без `json`: хук на прод-команду стреляет
    и у сессий пунктов. У субагента во входе `agent_id`; роль — `MAST_ROLE` или файл роли
    по `session_id`, как в `dispatcher.is_dispatcher`."""
    if b'"agent_id"' in raw:
        return False
    if os.environ.get("MAST_ROLE") == "dispatcher":
        return True
    data, i = os.environ.get("CLAUDE_PLUGIN_DATA"), raw.find(b'"session_id"')
    if not data or i < 0:
        return False
    session_id = raw[i + len(b'"session_id"'):].split(b'"')[1].decode()
    return os.path.exists(os.path.join(data, f"{session_id}.role"))


def main():
    raw = sys.stdin.buffer.read()
    prod_check = False
    # Кавычка внутри строкового значения JSON экранирована, поэтому `"PreToolUse"`
    # целиком встречается только как значение `hook_event_name`
    if b'"PreToolUse"' in raw:
        prod_check = dispatcher_thread(raw)
        # `if: Bash(git *)` пропускает сюда любую git-команду, а проверять надо коммит и вливание.
        # `merge ` с пробелом: `merge-base` и `--merges` медленный путь удорожил бы на 8 мс
        if not prod_check and b"commit" not in raw and b"merge " not in raw:
            return 0
    else:
        project = os.environ.get("CLAUDE_PROJECT_DIR", ".")
        # Проект без роадмапа — не наш: ни линта, ни файла кэша
        if not os.path.isfile(os.path.join(project, "ROADMAP.md")) or not changed(project):
            return 0
    import json
    import roadmap_lint
    lang, _ = roadmap_lint.pick_language(sys.argv[1:])
    payload = json.loads(raw)
    if payload["hook_event_name"] == "PreToolUse":
        # Защиты сессий — в dispatcher.py рядом с защитами Edit/Write
        from dispatcher import shell_refusal
        reason = shell_refusal(payload, lang or "en")
        if not reason and prod_check:
            import prod
            reason = prod.refusal(payload, lang or "en")
        if reason:
            print(reason, file=sys.stderr)
            return 2
    code = roadmap_lint.hook(payload, lang)
    if code == 0:
        # Вливание всегда меняет роадмап, поэтому `mast merge` быстрый путь не пропускает
        import restart
        hint = restart.hint(payload, lang or "en")
        if hint:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": hint}}))
    return code


if __name__ == "__main__":
    sys.exit(main())
