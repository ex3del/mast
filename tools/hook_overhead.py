#!/usr/bin/env python3
"""Накладные хука Bash парно (A-24): прежний `roadmap_watch.py` и текущий вперемешку.

  python3 tools/hook_overhead.py [ревизия прежнего хука, по умолчанию HEAD] [N, по умолчанию 60]

Прежний — `hooks/` из ревизии во временном каталоге, текущий — `hooks/` рабочего дерева.
Вход — PostToolUse обычного Bash (`ls`) в проекте с `ROADMAP.md`, отпечаток роадмапа уже
записан: так хук отрабатывает на каждом Bash диспетчера. python3 из PATH, как у площадки.
Абсолютное время зависит от машины, сравнивается разница медиан (правило `.claude/rules/hooks.md`).
"""
import json
import os
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
        payload = json.dumps({
            "session_id": "s", "transcript_path": str(tmp / "s.jsonl"), "cwd": str(project),
            "hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": "ls"},
            "tool_response": {"stdout": "ROADMAP.md", "stderr": "", "interrupted": False},
        }).encode()
        hooks = {"прежний": old / "roadmap_watch.py", "текущий": ROOT / "hooks" / "roadmap_watch.py"}
        times = {k: [] for k in hooks}
        for i in range(n + 10):
            for name, hook in hooks.items():
                t = time.perf_counter()
                r = subprocess.run([python, str(hook), "ru"], input=payload, capture_output=True, env=env)
                ms = (time.perf_counter() - t) * 1000
                assert r.returncode == 0 and not r.stdout and not r.stderr, (name, r)
                if i >= 10:  # первые 10 — прогрев
                    times[name].append(ms)
    med = {k: statistics.median(v) for k, v in times.items()}
    for k, v in med.items():
        print(f"{k} ({rev if k == 'прежний' else 'рабочее дерево'}): медиана {v:.2f} мс, N={n}")
    print(f"разница: {med['текущий'] - med['прежний']:+.2f} мс")
    return 0


if __name__ == "__main__":
    sys.exit(main())
