#!/usr/bin/env python3
"""Раскладывает код и тексты внутрь каталогов плагинов.

Площадка копирует в кэш **только содержимое каталога плагина** (`plugins/<язык>/`),
а не весь репозиторий: проверено живьём на установке из маркетплейса — `${CLAUDE_PLUGIN_ROOT}`
указывал в `~/.claude/plugins/cache/<маркетплейс>/<плагин>/<версия>`, и путь
`../../hooks/core.py` вёл в пустоту. Поэтому плагин обязан быть самодостаточным.

Истина одна — корневые `hooks/` и `locales/<язык>/`; внутри плагина лежат их копии,
и править их руками нельзя: следующий запуск скрипта затрёт правку.

  sync_plugins.py           — разложить копии
  sync_plugins.py --check   — код 1, если копии отличаются от источника
"""
import filecmp
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LANGS = ("ru", "en")
# Что копируется: (источник относительно корня, куда относительно каталога плагина)
COPIES = [("hooks", "hooks"), ("locales/{lang}", "locales/{lang}")]
SKIP = {".DS_Store", "__pycache__"}
# Файлы самого плагина, которые живут в тех же каталогах и копиями не являются:
# `hooks.json` — разводка хуков, у каждого плагина своя (в ней язык).
KEEP = {"hooks.json"}


def pairs(lang):
    plugin = ROOT / "plugins" / lang
    for src, dst in COPIES:
        yield ROOT / src.format(lang=lang), plugin / dst.format(lang=lang)


def sources(src):
    """Файлы источника: относительный путь → сам путь."""
    return {p.relative_to(src): p for p in sorted(src.rglob("*"))
            if p.is_file() and not (SKIP & set(p.parts))}


def stale(src, dst):
    """Что разошлось: отсутствующие, отличающиеся и лишние файлы копии."""
    wanted = sources(src)
    if not dst.is_dir():
        return [f"нет каталога {dst.name}"]
    diff = [str(rel) for rel, path in wanted.items()
            if not (dst / rel).is_file() or not filecmp.cmp(path, dst / rel, shallow=False)]
    diff += [f"лишний: {p.relative_to(dst)}" for p in sorted(dst.rglob("*"))
             if p.is_file() and p.relative_to(dst) not in wanted and p.name not in KEEP]
    return diff


def check():
    return [f"plugins/{lang}/{dst.relative_to(ROOT / 'plugins' / lang)}: {d}"
            for lang in LANGS for src, dst in pairs(lang) for d in stale(src, dst)]


def sync():
    for lang in LANGS:
        for src, dst in pairs(lang):
            wanted = sources(src)
            for rel, path in wanted.items():
                twin = dst / rel
                twin.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, twin)
            # Файл выбыл из источника — выбывает и из копии, но обёртку не трогаем
            for path in sorted(dst.rglob("*"), reverse=True):
                if path.is_file() and path.relative_to(dst) not in wanted and path.name not in KEEP:
                    path.unlink()
                elif path.is_dir() and not any(path.iterdir()):
                    path.rmdir()


def main():
    if sys.argv[1:2] == ["--check"]:
        problems = check()
        if problems:
            print("Копии в plugins/ отстали от источника:", *problems, sep="\n  ", file=sys.stderr)
            print("Разложить: python3 tools/sync_plugins.py", file=sys.stderr)
            return 1
        return 0
    sync()
    print("Копии разложены:", ", ".join(f"plugins/{lang}" for lang in LANGS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
