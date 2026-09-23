"""Диспетчер ставит контракт, а не план.

Замер в docs/research/2026-09-23-dispatcher-load.md: промпт старта — медиана 1165
символов при образце ~220, а в шапку `STATUS.md` диспетчер писал проектные указания,
не читая кода. План и `STATUS.md` пишет сессия пункта; промпт — номер, скилл и
координационные факты, контекст разговора с человеком — в строку пункта.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = "locales/{lang}/skills/managing-roadmap-items-dispatcher.md"
START = {"ru": "## Запуск пункта", "en": "## Starting an item"}
PROMPT_LIMIT = 300


def section(lang):
    text = (ROOT / SKILL.format(lang=lang)).read_text(encoding="utf-8")
    found = [p for p in re.split(r"^(?=## )", text, flags=re.M) if p.splitlines()[0] == START[lang]]
    assert found, f"{lang}: нет раздела «{START[lang]}» — переименовали, поправь сторожа"
    return found[0]


def test_запуск_пункта_не_заводит_status_md():
    for lang in START:
        assert "STATUS.md" not in section(lang), f"{lang}: план и STATUS.md заводит сессия пункта"


def test_образец_промпта_старта_короткий():
    for lang in START:
        prompts = re.findall(r'claude --bg[^\n]*?"([^"]+)"', section(lang))
        assert prompts, f"{lang}: образца промпта в разделе нет"
        for p in prompts:
            assert len(p) <= PROMPT_LIMIT, f"{lang}: образец промпта {len(p)} символов"
