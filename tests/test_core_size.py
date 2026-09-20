from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIMIT = 6000          # наш потолок; лимит площадки 10 000


def test_ядро_каждой_локали_влезает_в_лимит():
    for core in sorted(ROOT.glob("locales/*/core.md")):
        size = len(core.read_text())
        assert size <= LIMIT, f"{core}: {size} символов"
