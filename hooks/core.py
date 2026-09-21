#!/usr/bin/env python3
"""SessionStart: вкладывает ядро метода MAST в контекст сессии."""
import os
import sys
from pathlib import Path

LANGS = ("ru", "en")
HINT = {
    "ru": "В этом проекте метод MAST не развёрнут. Развернуть — команда `/mast:init-project-ru`.",
    "en": "MAST is not set up in this project. Run `/mast:init-project` to scaffold it.",
}
UNREADABLE = {
    "ru": "MAST: не удалось прочитать ядро ({path}). Проверь установку плагина.",
    "en": "MAST: could not read the core ({path}). Check the plugin installation.",
}


def pick_language(argv):
    """Язык — первым аргументом от того плагина, чья разводка вызвала хук.

    Код хуков общий на оба плагина, поэтому язык приходит не из настройки, а из
    `hooks.json` конкретного плагина: `mast` передаёт `en`, `mast-ru` — `ru`.
    """
    lang = argv[0] if argv else "ru"
    return lang if lang in LANGS else "ru"


def render(project_dir, root, lang):
    """Полное ядро там, где метод развёрнут, иначе одна строка-указатель.

    Нечитаемый файл ядра не роняет хук — вместо трассировки короткое сообщение.
    """
    project_dir = Path(project_dir)
    deployed = (project_dir / "ROADMAP.md").exists() or (project_dir / ".claude" / "rules").is_dir()
    if not deployed:
        return HINT[lang]
    core_path = Path(root) / "locales" / lang / "core.md"
    try:
        return core_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        # Битые байты в файле ядра — такая же непрочитанность, как и его отсутствие
        return UNREADABLE[lang].format(path=core_path)


def project_dir(env):
    """Каталог проекта. cwd вычисляем, только если переменной нет: он может быть
    удалён (worktree снесли после мерджа), и тогда `os.getcwd()` бросает."""
    if env.get("CLAUDE_PROJECT_DIR"):
        return env["CLAUDE_PROJECT_DIR"]
    try:
        return os.getcwd()
    except OSError:
        return ""


def main():
    # Тексты лежат рядом с этим файлом, а не в каталоге плагина: код общий на оба
    root = Path(__file__).resolve().parent.parent
    text = render(project_dir(os.environ), root, pick_language(sys.argv[1:]))
    sys.stdout.buffer.write(text.encode("utf-8") + b"\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
