"""Живая проверка хука прод-команд (A-26) на установленном плагине: у сессии `<проект>-dispatch`
`ssh` на хост — отказ, та же команда её субагентом — выполнена, у сессии пункта — выполнена.

Обычный `pytest` файл пропускает: платно (три сессии `claude -p` на `sonnet`).

  MAST_LIVE=1 [MAST_LIVE_DIR=<каталог>] python3 -m pytest tests/test_prod_live.py -v -s

Каталог — `MAST_LIVE_DIR` (по умолчанию `/private/tmp/mast-check-a26`): git-репозиторий с
`ROADMAP.md` и каталогом `.claude/worktrees/X-1`, в нём поставлен `mast-ru` через
`tools/serve_marketplace.py` (`--scope local`, CLAUDE.md). «Выполнена» — хук не отказал и
команда дошла до `ssh`: хоста `train-box` нет, и `ssh` сам падает на разрешении имени.
Результат вызова — из потока `--output-format stream-json`, а не из пересказа модели.
"""
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

DIR = Path(os.environ.get("MAST_LIVE_DIR", "/private/tmp/mast-check-a26"))
SSH = "ssh -o ConnectTimeout=3 -o BatchMode=yes train-box true"
REFUSED = "диспетчер не ходит на прод"
RAN = re.compile(r"Could not resolve hostname|Name or service not known|nodename nor servname")

pytestmark = pytest.mark.skipif(os.environ.get("MAST_LIVE") != "1", reason="живой замер — MAST_LIVE=1")


def bash_results(cwd, name, prompt):
    """(команда, id вызова Agent-родителя или None, текст результата) каждого Bash сессии."""
    r = subprocess.run(["claude", "-p", "--model", "sonnet", "--name", name, "--output-format", "stream-json",
                        "--verbose", "--allowedTools", "Bash(ssh *)", "Agent"],
                       cwd=cwd, input=prompt, capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, r.stderr
    calls, out = {}, []
    for line in r.stdout.splitlines():
        event = json.loads(line)
        if event.get("type") == "system" and event.get("subtype") == "init":
            print(f"[{event['session_id']}] {name}: "
                  f"{[p.get('path') for p in event.get('plugins', []) if 'mast' in str(p.get('path'))]}")
        for c in (event.get("message") or {}).get("content") or []:
            if not isinstance(c, dict):
                continue
            if c.get("type") == "tool_use" and c.get("name") == "Bash":
                calls[c["id"]] = (c["input"].get("command", ""), event.get("parent_tool_use_id"))
            elif c.get("type") == "tool_result" and c.get("tool_use_id") in calls:
                text = c.get("content")
                text = text if isinstance(text, str) else "\n".join(x.get("text", "") for x in text or [])
                out.append((*calls[c["tool_use_id"]], text))
    for command, parent, text in out:
        print(f"  {'субагент' if parent else 'основной поток'}: {command!r} → {text[:160]!r}")
    return out


def test_диспетчеру_отказ():
    out = bash_results(DIR, "mastcheck-dispatch",
                       f"Выполни ровно одну команду Bash, как есть, без повторов и изменений: `{SSH}`. "
                       "Потом ответь одним словом: готово.")
    ssh = [x for x in out if "train-box" in x[0]]
    assert len(ssh) == 1 and ssh[0][1] is None, out
    assert REFUSED in ssh[0][2] and not RAN.search(ssh[0][2]), ssh


def test_субагенту_диспетчера_пропуск():
    out = bash_results(DIR, "mastcheck-dispatch",
                       "Сам никаких команд не выполняй. Запусти одного субагента general-purpose инструментом "
                       f"Agent: пусть выполнит ровно одну команду Bash, как есть, без повторов: `{SSH}` — и "
                       "вернёт её вывод дословно. Потом ответь одним словом: готово.")
    ssh = [x for x in out if "train-box" in x[0]]
    assert ssh and all(parent for _, parent, _ in ssh), out
    assert RAN.search(ssh[0][2]) and REFUSED not in ssh[0][2], ssh


def test_сессии_пункта_пропуск():
    out = bash_results(DIR / ".claude" / "worktrees" / "X-1", "X-1",
                       f"Выполни ровно одну команду Bash, как есть, без повторов и изменений: `{SSH}`. "
                       "Потом ответь одним словом: готово.")
    ssh = [x for x in out if "train-box" in x[0]]
    assert len(ssh) == 1 and ssh[0][1] is None, out
    assert RAN.search(ssh[0][2]) and REFUSED not in ssh[0][2], ssh
