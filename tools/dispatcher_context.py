#!/usr/bin/env python3
"""Замер порога подсказки перезапуска диспетчера (A-24) по его транскриптам.

  python3 tools/dispatcher_context.py <каталог в ~/.claude/projects> ...

Берёт транскрипты сессий с именем `*-dispatch`. Контекст хода — сумма `usage` ответа
модели: `input_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens` (с советником —
последней итерации основной модели). Вливание —
успешный Bash с `mast merge X-N` или `git merge … worktree-X-N`. Сжатие — запись
`compact_boundary`: `auto` — автосжатие, `manual` — `/compact` человека.

Печатает по сессиям ходы, вливания и сжатия, прирост контекста между вливаниями и для
каждого порога — симуляцию: после вливания с контекстом выше порога человек делает
`/clear`, контекст падает до стартового. Считается, сколько было бы перезапусков, сколько
автосжатий они опередили бы и сколько входных токенов сэкономили бы.
"""
import json
import re
import statistics
import sys
from pathlib import Path

MERGE = re.compile(r"(?<![\w-])mast\s+merge\s+[A-Z]-\d+|git\b[^;&|\n]*\smerge\b[^;&|\n]*worktree-[A-Z]-\d+")
THRESHOLDS = range(100_000, 650_001, 50_000)


def context(usage):
    """С советником `usage` — сумма итераций: две итерации основной модели и одна советника,
    контекст вышел бы вдвое больше. Контекст — последняя итерация основной модели."""
    usage = ([i for i in usage.get("iterations") or [] if i.get("type") == "message"] or [usage])[-1]
    return sum(usage.get(k, 0) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))


def read(path, seen):
    """События сессии по порядку: ("turn", контекст), ("merge", контекст), ("compact", тип, preTokens).
    Ответ, уже встреченный в другом транскрипте (форк, `--resume`), не считается второй раз."""
    events, calls, ctx, failed = [], {}, {}, set()
    for line in path.open(encoding="utf-8"):
        r = json.loads(line)
        if r.get("isSidechain"):
            continue
        if r.get("subtype") == "compact_boundary" and r["uuid"] not in seen:
            seen.add(r["uuid"])
            m = r.get("compactMetadata") or {}
            events.append(("compact", m.get("trigger"), m.get("preTokens")))
        elif r.get("type") == "assistant":
            m = r["message"]
            if m["id"] not in ctx and m["id"] not in seen and m.get("usage"):
                seen.add(m["id"])
                ctx[m["id"]] = context(m["usage"])
                events.append(("turn", ctx[m["id"]]))
            for b in m.get("content") or []:
                if b.get("type") == "tool_use" and b.get("name") == "Bash" and m["id"] in ctx \
                        and MERGE.search(b["input"].get("command", "")):
                    calls[b["id"]] = len(events)
                    events.append(("merge", ctx[m["id"]]))
        elif r.get("type") == "user" and isinstance(r["message"].get("content"), list):
            failed |= {b["tool_use_id"] for b in r["message"]["content"]
                       if b.get("type") == "tool_result" and b.get("is_error")}
    drop = {calls[t] for t in failed if t in calls}
    return [e for i, e in enumerate(events) if i not in drop]


def simulate(events, limit, base):
    """(перезапуски, опережённые автосжатия, входные токены) при пороге `limit`."""
    restarts = saved = spent = 0
    offset, restarted = 0, False
    for e in events:
        if e[0] == "turn":
            spent += e[1] - offset
        elif e[0] == "merge" and e[1] - offset > limit:
            restarts += 1
            offset, restarted = e[1] - base, True
        elif e[0] == "compact":
            saved += e[1] == "auto" and restarted
            offset, restarted = 0, False
    return restarts, saved, spent


def main():
    sessions, seen = [], set()
    for d in sys.argv[1:]:
        for path in sorted(Path(d).glob("*.jsonl")):
            text = path.read_text(encoding="utf-8")
            title = re.findall(r'"customTitle":"([^"]*)"', text)
            if title and title[-1].endswith("-dispatch"):
                sessions.append((path, title[-1], read(path, seen)))
    starts, growth, autos = [], [], []
    for path, title, events in sessions:
        turns = [e[1] for e in events if e[0] == "turn"]
        merges = [e[1] for e in events if e[0] == "merge"]
        compacts = [e[1:] for e in events if e[0] == "compact"]
        if not turns:
            continue
        starts.append(turns[0])
        autos += [pre for kind, pre in compacts if kind == "auto"]
        last = None
        for e in events:
            if e[0] == "compact":
                last = None
            elif e[0] == "merge":
                if last is not None:
                    growth.append(e[1] - last)
                last = e[1]
        print(f"{title} {path.name[:8]}: ходов {len(turns)}, медиана контекста {statistics.median(turns) / 1000:.0f} тыс., "
              f"максимум {max(turns) / 1000:.0f} тыс., вливаний {len(merges)}, сжатия {compacts}")
    base = int(statistics.median(starts))
    q = statistics.quantiles(growth, n=10)
    print(f"\nстартовый контекст, медиана: {base / 1000:.0f} тыс.")
    print(f"автосжатия: {len(autos)}, preTokens {min(autos) / 1000:.0f}–{max(autos) / 1000:.0f} тыс.")
    print(f"прирост между вливаниями ({len(growth)}): медиана {statistics.median(growth) / 1000:.0f} тыс., "
          f"p90 {q[-1] / 1000:.0f} тыс., максимум {max(growth) / 1000:.0f} тыс.")
    total = sum(simulate(ev, 10 ** 12, base)[2] for _, _, ev in sessions)
    print("\nпорог, тыс. | перезапусков | автосжатий опережено | входных токенов")
    for limit in THRESHOLDS:
        r = [simulate(ev, limit, base) for _, _, ev in sessions]
        print(f"{limit // 1000:>11} | {sum(x[0] for x in r):>12} | {sum(x[1] for x in r):>11} из {len(autos):<7} | "
              f"{sum(x[2] for x in r) / total:.0%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
