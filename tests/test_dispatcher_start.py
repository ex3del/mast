"""Диспетчер ставит контракт, а не план.

Замер в docs/research/2026-09-23-dispatcher-load.md: промпт старта — медиана 1165
символов при образце ~220, а в шапку `STATUS.md` диспетчер писал проектные указания,
не читая кода. План и `STATUS.md` пишет сессия пункта; промпт — номер, скилл и
координационные факты, контекст разговора с человеком — в строку пункта.

Промпт собирает `mast start` (A-19), предел хвоста держит он и `tests/test_mast_start.py`.
Раздел — вызов команды и то, чего скрипт не проверит: был 1761 символ ru, 2009 en.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = "plugins/{lang}/locales/{lang}/skills/managing-roadmap-items-dispatcher.md"
START = {"ru": "## Запуск пункта", "en": "## Starting an item"}
# ru — из «Готово когда» A-19; en при ru 384 вышел 462
SECTION_LIMIT = {"ru": 400, "en": 480}


def section(lang):
    text = (ROOT / SKILL.format(lang=lang)).read_text(encoding="utf-8")
    found = [p for p in re.split(r"^(?=## )", text, flags=re.M) if p.splitlines()[0] == START[lang]]
    assert found, f"{lang}: нет раздела «{START[lang]}» — переименовали, поправь сторожа"
    return found[0]


def test_запуск_пункта_не_заводит_status_md():
    for lang in START:
        assert "STATUS.md" not in section(lang), f"{lang}: план и STATUS.md заводит сессия пункта"


def test_запуск_одной_командой_раздел_короткий():
    for lang in START:
        text = section(lang).rstrip("\n")
        assert "mast start" in text and "claude --bg" not in text, f"{lang}: запуск — командой mast start"
        assert len(text) <= SECTION_LIMIT[lang], f"{lang}: раздел {len(text)} символов"
