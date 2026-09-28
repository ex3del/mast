"""Прод-команды у диспетчера (A-26): разбор команды `hooks/prod.py` и отказ основному потоку
`*-dispatch` через `roadmap_watch.py` — так, как его зовёт площадка."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "hooks"))
import prod  # noqa: E402

PATS = [["curl", "api.telegram.org"], ["clearml-task", "--project", "mnist"], ["DOCKER_CONTEXT=prod-vps"],
        ["python", "scripts/launch_train.py"]]


@pytest.mark.parametrize("command", [
    "ssh train-box uptime",
    "cd /opt && ssh -p 2222 root@train-box 'git pull --ff-only'",
    "echo $(ssh train-box cat /etc/hostname)",
    "timeout 30 ssh train-box true",
    "scp model.pt train-box:/models/",
    "rsync -avz ./data/ train-box:/data/",
    "aws s3 cp s3://ml-datasets/x.csv .",
    "aws --profile ml s3 ls",
    "mc cp local/x minio/bucket/x",
    "rclone copy remote:bucket ./x",
    "lakectl fs ls lakefs://repo/main/",
    "clearml-task --project mnist --script train.py",
    "kubectl get pods",
    "dvc push",
    "docker --context prod-vps ps",
    "docker -H ssh://train-box compose up -d",
    "DOCKER_CONTEXT=prod-vps docker compose up -d",
    "DOCKER_CONTEXT=reinhold-vps python3 scripts/e2e-test-runner.py",
    "export DOCKER_CONTEXT=prod-vps && docker ps",
    "for h in a b; do ssh $h true; done",
    "if ssh train-box test -f /x; then echo ok; fi",
])
def test_базовый_список_прод(command):
    assert prod.hit(command, [], Path.cwd())


@pytest.mark.parametrize("command", [
    "ssh -G train-box",
    "ssh -V",
    "rsync -a ./a/ ./b/",
    "docker ps",
    "docker compose up -d",
    "docker --context default ps",
    "docker context use prod-vps",
    "DOCKER_CONTEXT=prod-vps docker compose config",
    "aws sts get-caller-identity",
    "dvc status",
    "mc --version",
    'git commit -m "ssh train-box: выкладка, docker --context prod-vps"',
    "echo ssh train-box",
    "grep -rn 'ssh train-box' docs/",
    "git log --oneline -5",
    "curl -s http://localhost:8000/health",
    "ssh-keygen -lf key.pub",
    "git commit -F - <<'EOF'\n[A-1] ssh train-box и aws s3 cp\nEOF",
])
def test_не_прод(command):
    assert prod.hit(command, [], Path.cwd()) is None


@pytest.mark.parametrize("command", [
    "bash <<'SH'\ncd /opt\nssh train-box uptime\nSH",
    'bash -c "ssh train-box uptime"',
    "cat > /tmp/d.sh <<'EOF'\nssh train-box 'git pull'\nEOF\nbash /tmp/d.sh",
])
def test_тело_оболочки_разбирается(command):
    assert prod.hit(command, [], Path.cwd())


def test_файл_из_bash_читается_с_диска(tmp_path):
    (tmp_path / "deploy.sh").write_text("#!/bin/sh\nset -e\nssh train-box 'git pull --ff-only'\n")
    (tmp_path / "local.sh").write_text("pytest -q\n")
    assert prod.hit("bash deploy.sh", [], tmp_path)
    assert prod.hit("sh -e ./deploy.sh", [], tmp_path)
    assert prod.hit("bash local.sh", [], tmp_path) is None
    assert prod.hit("bash missing.sh", [], tmp_path) is None


@pytest.mark.parametrize("command,expected", [
    ('curl -s "https://api.telegram.org/bot<T>/getMe"', True),
    ("curl -s https://example.com", False),
    ("clearml-task --name exp1 --project mnist --script train.py", True),
    ("clearml-task --project cifar", True),  # базовый список: clearml-* — прод и без шаблона
    ("DOCKER_CONTEXT=prod-vps make deploy", True),
    ("python scripts/launch_train.py --epochs 3", True),
    ("python3 scripts/launch_train.py", False),
    ("echo python scripts/launch_train.py", False),
])
def test_шаблоны_прод(command, expected):
    assert bool(prod.hit(command, PATS, Path.cwd())) is expected


def test_шаблоны_из_настроек(tmp_path):
    assert prod.patterns(tmp_path) == []
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "mast.md").write_text(
        "# Настройки MAST\n\nНастройка — ключ `Прод` и шаблоны через запятую.\nПорог тишины: 30 мин\n\n"
        "Прод: ssh train-box, aws s3 cp s3://ml-datasets\nProd:`clearml-task --project mnist` ,\n",
        encoding="utf-8")
    assert prod.patterns(tmp_path) == [["ssh", "train-box"], ["aws", "s3", "cp", "s3://ml-datasets"],
                                       ["clearml-task", "--project", "mnist"]]


def test_powershell_env():
    assert prod.hit('$env:DOCKER_CONTEXT = "prod-vps"; docker ps', [], Path.cwd())
    assert prod.hit("$env:DOCKER_HOST='ssh://train-box'\ndocker ps", [], Path.cwd())
    assert prod.hit('$env:PATH = "C:\\bin"; docker ps', [], Path.cwd()) is None
