import os
import subprocess
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


def test_нечитаемое_ядро_возвращает_сообщение_а_не_падает(tmp_path):
    (tmp_path / "ROADMAP.md").write_text("- **A-1** что-то\n")
    missing_root = tmp_path / "no-such-plugin-root"
    out = core.render(tmp_path, missing_root, "ru")
    assert "MAST: не удалось прочитать ядро" in out
    assert str(missing_root) in out


def test_вывод_utf8_даже_при_не_utf8_кодировке_окружения(tmp_path):
    (tmp_path / "ROADMAP.md").write_text("- **A-1** что-то\n", encoding="utf-8")
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "cp1252"
    env["CLAUDE_PROJECT_DIR"] = str(tmp_path)
    env["CLAUDE_PLUGIN_ROOT"] = str(ROOT)
    result = subprocess.run(
        [sys.executable, str(ROOT / "hooks" / "core.py")],
        env=env,
        capture_output=True,
    )
    assert result.returncode == 0
    expected = (ROOT / "locales/ru/core.md").read_text(encoding="utf-8") + "\n"
    assert result.stdout.decode("utf-8") == expected
