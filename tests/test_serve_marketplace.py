"""Локальный git-маркетплейс: shallow-клон по smart HTTP, занятое имя, snapshot/compare."""
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "serve_marketplace.py"
sys.path.insert(0, str(ROOT / "tools"))
import serve_marketplace  # noqa: E402


def run(*args, **kw):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
                          timeout=30, **kw)


def test_shallow_клон_по_smart_http(tmp_path):
    """Площадка клонирует маркетплейс с --depth 1: dumb HTTP так не умеет, нужен smart."""
    src = tmp_path / "src"
    (src / "plugins/ru/.claude-plugin").mkdir(parents=True)
    (src / "plugins/ru/.claude-plugin/plugin.json").write_text('{"name": "mast-ru"}\n')
    (src / ".claude-plugin").mkdir()
    (src / ".claude-plugin/marketplace.json").write_text(
        '{"name": "ex3del", "plugins": [{"name": "mast-ru", "source": "./plugins/ru"}]}\n')
    server = serve_marketplace.start(src, "mast-local", tmp_path / "srv", 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    clone = tmp_path / "clone"
    try:
        subprocess.run(["git", "clone", "-q", "--depth", "1",
                        f"http://127.0.0.1:{server.server_address[1]}/mast-local.git", str(clone)],
                       check=True, timeout=30)
    finally:
        server.shutdown()
        server.server_close()
    assert (clone / ".git/shallow").is_file()
    assert (clone / "plugins/ru/.claude-plugin/plugin.json").is_file()
    assert json.loads((clone / ".claude-plugin/marketplace.json").read_text())["name"] == "mast-local"


def test_имя_маркетплейса_с_github_занято():
    out = run("--name", "ex3del")
    assert out.returncode == 1 and "ex3del занято" in out.stderr


def test_snapshot_и_compare(tmp_path):
    """Отсутствующий файл — тоже состояние: появился после снимка — отличие."""
    claude = tmp_path / "home/.claude"
    (claude / "plugins").mkdir(parents=True)
    (claude / "settings.json").write_text("{}\n")
    env = dict(os.environ, HOME=str(tmp_path / "home"))
    snap = str(tmp_path / "snap")
    assert run("snapshot", snap, env=env).returncode == 0
    out = run("compare", snap, env=env)
    assert (out.returncode, out.stdout.splitlines()[-1]) == (0, "Отличий: 0")

    (claude / "settings.json").write_text('{"enabledPlugins": {}}')  # площадка пишет без \n
    (claude / "plugins/installed_plugins.json").write_text("{}\n")
    out = run("compare", snap, env=env)
    assert out.returncode == 1 and out.stdout.splitlines()[-1] == "Отличий: 2"
    assert '+{"enabledPlugins": {}}' in out.stdout
