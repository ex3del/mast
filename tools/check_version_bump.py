#!/usr/bin/env python3
"""Версия плагина выросла, если изменение трогает метод.

Для CI: `pre-commit` работает только у того, кто его подключил, а PR контрибьютора
и мердж через веб-интерфейс его обходят. Сравниваются версии, а не время коммитов:
коммит из форка бывает старше последнего бампа в `main`.

  check_version_bump.py <база>   — база: `origin/main` для PR, прошлая вершина для push
"""
import json
import subprocess
import sys

MANIFEST = "plugins/en/.claude-plugin/plugin.json"
METHOD = ("hooks/", "locales/", "plugins/")


def git(*args):
    r = subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        sys.exit(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def version(ref):
    """Версия как кортеж чисел — «3.10.0» больше «3.9.0», чего строки не умеют."""
    return tuple(int(p) for p in json.loads(git("show", f"{ref}:{MANIFEST}"))["version"].split("."))


def check(base, head="HEAD"):
    """Текст ошибки или None."""
    changed = [f for f in git("diff", "--name-only", f"{base}...{head}").splitlines()
               if f.startswith(METHOD)]
    if not changed:
        return None
    old, new = version(base), version(head)
    if new > old:
        return None
    shown = ", ".join(changed[:3]) + (" …" if len(changed) > 3 else "")
    return (f"Метод изменился ({shown}), а версия в {MANIFEST} не выросла: "
            f"{'.'.join(map(str, old))} → {'.'.join(map(str, new))}. Без бампа обновление "
            "не доедет до пользователей. / The method changed but the plugin version didn't grow.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    error = check(sys.argv[1])
    if error:
        sys.exit(error)
    print("версия в порядке")
