"""Сторожа команды `/mast:init-project`.

Саму команду тест прогнать не может: это markdown-промпт для модели, а не скрипт.
Поведение «`--check` не меняет ни файла» проверено ручными прогонами (архив пункта
A-1) и записано долгом в `TECH_DEBT.md`. Здесь — то, что проверяемо детерминированно:
образец чужого проекта и целость ограждений в тексте команды.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIX = Path(__file__).resolve().parent / "fixtures" / "legacy"
COMMAND = ROOT / "commands" / "init-project.md"


def test_образец_содержит_все_случаи_ревизии():
    names = {p.name for p in FIX.rglob("*") if p.is_file()}
    assert {"CLAUDE.md", "TODO.md", "CHANGELOG.md"} <= names
    assert len((FIX / "CLAUDE.md").read_text(encoding="utf-8").splitlines()) > 200
    rule = next(FIX.glob(".claude/rules/*.md"))
    assert not rule.read_text(encoding="utf-8").startswith("---")      # правило без paths:


def test_ограждения_ревизии_на_месте_в_тексте_команды():
    """Вырезать ограждение из промпта — единственный способ снять его молча."""
    text = COMMAND.read_text(encoding="utf-8")
    section = re.search(r"^## Ограждения ревизии\n(.*?)^## ", text, re.S | re.M)
    assert section, "в команде нет секции «Ограждения ревизии»"
    guards = re.findall(r"^\d+\. \*\*(.+?)\*\*", section.group(1), re.M)
    assert len(guards) >= 4, f"ограждений осталось {len(guards)}, было четыре: {guards}"
    # Ограждение — это запрет («не придумывается») или обязательная проверка
    # («проверяется в описи»). Формулировка без того и другого не ограждает.
    for g in guards:
        assert re.search(r"\bне\b|\bтолько\b|должн|проверя|обязат", g.lower()), \
            f"ограждение ничего не запрещает и ничего не требует: {g}"
