#!/usr/bin/env python3
"""SessionStart: вкладывает ядро метода MAST в контекст сессии."""
import os
import sys
from pathlib import Path

LANGS = ("ru", "en")
HINT = {
    "ru": "В этом проекте метод MAST не развёрнут. Развернуть — команда `/mast:init-project`.",
    "en": "MAST is not set up in this project. Run `/mast:init-project` to scaffold it.",
}
UNREADABLE = {
    "ru": "MAST: не удалось прочитать ядро ({path}). Проверь установку плагина.",
    "en": "MAST: could not read the core ({path}). Check the plugin installation.",
}


def pick_language(env):
    """Язык из настройки плагина; неизвестное значение — русский."""
    lang = env.get("CLAUDE_PLUGIN_OPTION_LANGUAGE", "ru")
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
    except OSError:
        return UNREADABLE[lang].format(path=core_path)


def main():
    root = os.environ.get("CLAUDE_PLUGIN_ROOT", str(Path(__file__).resolve().parent.parent))
    project = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    text = render(project, root, pick_language(os.environ))
    sys.stdout.buffer.write(text.encode("utf-8") + b"\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
