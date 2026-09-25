"""Живой замер горячего часа: настоящая `--bg` сессия пункта, `mast merge` с настоящим
ревьюером, вопрос через `claude attach` в пределах часа и командой из `mast status` после часа.

Обычный `pytest` файл пропускает: платно (`sonnet` у сессии, `opus` у ревьюера).

  MAST_LIVE=1 MAST_BIN=<bin/mast установленного плагина> python3 -m pytest tests/test_hot_hour_live.py -v -s

`MAST_BIN` — `mast` из кэша плагина, поставленного через `tools/serve_marketplace.py`
(`--scope local` в каталоге проекта); без него — `plugins/ru/bin/mast` этого дерева.
Каталог проекта — `MAST_LIVE_DIR` (по умолчанию `/private/tmp/mast-check-new`): `claude --bg`
доверяет только точному корню git, поэтому каталог — доверенный путь, и репозитория в нём ещё нет.
`MAST_LIVE_HOUR=wait` — ждать час по-настоящему (больше часа прогона); по умолчанию час
сымитирован: последнее сообщение сессии сдвигается на 61 мин назад — решение человека
25.09, команда вопроса от кэша не зависит.
"""
import json
import os
import pty
import re
import select
import shlex
import signal
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MAST = os.environ.get("MAST_BIN") or str(ROOT / "plugins" / "ru" / "bin" / "mast")
DIR = Path(os.environ.get("MAST_LIVE_DIR", "/private/tmp/mast-check-new"))
WAIT = os.environ.get("MAST_LIVE_HOUR") == "wait"
WORD = "СИРЕНЬ-42"
CRIT = "файл probe/done.txt есть — 1 из 1."
ROADMAP = f"""# Роадмап

## X. Проба

- **X-1** Проба горячего часа — 🔨 в работе · `worktree-X-1` · сессия `X-1` · с 25.09
  Мои пути: probe/**
  Готово когда: {CRIT}
"""
READY = f"""[X-1] готов

Готово когда: {CRIT}
Замер: файла нет → есть, python3 -m pytest probe/test_done.py.

Тезис: Проба пишет probe/done.txt: 0 → 1 файл.

Справка:
- сделано: файл probe/done.txt и тест на него.
- для пользователя: ничего, это проба.
- проверить глазами: probe/done.txt не пустой.
"""
MISMATCH = re.compile(r"^(X-\d+ брошен|сирота|лишняя)", re.M)

pytestmark = pytest.mark.skipif(os.environ.get("MAST_LIVE") != "1", reason="живой замер — MAST_LIVE=1")


def sh(*args, cwd=DIR, check=True):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    assert r.returncode == 0 or not check, f"{args}: {r.stdout}{r.stderr}"
    return r.stdout


def agent(name):
    return next((a for a in json.loads(sh("claude", "agents", "--json", "--all"))
                 if a.get("name") == name and os.path.realpath(a.get("cwd", "")).startswith(str(DIR.resolve()))), None)


def transcript(sid):
    return next((Path.home() / ".claude" / "projects").glob(f"*/{sid}.jsonl"))


def usage(sid):
    """usage последнего ответа сессии из её транскрипта."""
    entries = [json.loads(line) for line in transcript(sid).read_text(encoding="utf-8").splitlines() if line.strip()]
    return [e["message"]["usage"] for e in entries if e.get("type") == "assistant"][-1]


def drive(cmd, question, expect, leave, timeout=120):
    """Команда в псевдотерминале: набрать вопрос, ждать `expect` на экране, выйти `leave`."""
    pid, fd = pty.fork()
    if pid == 0:
        os.chdir(DIR)
        os.environ["TERM"] = "xterm-256color"
        os.execvp(cmd[0], cmd)
    screen, deadline = b"", time.time() + timeout

    def pump(until):
        nonlocal screen
        while time.time() < until:
            if select.select([fd], [], [], 0.2)[0]:
                try:
                    screen += os.read(fd, 65536)
                except OSError:
                    return
            if expect.encode() in screen:
                return

    pump(time.time() + 8)
    for ch in question:
        os.write(fd, ch.encode())
        time.sleep(0.02)
    time.sleep(0.5)
    os.write(fd, b"\r")
    pump(deadline)
    os.write(fd, leave)
    time.sleep(3)
    os.kill(pid, signal.SIGKILL)
    # Убитый процесс не выйдет, пока его вывод в терминал некому читать
    os.close(fd)
    os.waitpid(pid, 0)
    return re.sub(r"\x1b\[[0-9;?<>]*[A-Za-z]", "", screen.decode("utf-8", "replace"))


@pytest.fixture
def project():
    """Проект в доверенном каталоге. В нём уже может лежать `.claude/` установки плагина
    `--scope local`; каталог после пробы остаётся — плагин снимается из него же по CLAUDE.md."""
    assert not (DIR / ".git").exists(), f"{DIR} уже репозиторий — проба берёт чистый доверенный каталог"
    (DIR / "docs" / "roadmap").mkdir(parents=True, exist_ok=True)
    (DIR / "ROADMAP.md").write_text(ROADMAP, encoding="utf-8")
    (DIR / "docs" / "roadmap" / "DONE.md").write_text("# Закрытые пункты\n", encoding="utf-8")
    (DIR / ".gitignore").write_text(".claude/\n")
    sh("git", "init", "-q", "-b", "main")
    sh("git", "add", ".")
    sh("git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")
    yield DIR
    # Удалённого у пробы нет: `claude rm` просит подтвердить потерю коммитов — проба их не хранит
    for a in json.loads(sh("claude", "agents", "--json", "--all")):
        if a.get("id") and os.path.realpath(a.get("cwd", "")).startswith(str(DIR.resolve())):
            r = subprocess.run(["claude", "rm", a["id"]], capture_output=True, text=True)
            token = re.search(r"--discard-unpushed (\S+)", r.stdout + r.stderr)
            if r.returncode and token:
                sh("claude", "rm", a["id"], "--discard-unpushed", token.group(1), check=False)


def test_горячий_час_и_вопрос_после(project):
    out = sh("claude", "--bg", "--worktree", "X-1", "--name", "X-1", "--model", "sonnet",
             "--settings", '{"worktree":{"baseRef":"head"}}',
             f"Ты сессия пункта X-1. Пароль пункта — {WORD}, запомни его. Файлов не трогай, "
             "инструментов не запускай. Ответь одним словом: готов.")
    sid = re.search(r"claude attach (\w+)", re.sub(r"\x1b\[[0-9;]*m", "", out)).group(1)
    for _ in range(90):
        a = agent("X-1")
        if a and a.get("state") == "done":
            break
        time.sleep(2)
    wt = DIR / ".claude" / "worktrees" / "X-1"
    (wt / "probe").mkdir()
    (wt / "probe" / "done.txt").write_text("проба\n", encoding="utf-8")
    (wt / "probe" / "test_done.py").write_text(
        "from pathlib import Path\n\n\ndef test_done():\n"
        "    assert Path(__file__).with_name('done.txt').read_text().strip()\n", encoding="utf-8")
    sh("git", "add", ".", cwd=wt)
    sh("git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", READY, cwd=wt)

    merged = sh(MAST, "merge", "X-1", "--no-push")
    print(merged)
    assert f"claude attach {sid}" in merged

    status = sh(MAST, "status")
    print(status)
    assert re.search(rf"^X-1 закрыт, сессия открыта до \d\d:\d\d — `claude attach {sid}`", status, re.M), status
    assert not MISMATCH.search(status), status

    # В пределах часа: вопрос через attach читается из кэша. На экране ждём фрагмент:
    # модель может переставить цифры, а буквы задом наперёд — только из ответа
    word = "ЬНЕРИС"
    screen = drive(["claude", "attach", sid], "Напиши пароль пункта задом наперёд, одним словом.", word, b"\x1a")
    u = usage(agent("X-1")["sessionId"])
    context = u["input_tokens"] + u["cache_creation_input_tokens"] + u["cache_read_input_tokens"]
    print(f"attach: кэш {u['cache_read_input_tokens']} из {context} "
          f"({u['cache_read_input_tokens'] / context:.1%})")
    assert word in screen, screen[-2000:]
    assert u["cache_read_input_tokens"] >= 0.9 * context

    # После часа: команда ровно из `mast status`. Форк показывает историю с ответом выше,
    # поэтому вопрос другой — строчными буквами
    if WAIT:
        time.sleep(61 * 60)
    else:
        when = time.time() - 61 * 60
        os.utime(transcript(agent("X-1")["sessionId"]), (when, when))
    status = sh(MAST, "status")
    print(status)
    cmd = re.search(r"^X-1 закрыт, час прошёл — вопрос: `([^`]+)`", status, re.M).group(1)
    word = "сирень"
    screen = drive(shlex.split(cmd), "Напиши пароль пункта строчными буквами, одним словом.", word, b"/exit\r")
    assert word in screen, screen[-2000:]

    status = sh(MAST, "status")
    print(status)
    assert not MISMATCH.search(status), status
