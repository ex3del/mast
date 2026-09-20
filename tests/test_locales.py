import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCALES = ROOT / "locales"


def files(lang):
    return {p.relative_to(LOCALES / lang) for p in (LOCALES / lang).rglob("*.md")}


def headings(path):
    return re.findall(r"^(#{1,6})(?= )", path.read_text(), re.M)


def test_состав_файлов_локалей_совпадает():
    assert files("ru") == files("en")


def test_дерево_заголовков_совпадает():
    for rel in sorted(files("ru")):
        assert headings(LOCALES / "ru" / rel) == headings(LOCALES / "en" / rel), rel
