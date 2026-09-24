#!/usr/bin/env python3
"""Быстрый вход Bash-хуков линта роадмапа: PostToolUse на каждый вызов Bash и
PreToolUse перед git-командами — там же защиты сессий на коммит и `git merge`.

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


def main():
    raw = sys.stdin.buffer.read()
    # Кавычка внутри строкового значения JSON экранирована, поэтому `"PreToolUse"`
    # целиком встречается только как значение `hook_event_name`
    if b'"PreToolUse"' in raw:
        # `if: Bash(git *)` пропускает сюда любую git-команду, а проверять надо коммит и вливание.
        # `merge ` с пробелом: `merge-base` и `--merges` медленный путь удорожил бы на 8 мс
        if b"commit" not in raw and b"merge " not in raw:
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
        if reason:
            print(reason, file=sys.stderr)
            return 2
    return roadmap_lint.hook(payload, lang)


if __name__ == "__main__":
    sys.exit(main())
