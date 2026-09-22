"""Сторожа команды разворачивания каркаса — по одной на язык.

Саму команду тест прогнать не может: это markdown-промпт для модели, а не скрипт.
Поведение «`--check` не меняет ни файла» проверено ручными прогонами (архив пункта
A-1) и записано долгом в `TECH_DEBT.md`. Здесь — то, что проверяемо детерминированно:
образец чужого проекта, целость ограждений и паритет двух языковых версий.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIX = Path(__file__).resolve().parent / "fixtures" / "legacy"
COMMANDS = {lang: ROOT / "plugins" / lang / "commands" / "init-project.md"
            for lang in ("en", "ru")}
GUARD_SECTION = {"en": "## Audit guardrails", "ru": "## Ограждения ревизии"}
# Ограждение — это запрет («не придумывается») или обязательное требование
# («проверяется в описи»). Формулировка без того и другого не ограждает.
GUARD_WORDS = {"en": r"\bnever\b|\bmust\b|\bno\b|\bonly\b|is checked",
               "ru": r"\bне\b|\bтолько\b|должн|проверя|обязат"}


def text(lang):
    return COMMANDS[lang].read_text(encoding="utf-8")


def headings(lang):
    return re.findall(r"^## .+$", text(lang), re.M)


# Находки ручной проверки 22.09 (пункт A-9): предложения шли текстом файла целиком,
# а оригинал после переноса оставался рядом с копией — две истины об одном.
DIFF_BLOCK = {"en": r"a `diff` block", "ru": r"блоком `diff`"}
ORIGINAL_QUESTION = {"en": r"delete the original", "ru": r"удалить ли оригинал"}


def guard_section(lang):
    section = re.search(rf"^{re.escape(GUARD_SECTION[lang])}\n(.*?)^## ", text(lang), re.S | re.M)
    assert section, f"{COMMANDS[lang].name}: нет секции «{GUARD_SECTION[lang]}»"
    return section.group(1)


def guards(lang):
    return re.findall(r"^\d+\. \*\*(.+?)\*\*", guard_section(lang), re.M)


def test_образец_содержит_все_случаи_ревизии():
    names = {p.name for p in FIX.rglob("*") if p.is_file()}
    assert {"CLAUDE.md", "TODO.md", "CHANGELOG.md"} <= names
    assert len((FIX / "CLAUDE.md").read_text(encoding="utf-8").splitlines()) > 200
    rule = next(FIX.glob(".claude/rules/*.md"))
    assert not rule.read_text(encoding="utf-8").startswith("---")      # правило без paths:


@pytest.mark.parametrize("lang", sorted(COMMANDS))
def test_ограждения_ревизии_на_месте_в_тексте_команды(lang):
    """Вырезать ограждение из промпта — единственный способ снять его молча."""
    found = guards(lang)
    assert len(found) >= 5, f"{lang}: ограждений осталось {len(found)}, было пять: {found}"
    for g in found:
        assert re.search(GUARD_WORDS[lang], g.lower()), \
            f"{lang}: ограждение ничего не запрещает и ничего не требует: {g}"


@pytest.mark.parametrize("lang", sorted(COMMANDS))
def test_предложение_по_существующему_файлу_показано_блоком_diff(lang):
    """Текст файла целиком прячет, что именно меняется: 18 тыс. символов без единой
    строки `-`/`+` человек не проверит, а просто согласится."""
    assert re.search(DIFF_BLOCK[lang], guard_section(lang)), \
        f"{lang}: ограждения не требуют блока diff для существующего файла"


@pytest.mark.parametrize("lang", sorted(COMMANDS))
def test_перенос_спрашивает_удалить_ли_оригинал(lang):
    """После переноса `TODO.md` → `ROADMAP.md` и `CHANGELOG.md` → `DONE.md` оригинал без
    вопроса остаётся рядом, и в проекте две истины об одном."""
    rows = [r for r in text(lang).splitlines() if r.startswith(("| `TODO.md`", "| `CHANGELOG.md`"))]
    assert len(rows) == 2, f"{lang}: строк переноса в таблице находок {len(rows)}, ждали 2"
    for row in rows:
        assert re.search(ORIGINAL_QUESTION[lang], row, re.I), \
            f"{lang}: «{row[:40]}…» не спрашивает про оригинал"


def test_языковые_версии_команды_не_разъехались():
    """Правка сценария на одном языке без другого — то же расхождение, что у локалей."""
    assert len(headings("ru")) == len(headings("en")), \
        f"разное число разделов: ru {headings('ru')}, en {headings('en')}"
    assert len(guards("ru")) == len(guards("en"))
    for lang in COMMANDS:
        steps = re.findall(r"^## (?:Шаг|Step) (\d)", text(lang), re.M)
        assert steps == sorted(steps), f"{lang}: шаги идут не по порядку: {steps}"


def test_каждая_версия_живёт_в_своей_локали():
    assert not re.search(r"[а-яёА-ЯЁ]", text("en")), "в английской команде осталась кириллица"
    assert "locales/en/" in text("en") and "locales/ru/" not in text("en")
    assert "locales/ru/" in text("ru") and "locales/en/" not in text("ru")
    for lang in COMMANDS:                      # язык больше не угадывается по контексту
        assert "<язык>" not in text(lang) and "<lang>" not in text(lang)


@pytest.mark.parametrize("lang", sorted(COMMANDS))
def test_каждый_шаблон_локали_предлагается_командой(lang):
    """Завести шаблон и забыть предложить его — он не доедет до пользователя никогда."""
    templates = sorted(p.name for p in (ROOT / "locales" / lang / "templates").glob("*.template.md"))
    assert templates, f"{lang}: шаблонов не найдено"
    for name in templates:
        assert name in text(lang), f"{lang}: команда не знает про шаблон {name}"
