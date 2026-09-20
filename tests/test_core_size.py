from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIMIT = 6000          # наш потолок; лимит площадки 10 000


def test_ядро_каждой_локали_влезает_в_лимит():
    cores = sorted(ROOT.glob("locales/*/core.md"))
    assert len(cores) == 2, f"ожидались ru и en, найдено: {cores}"
    for core in cores:
        size = len(core.read_text())
        assert 0 < size <= LIMIT, f"{core}: {size} символов"
