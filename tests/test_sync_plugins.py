"""Копии hooks/ в плагинах помечены как сгенерированные, и --check это сверяет."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import sync_plugins  # noqa: E402

MARK = "# Сгенерировано tools/sync_plugins.py из hooks/"


def test_копия_без_пометки_не_проходит_check(tmp_path, monkeypatch):
    """Копия побайтно равна источнику — так выглядит и символьная ссылка, которую на
    Windows git выкладывает текстовым файлом. Пометка пропала — --check обязан отказать."""
    monkeypatch.setattr(sync_plugins, "ROOT", tmp_path)
    src, dst = tmp_path / "hooks", tmp_path / "plugins/ru/hooks"
    src.mkdir()
    dst.mkdir(parents=True)
    (src / "core.py").write_text("#!/usr/bin/env python3\nprint()\n", encoding="utf-8")
    (dst / "core.py").write_bytes((src / "core.py").read_bytes())
    assert sync_plugins.stale(src, dst) == ["core.py"]
    (dst / "core.py").write_bytes(sync_plugins.generated(src / "core.py"))
    assert sync_plugins.stale(src, dst) == []


def test_кэш_python_в_копии_не_лишний_а_чужой_файл_лишний(tmp_path, monkeypatch):
    """Тесты в CI запускают копии хуков, и Python кладёт рядом `__pycache__/*.pyc` — это не
    отставшая копия. Настоящий лишний файл --check по-прежнему ловит."""
    monkeypatch.setattr(sync_plugins, "ROOT", tmp_path)
    src, dst = tmp_path / "hooks", tmp_path / "plugins/ru/hooks"
    src.mkdir()
    (dst / "__pycache__").mkdir(parents=True)
    (src / "core.py").write_text("print()\n", encoding="utf-8")
    (dst / "core.py").write_bytes(sync_plugins.generated(src / "core.py"))
    (dst / "__pycache__" / "core.cpython-312.pyc").write_bytes(b"\0")
    assert sync_plugins.stale(src, dst) == []
    (dst / "extra.py").write_text("", encoding="utf-8")
    assert sync_plugins.stale(src, dst) == ["лишний: extra.py"]


def test_пометка_первой_строкой_а_при_shebang_сразу_после_него():
    for lang in ("ru", "en"):
        for path in sorted((ROOT / "plugins" / lang / "hooks").glob("*.py")):
            lines = path.read_text(encoding="utf-8").splitlines()
            at = 1 if lines[0].startswith("#!") else 0
            assert lines[at].startswith(MARK + path.name), f"{path.relative_to(ROOT)}: нет пометки"
