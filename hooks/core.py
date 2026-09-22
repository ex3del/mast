#!/usr/bin/env python3
"""SessionStart: вкладывает ядро метода MAST в контекст сессии."""
import os
import sys
from pathlib import Path

from plugin_names import PLUGIN

LANGS = ("ru", "en")
HINT = {
    "ru": "В этом проекте метод MAST не развёрнут. Развернуть — команда `/{p}:init-project`.",
    "en": "MAST is not set up in this project. Run `/{p}:init-project` to scaffold it.",
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


# Настройка `always_core` доезжает до хука двумя путями: подстановкой
# `${user_config.always_core}` в `env` разводки и автоматической переменной
# площадки. Живой прогон на 3.1.0 показал, что первая не сработала, — поэтому
# читаем обе и не зависим от того, какая жива в конкретной версии Claude Code.
ALWAYS_CORE_VARS = ("MAST_ALWAYS_CORE", "CLAUDE_PLUGIN_OPTION_ALWAYS_CORE")


def wants_core_everywhere(env):
    """Значение не задано — приходит пустая строка или переменной нет вовсе; всё,
    кроме явного «да», считаем «нет», чтобы у постороннего плагин молчал в чужих
    проектах, пока он не попросил обратного."""
    for name in ALWAYS_CORE_VARS:
        value = env.get(name, "").strip().lower()
        if value:
            return value in {"true", "1", "yes", "on"}
    return False


def read_core(root, lang):
    """Текст ядра. Нечитаемый файл не роняет хук — вместо трассировки сообщение."""
    core_path = Path(root) / "locales" / lang / "core.md"
    try:
        return core_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        # Битые байты в файле ядра — такая же непрочитанность, как и его отсутствие
        return UNREADABLE[lang].format(path=core_path)


def render(project_dir, root, lang, always=False):
    """Развёрнут метод — ядро целиком. Нет — строка-указатель, а с настройкой
    `always_core` ещё и само ядро: правила про план, записи и параллельные сессии
    работают и там, где роадмапа пока нет."""
    project_dir = Path(project_dir)
    deployed = (project_dir / "ROADMAP.md").exists() or (project_dir / ".claude" / "rules").is_dir()
    if deployed:
        return read_core(root, lang)
    hint = HINT[lang].format(p=PLUGIN[lang])
    return f"{hint}\n\n{read_core(root, lang)}" if always else hint


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
    text = render(project_dir(os.environ), root, pick_language(sys.argv[1:]),
                  wants_core_everywhere(os.environ))
    sys.stdout.buffer.write(text.encode("utf-8") + b"\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
