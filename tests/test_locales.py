import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def locale(lang):
    """Тексты языка лежат в его плагине — других копий нет."""
    return ROOT / "plugins" / lang / "locales" / lang


def files(lang):
    return {p.relative_to(locale(lang)) for p in locale(lang).rglob("*.md")}


def headings(path):
    return re.findall(r"^(#{1,6})(?= )", path.read_text(encoding="utf-8"), re.M)


def test_состав_файлов_локалей_совпадает():
    ru = files("ru")
    assert ru, "plugins/ru/locales/ru пуст"
    assert ru == files("en")


def test_дерево_заголовков_совпадает():
    ru = sorted(files("ru"))
    assert ru, "plugins/ru/locales/ru пуст"
    for rel in ru:
        ru_headings = headings(locale("ru") / rel)
        assert ru_headings, f"{rel}: заголовков не найдено"
        assert ru_headings == headings(locale("en") / rel), rel


def test_текст_лежит_в_репозитории_один_раз():
    """Каждый язык едет ровно в один плагин, поэтому его тексты живут только там.
    Копия рядом — второй «источник»: его правят, а до пользователя правка не доезжает.
    `.claude/` пропускаем — там чужие worktree, полные копии репозитория."""
    texts = {p.read_bytes(): p for lang in ("ru", "en") for p in locale(lang).rglob("*.md")}
    twins = [f"{p.relative_to(ROOT)} = {texts[p.read_bytes()].relative_to(ROOT)}"
             for p in ROOT.rglob("*.md")
             if not {".git", ".claude"} & set(p.relative_to(ROOT).parts)
             and p.read_bytes() in texts and p != texts[p.read_bytes()]]
    assert not twins, "тексты правятся только в plugins/<язык>/locales/<язык>/:\n" + "\n".join(twins)
