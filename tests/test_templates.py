import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_шаблон_роадмапа_проходит_собственный_линт(tmp_path):
    dst = tmp_path / "ROADMAP.md"
    dst.write_text((ROOT / "locales/ru/templates/ROADMAP.template.md").read_text(encoding="utf-8"))
    r = subprocess.run([sys.executable, str(ROOT / "hooks/roadmap_lint.py"), str(dst)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_английский_шаблон_роадмапа_проходит_собственный_линт(tmp_path):
    dst = tmp_path / "ROADMAP.md"
    dst.write_text((ROOT / "locales/en/templates/ROADMAP.template.md").read_text(encoding="utf-8"))
    r = subprocess.run([sys.executable, str(ROOT / "hooks/roadmap_lint.py"), str(dst)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_шаблон_правила_несёт_paths():
    assert (ROOT / "locales/ru/templates/rule.template.md").read_text(encoding="utf-8").startswith("---\npaths:")


def test_правило_context7_ссылается_на_инструмент_по_роли():
    for lang in ("ru", "en"):
        text = (ROOT / f"locales/{lang}/templates/context7.rule.template.md").read_text(encoding="utf-8")
        assert text.startswith("---\npaths:")
        assert "mcp__plugin_mast_context7" not in text   # по роли, а не по точному имени
