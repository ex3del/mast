import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "hooks"))
import core  # noqa: E402


def test_язык_берётся_из_окружения_иначе_русский():
    assert core.pick_language({"CLAUDE_PLUGIN_OPTION_LANGUAGE": "en"}) == "en"
    assert core.pick_language({"CLAUDE_PLUGIN_OPTION_LANGUAGE": "de"}) == "ru"
    assert core.pick_language({}) == "ru"


def test_в_проекте_с_роадмапом_вкладывается_полное_ядро(tmp_path):
    (tmp_path / "ROADMAP.md").write_text("- **A-1** что-то\n")
    assert core.render(tmp_path, ROOT, "ru") == (ROOT / "locales/ru/core.md").read_text()


def test_в_проекте_без_метода_только_строка_указатель(tmp_path):
    out = core.render(tmp_path, ROOT, "ru")
    assert len(out) < 300
    assert "/init-project" in out
