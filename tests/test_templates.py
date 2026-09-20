import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_шаблон_роадмапа_проходит_собственный_линт(tmp_path):
    dst = tmp_path / "ROADMAP.md"
    dst.write_text((ROOT / "locales/ru/templates/ROADMAP.template.md").read_text())
    r = subprocess.run([sys.executable, str(ROOT / "hooks/roadmap_lint.py"), str(dst)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_шаблон_правила_несёт_paths():
    assert (ROOT / "locales/ru/templates/rule.template.md").read_text().startswith("---\npaths:")
