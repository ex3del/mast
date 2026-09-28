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


@pytest.mark.parametrize("lang", ["ru", "en"])
def test_шаблон_настроек_прода_не_объявляет(tmp_path, lang):
    """`/init-project` кладёт шаблон как есть: его проза не должна стать строкой `Прод:`."""
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "mast.md").write_bytes(
        (ROOT / "plugins" / lang / "locales" / lang / "templates" / "mast.template.md").read_bytes())
    assert prod.patterns(tmp_path) == []


def test_powershell_env():
    assert prod.hit('$env:DOCKER_CONTEXT = "prod-vps"; docker ps', [], Path.cwd())
    assert prod.hit("$env:DOCKER_HOST='ssh://train-box'\ndocker ps", [], Path.cwd())
    assert prod.hit('$env:PATH = "C:\\bin"; docker ps', [], Path.cwd()) is None


sys.path.insert(0, str(ROOT / "tools"))
from hook_overhead import fired  # noqa: E402

WORDS = ("git", "ssh", "docker", "clearml*", "bash")


@pytest.mark.parametrize("command,expected", [
    # живой замер 28.09, Claude Code 2.1.283: хук-логгер на `Bash(<слово> *)`
    ("DOCKER_CONTEXT=x docker ps", {"docker"}),
    ("DOCKER_CONTEXT=x python3 -c 1", set()),
    ("clearml-task --version", {"clearml*"}),
    ("git status && ssh -G h", {"git", "ssh"}),
    ("timeout 1 ssh -G h", set()),
    ("echo $(ssh -G h)", {"ssh"}),
    ("cd /tmp && ssh -G h", {"ssh"}),
    ("/usr/bin/ssh -G h", set()),
    ("bash <<'EOF'\necho hi\nEOF", {"bash"}),
    ("env DOCKER_CONTEXT=x docker ps", set()),
    ("docker --context x ps", {"docker"}),
    ("ls", set()),
    ("export DOCKER_CONTEXT=x && docker ps", {"docker"}),
    ("(ssh -G h)", {"ssh"}),
    ("for h in a b; do ssh -G $h; done", set(WORDS)),
    ("if ssh -G h >/dev/null; then echo y; fi", {"ssh"}),
    ("while false; do ssh -G h; done", {"ssh"}),
    ("$SHELL -c 'echo x'", set(WORDS)),
    ('x=$(ssh -G h) && echo "$x"', set(WORDS)),
    ("cat > /tmp/a26-x.sh <<'EOF'\nssh -G h\nEOF", set()),
    ("ls | xargs echo", set()),
    ("echo hi > /dev/null && ls", set()),
    ("case x in x) ssh -G h;; esac", set(WORDS)),
    ("f() { ssh -G h; }; f", set(WORDS)),
    ('ls && echo "$(date)"', set(WORDS)),
    ('echo "$(date)"', set()),
    ('echo "$HOME"', set()),
    ("echo $HOME", set()),
    ("ssh -G $HOME", {"ssh"}),
    ("x=$(date)", set()),
    ('git log --format="%h"', {"git"}),
    ("for h in a b; do echo $h; done", set(WORDS)),
    ("echo `date`", set()),
    ('echo "`date`"', set()),
    ('python3 -c "print(1)"', set()),
    ('grep -n "foo" bar.txt | head -5', set()),
    ("echo '$(date)'", set()),
])
def test_эмуляция_фильтра_по_живому_замеру(command, expected):
    assert fired(command, WORDS) == expected


def watch(tmp_path, command, lang="ru", role=None, tool="Bash", **extra):
    """PreToolUse через `roadmap_watch.py` — так, как его зовёт площадка по фильтру `if`."""
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(tmp_path), "CLAUDE_PLUGIN_DATA": str(tmp_path / "data")}
    env.pop("MAST_ROLE", None)
    if role == "env":
        env["MAST_ROLE"] = "dispatcher"
    elif role == "file":
        (tmp_path / "data").mkdir(exist_ok=True)
        (tmp_path / "data" / "s1.role").touch()
    payload = {"session_id": "s1", "transcript_path": str(tmp_path / "s1.jsonl"), "cwd": str(tmp_path),
               "hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": {"command": command}, **extra}
    return subprocess.run([sys.executable, str(ROOT / "hooks" / "roadmap_watch.py"), lang],
                          input=json.dumps(payload).encode(), capture_output=True, env=env)


@pytest.mark.parametrize("role", ["env", "file"])
@pytest.mark.parametrize("tool", ["Bash", "PowerShell"])
def test_диспетчеру_отказ(tmp_path, role, tool):
    r = watch(tmp_path, "cd /opt && ssh train-box uptime", role=role, tool=tool)
    assert r.returncode == 2
    assert "диспетчер не ходит на прод — `ssh train-box uptime`" in r.stderr.decode()


def test_отказ_на_языке_плагина(tmp_path):
    r = watch(tmp_path, "ssh train-box uptime", lang="en", role="env")
    assert r.returncode == 2 and "the dispatcher doesn't go to prod" in r.stderr.decode()


@pytest.mark.parametrize("role,command,extra", [
    ("env", "ssh train-box uptime", {"agent_id": "a1", "agent_type": "general-purpose"}),  # субагент
    (None, "ssh train-box uptime", {}),  # сессия пункта или без роли
    ("env", "git status && docker ps", {}),
])
def test_пропуск(tmp_path, role, command, extra):
    r = watch(tmp_path, command, role=role, **extra)
    assert (r.returncode, r.stdout, r.stderr) == (0, b"", b"")


def test_шаблон_из_настроек_проекта(tmp_path):
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "mast.md").write_text("Прод: curl api.telegram.org\n", encoding="utf-8")
    assert watch(tmp_path, 'curl -s "https://api.telegram.org/x"', role="env").returncode == 2
    assert watch(tmp_path, "curl -s https://example.com", role="env").returncode == 0
