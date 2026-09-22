import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "hooks"))
import core  # noqa: E402


def test_язык_приходит_аргументом_от_своего_плагина():
    """`mast` передаёт en, `mast-ru` — ru; код хуков у них общий."""
    assert core.pick_language(["en"]) == "en"
    assert core.pick_language(["ru"]) == "ru"
    assert core.pick_language(["de"]) == "ru"
    assert core.pick_language([]) == "ru"


def test_в_проекте_с_роадмапом_вкладывается_полное_ядро(tmp_path):
    (tmp_path / "ROADMAP.md").write_text("- **A-1** что-то\n")
    assert core.render(tmp_path, ROOT, "ru") == (ROOT / "locales/ru/core.md").read_text(encoding="utf-8")


def test_в_проекте_без_метода_только_строка_указатель(tmp_path):
    out = core.render(tmp_path, ROOT, "ru")
    assert len(out) < 300
    assert "/mast-ru:init-project" in out


def test_подсказка_зовёт_команду_своего_плагина(tmp_path):
    """Имя команды = имя плагина: у `mast-ru` она `/mast-ru:init-project`, у `mast` —
    `/mast:init-project`. Литерал от прошлой схемы отправлял в несуществующую команду."""
    for lang, name in (("ru", "mast-ru"), ("en", "mast")):
        out = core.render(tmp_path, ROOT, lang)
        assert f"/{name}:init-project`" in out or f"/{name}:init-project` " in out, out


def test_настройка_ядро_везде_читается_из_окружения():
    """Значение приезжает строкой из `env` разводки хука; не задано — пустая строка."""
    assert core.wants_core_everywhere({"MAST_ALWAYS_CORE": "true"})
    assert core.wants_core_everywhere({"MAST_ALWAYS_CORE": " True "})
    assert core.wants_core_everywhere({"MAST_ALWAYS_CORE": "1"})
    assert not core.wants_core_everywhere({"MAST_ALWAYS_CORE": "false"})
    assert not core.wants_core_everywhere({"MAST_ALWAYS_CORE": ""})
    assert not core.wants_core_everywhere({})


def test_с_настройкой_ядро_приезжает_и_в_неразвёрнутый_проект(tmp_path):
    """Правила про план, записи и параллельные сессии нужны и там, где роадмапа нет;
    подсказка при этом остаётся — иначе непонятно, почему каркаса не видно."""
    out = core.render(tmp_path, ROOT, "ru", always=True)
    assert "/mast-ru:init-project" in out
    assert "## Планирование" in out
    assert out.endswith((ROOT / "locales/ru/core.md").read_text(encoding="utf-8"))


def test_без_настройки_в_неразвёрнутом_проекте_только_подсказка(tmp_path):
    assert core.render(tmp_path, ROOT, "ru", always=False) == core.render(tmp_path, ROOT, "ru")


def test_в_развёрнутом_проекте_настройка_ничего_не_меняет(tmp_path):
    (tmp_path / "ROADMAP.md").write_text("- **A-1** что-то\n")
    core_md = (ROOT / "locales/ru/core.md").read_text(encoding="utf-8")
    assert core.render(tmp_path, ROOT, "ru", always=True) == core_md
    assert core.render(tmp_path, ROOT, "ru", always=False) == core_md


def test_нечитаемое_ядро_возвращает_сообщение_а_не_падает(tmp_path):
    (tmp_path / "ROADMAP.md").write_text("- **A-1** что-то\n")
    missing_root = tmp_path / "no-such-plugin-root"
    out = core.render(tmp_path, missing_root, "ru")
    assert "MAST: не удалось прочитать ядро" in out
    assert str(missing_root) in out


def test_битая_кодировка_ядра_возвращает_сообщение_а_не_падает(tmp_path):
    """Повреждённая установка плагина: файл ядра есть, но читается не как UTF-8."""
    (tmp_path / "ROADMAP.md").write_text("- **A-1** что-то\n", encoding="utf-8")
    root = tmp_path / "plugin"
    core_md = root / "locales" / "ru" / "core.md"
    core_md.parent.mkdir(parents=True)
    core_md.write_bytes(b"\xff\xfe\x00\x01 no utf-8 here")
    assert "MAST: не удалось прочитать ядро" in core.render(tmp_path, root, "ru")


def test_удалённый_cwd_не_роняет_старт_сессии(tmp_path):
    """Worktree снесли после мерджа, а cwd процесса остался на нём: `os.getcwd()`
    бросает, и хук не имеет права падать из-за этого."""
    victim = tmp_path / "worktree"
    victim.mkdir()
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp_path), CLAUDE_PLUGIN_ROOT=str(ROOT))
    script = (f'cd "{victim}" && rmdir "{victim}" && '
              f'exec "{sys.executable}" "{ROOT / "hooks" / "core.py"}"')
    result = subprocess.run(["bash", "-c", script], env=env,
                            capture_output=True, cwd=str(tmp_path))
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    assert core.project_dir({}) is not None      # без переменной тоже не бросает


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
