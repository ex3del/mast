"""Проверка бампа для CI — на настоящем временном репозитории, а не на моках."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import check_version_bump as cvb  # noqa: E402


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def write(repo, rel, text):
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def set_version(repo, v):
    write(repo, cvb.MANIFEST, json.dumps({"name": "mast", "version": v}))


@pytest.fixture
def repo(tmp_path, monkeypatch):
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "user.email", "t@t")
    git(tmp_path, "config", "user.name", "t")
    set_version(tmp_path, "3.9.0")
    write(tmp_path, "locales/ru/core.md", "ядро")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "база")
    git(tmp_path, "branch", "base")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def commit(repo, msg):
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", msg)


def test_правка_метода_без_бампа_отклоняется(repo):
    write(repo, "locales/ru/core.md", "новое ядро")
    commit(repo, "правка без бампа")
    assert "не выросла" in cvb.check("base")


def test_правка_метода_с_бампом_проходит(repo):
    write(repo, "locales/ru/core.md", "новое ядро")
    set_version(repo, "3.10.0")                 # 3.10 > 3.9 — сравнение чисел, не строк
    commit(repo, "правка с бампом")
    assert cvb.check("base") is None


def test_понижение_версии_отклоняется(repo):
    write(repo, "hooks/core.py", "print()")
    set_version(repo, "3.8.0")
    commit(repo, "откат версии")
    assert cvb.check("base") is not None


def test_правка_вне_метода_бампа_не_требует(repo):
    write(repo, "README.md", "текст")
    commit(repo, "только README")
    assert cvb.check("base") is None
