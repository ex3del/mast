#!/usr/bin/env python3
"""SessionStart: вкладывает ядро метода MAST в контекст сессии."""
import os
import sys
from pathlib import Path

LANGS = ("ru", "en")
HINT = {
    "ru": "В этом проекте метод MAST не развёрнут. Развернуть — команда `/init-project`.",
    "en": "MAST is not set up in this project. Run `/init-project` to scaffold it.",
}


def pick_language(env):
    """Язык из настройки плагина; неизвестное значение — русский."""
    lang = env.get("CLAUDE_PLUGIN_OPTION_LANGUAGE", "ru")
    return lang if lang in LANGS else "ru"


def render(project_dir, root, lang):
    """Полное ядро там, где метод развёрнут, иначе одна строка-указатель."""
    project_dir = Path(project_dir)
    deployed = (project_dir / "ROADMAP.md").exists() or (project_dir / ".claude" / "rules").is_dir()
    if not deployed:
        return HINT[lang]
    return (Path(root) / "locales" / lang / "core.md").read_text()


def main():
    root = os.environ.get("CLAUDE_PLUGIN_ROOT", str(Path(__file__).resolve().parent.parent))
    project = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    print(render(project, root, pick_language(os.environ)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
