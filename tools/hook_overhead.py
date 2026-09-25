#!/usr/bin/env python3
"""Накладные хуков парно (A-24): прежние и текущие вперемешку.

  python3 tools/hook_overhead.py [ревизия прежних хуков, по умолчанию HEAD] [N, по умолчанию 60]

Прежние — `hooks/` из ревизии во временном каталоге, текущие — `hooks/` рабочего дерева,
порядок в паре случайный. Два входа, как на каждом вызове инструмента в проекте с
`ROADMAP.md`: PostToolUse обычного Bash (`ls`) в `roadmap_watch.py` — отпечаток роадмапа уже
записан, — и PreToolUse Edit обычного файла в `dispatcher.py` у сессии без роли. python3 из
PATH, как у площадки.
Абсолютное время зависит от машины, сравнивается разница медиан (правило `.claude/rules/hooks.md`).
"""
import json
import os
import random
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    rev = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    python = shutil.which("python3")
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
        times = {(c, v): [] for c in cases for v in ("прежний", "текущий")}
        for i in range(n + 10):
            for case, payload in cases.items():
                script = case.split(",")[0]
                pair = [("прежний", old / script), ("текущий", ROOT / "hooks" / script)]
                random.shuffle(pair)  # первый в паре стабильно медленнее на ~0,2 мс
                for version, hook in pair:
                    t = time.perf_counter()
                    r = subprocess.run([python, str(hook), "ru"], input=json.dumps(payload).encode(),
                                       capture_output=True, env=env)
                    ms = (time.perf_counter() - t) * 1000
                    assert r.returncode == 0 and not r.stdout and not r.stderr, (case, version, r)
                    if i >= 10:  # первые 10 — прогрев
                        times[case, version].append(ms)
    for case in cases:
        a, b = (statistics.median(times[case, v]) for v in ("прежний", "текущий"))
        print(f"{case}: прежний ({rev}) {a:.2f} мс, текущий {b:.2f} мс, разница {b - a:+.2f} мс, N={n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
