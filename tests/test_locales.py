import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCALES = ROOT / "locales"


def files(lang):
    return {p.relative_to(LOCALES / lang) for p in (LOCALES / lang).rglob("*.md")}


def headings(path):
    return re.findall(r"^(#{1,6})(?= )", path.read_text(encoding="utf-8"), re.M)


def test_состав_файлов_локалей_совпадает():
    ru = files("ru")
    assert ru, "locales/ru пуст"
    assert ru == files("en")


def test_дерево_заголовков_совпадает():
    ru = sorted(files("ru"))
    assert ru, "locales/ru пуст"
    for rel in ru:
        ru_headings = headings(LOCALES / "ru" / rel)
        assert ru_headings, f"{rel}: заголовков не найдено"
        assert ru_headings == headings(LOCALES / "en" / rel), rel
