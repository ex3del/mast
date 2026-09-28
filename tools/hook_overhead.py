#!/usr/bin/env python3
"""Накладные хуков парно (A-24): прежние и текущие вперемешку.

  python3 tools/hook_overhead.py [ревизия прежних хуков, по умолчанию HEAD] [N, по умолчанию 60] [--mix ПУТЬ]

Прежние — `hooks/` из ревизии во временном каталоге, текущие — `hooks/` рабочего дерева,
порядок в паре случайный. Два входа, как на каждом вызове инструмента в проекте с
`ROADMAP.md`: PostToolUse обычного Bash (`ls`) в `roadmap_watch.py` — отпечаток роадмапа уже
записан, — и PreToolUse Edit обычного файла в `dispatcher.py` у сессии без роли. python3 из
PATH, как у площадки.
Абсолютное время зависит от машины, сравнивается разница медиан (правило `.claude/rules/hooks.md`).

`--mix` (A-26) — среднее на вызов Bash у сессии без роли по смеси команд: файл фикстуры
(`{"command": …}` в строке) или каталог транскриптов (`~/.claude/projects`). На команду —
PostToolUse и столько PreToolUse `roadmap_watch.py` разом, сколько обработчиков позовёт фильтр
`if` (`fired`) при прежней разводке (`git`) и текущей (`git` и `prod.FILTER`). Печатаются
только доли и времена, команды — нет.
"""
import json
import os
import random
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "hooks"))
import prod  # noqa: E402

# Фильтр `if` площадки по живому замеру 28.09 (Claude Code 2.1.283): все обработчики — на `for`,
# `case`, функции, `$VAR` вместо команды и на составной команде с подстановкой `$(…)`/`` `…` ``
# в двойных кавычках или присваиванием `=$(`; иначе — слово каждой подкоманды после
# присваиваний окружения и `if`/`while`, обёртки (`timeout`, `env`) не снимаются
ALL = re.compile(r"(?:^|[\s;&|(])(?:for|case|select)\s|\w\s*\(\)\s*\{")
QUOTED_SUB = re.compile(r"\"(?:\\.|[^\"\\])*?(?:\$\(|`)")


def fired(command, words):
    """Слова фильтра, чьи обработчики площадка позовёт на эту команду Bash."""
    main = prod.split_heredocs(command.replace("\\\n", " "))[0]
    masked = prod.QUOTE.sub(lambda m: m[0][0] + "\0" * (len(m[0]) - 2) + m[0][-1], main)
    compound = re.search(r"&&|\|\||[;|\n]", masked.strip())
    if ALL.search(masked) or compound and (QUOTED_SUB.search(main) or re.search(r"\w=\$\(", main)):
        return set(words)
    out = set()
    for seg in prod.SEP.split(masked):
        toks = seg.split()
        while toks and (prod.ENV.match(toks[0]) or toks[0] in ("if", "while", "until", "!")):
            toks.pop(0)
        if toks and toks[0].startswith("$"):
            return set(words)
        if toks:
            out |= {w for w in words if toks[0] == w or w.endswith("*") and toks[0].startswith(w[:-1])}
    return out


def commands(path):
    """Команды Bash из файла фикстуры или из транскриптов каталога (с субагентами)."""
    path = Path(path).expanduser()
    if path.is_file():
        return [json.loads(line)["command"] for line in path.read_text(encoding="utf-8").splitlines() if line]
    out = []
    for f in path.rglob("*.jsonl"):
        for line in f.open(encoding="utf-8", errors="replace"):
            if '"Bash"' not in line:
                continue
            try:
                message = json.loads(line).get("message")
            except (ValueError, AttributeError):
                continue
            content = message.get("content") if isinstance(message, dict) else None
            if isinstance(content, list):
                out += [(c.get("input") or {}).get("command", "") for c in content if isinstance(c, dict)
                        and c.get("type") == "tool_use" and c.get("name") == "Bash"]
    return out


def run(python, hook, payload, env, k):
    """Стена k одновременных запусков хука, мс: площадка зовёт совпавшие обработчики разом."""
    t = time.perf_counter()
    ps = [subprocess.Popen([python, str(hook), "ru"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, env=env) for _ in range(k)]
    for p in ps:
        out, err = p.communicate(payload)
        assert p.returncode == 0 and not out and not err, (hook, out, err)
    return (time.perf_counter() - t) * 1000


def main():
    args = sys.argv[1:]
    mix = args.pop(args.index("--mix") + 1) if "--mix" in args else None
    args = [a for a in args if a != "--mix"]
    rev = args[0] if args else "HEAD"
    n = int(args[1]) if len(args) > 1 else 60
    python = shutil.which("python3")
    shares = {}
    if mix:
        cmds = commands(mix)
        # Прежняя и текущая разводка и два варианта на выбор человеку: фильтр на минимум слов и
        # один обработчик без `if` — хук на каждую команду
        for version, words in (("прежний", ("git",)), ("текущий", ("git", *prod.FILTER)),
                               ("минимум слов", ("git", "ssh", "docker", "aws", "bash", "curl")),
                               ("без фильтра", None)):
            k = Counter(len(fired(c, words)) if words else 1 for c in cmds)
            shares[version] = {x: v / len(cmds) for x, v in k.items()}
            print(f"смесь {len(cmds)} команд Bash, {version}: доля команд по числу обработчиков PreToolUse — "
                  + ", ".join(f"{x}: {100 * v:.1f}%" for x, v in sorted(shares[version].items())))
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        old = tmp / "old"
        old.mkdir()
        files = subprocess.run(["git", "-C", str(ROOT), "ls-tree", "--name-only", rev, "hooks/"],
                               capture_output=True, text=True, check=True).stdout.split()
        for f in files:
            (old / Path(f).name).write_bytes(
                subprocess.run(["git", "-C", str(ROOT), "show", f"{rev}:{f}"], capture_output=True, check=True).stdout)
        project = tmp / "project"
        project.mkdir()
        (project / "ROADMAP.md").write_text("# ROADMAP\n", encoding="utf-8")
        env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project), "CLAUDE_PLUGIN_DATA": str(tmp / "data")}
        env.pop("MAST_ROLE", None)
        common = {"session_id": "s", "transcript_path": str(tmp / "s.jsonl"), "cwd": str(project)}
        cases = {
            "roadmap_watch.py, Bash": {**common, "hook_event_name": "PostToolUse", "tool_name": "Bash",
                                       "tool_input": {"command": "ls"},
                                       "tool_response": {"stdout": "ROADMAP.md", "stderr": "", "interrupted": False}},
            "dispatcher.py, Edit": {**common, "hook_event_name": "PreToolUse", "tool_name": "Edit",
                                    "tool_input": {"file_path": str(project / "x.py"), "old_string": "x"}},
        }
        pre = json.dumps({**common, "hook_event_name": "PreToolUse", "tool_name": "Bash",
                          "tool_input": {"command": "ssh train-box uptime"}}).encode()
        parallel = sorted({k for s in shares.values() for k in s if k})
        times = {(c, v): [] for c in [*cases, *parallel] for v in ("прежний", "текущий")}
        for i in range(n + 10):
            for case in [*cases, *parallel]:
                script = "roadmap_watch.py" if case in parallel else case.split(",")[0]
                pair = [("прежний", old / script), ("текущий", ROOT / "hooks" / script)]
                random.shuffle(pair)  # первый в паре стабильно медленнее на ~0,2 мс
                for version, hook in pair:
                    payload = pre if case in parallel else json.dumps(cases[case]).encode()
                    ms = run(python, hook, payload, env, case if case in parallel else 1)
                    if i >= 10:  # первые 10 — прогрев
                        times[case, version].append(ms)
    med = {key: statistics.median(v) for key, v in times.items()}
    for case in cases:
        a, b = med[case, "прежний"], med[case, "текущий"]
        print(f"{case}: прежний ({rev}) {a:.2f} мс, текущий {b:.2f} мс, разница {b - a:+.2f} мс, N={n}")
    for k in parallel:
        print(f"PreToolUse Bash, {k} обработчиков разом: прежний {med[k, 'прежний']:.2f} мс, "
              f"текущий {med[k, 'текущий']:.2f} мс")
    for version, share in shares.items():
        hooks = "прежний" if version == "прежний" else "текущий"  # варианты — на текущих хуках
        avg = med["roadmap_watch.py, Bash", hooks] + sum(p * med[k, hooks] for k, p in share.items() if k)
        print(f"в среднем на вызов Bash, разводка «{version}»: {avg:.2f} мс")
    return 0


if __name__ == "__main__":
    sys.exit(main())
