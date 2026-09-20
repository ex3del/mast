#!/usr/bin/env python3
"""Проверка формата ROADMAP.md и очередь готовых к взятию пунктов.

  roadmap_lint.py ROADMAP.md          — список нарушений, код 1 если есть
  roadmap_lint.py --ready ROADMAP.md  — пункты, которые можно брать в работу
  без аргументов                      — режим PostToolUse-хука: JSON на stdin,
                                        при новых (относительно HEAD) нарушениях
                                        код 2 и текст в stderr
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ITEM = re.compile(r"^- \*\*([A-Z]-\d+)\*\*(.*)$")
# Статус стоит после разделителя «—» или «·», поэтому слово «готов» в названии не считается
STATUS = re.compile(r"(?:—|·)\s*(запланирован|(?:🔨\s*)?в работе|готов|снят)(?=\s*(?:·|$|\()|\s+\d)")
DEPS = re.compile(r"зависит от:\s*([A-Z]-\d+(?:\s*,\s*[A-Z]-\d+)*)", re.IGNORECASE)


def parse(text):
    """Пункты роадмапа: {id: {status, head, body, deps}}, плюс список дублей."""
    items, dups, cur = {}, [], None
    for line in text.splitlines():
        m = ITEM.match(line)
        if m:
            cur = m.group(1)
            if cur in items:
                dups.append(cur)
            s = STATUS.search(m.group(2))
            items[cur] = {"status": s and s.group(1).replace("🔨", "").strip(),
                          "head": m.group(2), "body": line}
        elif cur and line.startswith((" ", "\t")):
            items[cur]["body"] += "\n" + line
        else:
            cur = None
    for it in items.values():
        it["deps"] = [d.strip() for m in DEPS.finditer(it["body"]) for d in m.group(1).split(",")]
    return items, dups


def ledger_ids(text):
    """ID закрытых пунктов из верхнего слоя архива (docs/roadmap/DONE.md)."""
    return [m.group(1) for m in (ITEM.match(line) for line in text.splitlines()) if m]


def lint(text, ledger=""):
    items, dups = parse(text)
    archived = set(ledger_ids(ledger))
    errors = [f"{i}: номер занят дважды" for i in dups]
    errors += [f"{i}: номер занят, пункт уже в DONE.md" for i in items if i in archived]
    for i, it in items.items():
        if not it["status"]:
            errors.append(f"{i}: нет статуса")
        crit = it["body"].lower().partition("готово когда")[2]
        if not crit:
            errors.append(f"{i}: нет «Готово когда»")
        elif not re.search(r"\d", crit):
            errors.append(f"{i}: в «Готово когда» нет числа")
        if it["status"] == "в работе":
            if "worktree-" not in it["head"] and "основная копия" not in it["head"]:
                errors.append(f"{i}: в работе, но не указано где — `worktree-…` или «основная копия»")
            if "сессия" not in it["head"]:
                errors.append(f"{i}: в работе, но нет сессии")
            waiting = [d for d in it["deps"] if d in items and items[d]["status"] != "готов"]
            if waiting:
                errors.append(f"{i}: взят в работу, но не готовы зависимости: {', '.join(waiting)}")
        if it["status"] == "готов" and f"worktree-{i}" in it["head"]:
            errors.append(f"{i}: готов, но осталась пометка `worktree-{i}`")
        errors += [f"{i}: зависит от несуществующего {d}" for d in it["deps"]
                   if d not in items and d not in archived]
    errors += [f"цикл зависимостей: {c}" for c in cycles(items)]
    return errors


def cycles(items):
    """Циклы в графе зависимостей, каждый — строкой «A-1 → B-2 → A-1»."""
    found, state = [], {}

    def visit(i, path):
        state[i] = "open"
        for d in items[i]["deps"]:
            if d not in items:
                continue
            if state.get(d) == "open":
                found.append(" → ".join(path[path.index(d):] + [d]))
            elif d not in state:
                visit(d, path + [d])
        state[i] = "done"

    for i in items:
        if i not in state:
            visit(i, [i])
    return found


def ready(text, ledger=""):
    """Запланированные пункты, у которых все зависимости готовы или уже в архиве."""
    items, _ = parse(text)
    archived = set(ledger_ids(ledger))

    def done(d):
        return d in archived or items.get(d, {}).get("status") == "готов"

    return [i for i, it in items.items()
            if it["status"] == "запланирован" and all(done(d) for d in it["deps"])]


def orphans(ledger, base):
    """Битые ссылки тезисов на слой подробностей. base — папка, где лежит DONE.md.

    Ссылки нет — это норма: пункт закрылся в одну сессию и STATUS.md не заводил.
    """
    errors = []
    for line in ledger.splitlines():
        m = ITEM.match(line)
        if m:
            errors += [f"{m.group(1)}: ссылка {link} никуда не ведёт"
                       for link in re.findall(r"\]\((done/[^)\s]+)\)", line)
                       if not (Path(base) / link).exists()]
    return errors


def read_ledger(roadmap):
    """Верхний слой архива лежит рядом с роадмапом: docs/roadmap/DONE.md."""
    path = Path(roadmap).parent / "docs/roadmap/DONE.md"
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def main():
    args = sys.argv[1:]
    if args[:1] == ["--ready"]:
        print("\n".join(ready(Path(args[1]).read_text(encoding="utf-8"), read_ledger(args[1]))))
        return 0
    if args:
        ledger = read_ledger(args[0])
        errors = lint(Path(args[0]).read_text(encoding="utf-8"), ledger)
        errors += orphans(ledger, Path(args[0]).parent / "docs/roadmap")
        print("\n".join(errors))
        return 1 if errors else 0
    path = Path(json.load(sys.stdin).get("tool_input", {}).get("file_path", ""))
    if path.name != "ROADMAP.md":
        return 0
    # Нарушения, которые уже были в HEAD, не показываем — их вносила не эта правка
    head = subprocess.run(["git", "-C", str(path.parent), "show", "HEAD:./ROADMAP.md"],
                          capture_output=True, text=True, encoding="utf-8")
    ledger = read_ledger(path)
    old = set(lint(head.stdout, ledger)) if head.returncode == 0 else set()
    errors = [e for e in lint(path.read_text(encoding="utf-8"), ledger) if e not in old]
    if errors:
        print("ROADMAP.md нарушает формат (скилл managing-roadmap-items), исправь:\n"
              + "\n".join(f"- {e}" for e in errors), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
