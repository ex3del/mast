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
# Статус стоит после разделителя «—» или «·», поэтому слово «готов» в названии не считается.
# Оба языка равноправны: русские и английские метки статуса разобраны в одном месте.
STATUS = re.compile(
    r"(?:—|·)\s*(запланирован|planned|(?:🔨\s*)?(?:в работе|in progress)|готов|done|снят|dropped)"
    r"(?=\s*(?:·|$|\()|\s+\d)"
)
# Внутреннее представление статуса — всегда русское каноническое слово,
# поэтому вся остальная логика lint()/ready() не знает про язык файла
STATUS_ALIASES = {
    "planned": "запланирован", "in progress": "в работе",
    "done": "готов", "dropped": "снят",
}
DEPS = re.compile(r"(?:зависит от|depends on):\s*([A-Z]-\d+(?:\s*,\s*[A-Z]-\d+)*)", re.IGNORECASE)
# Подраздел архива со снятыми пунктами — на любом уровне заголовка. Заголовок
# пишет сессия прозой, поэтому хвост («Снято (архив)», «Dropped items») и эмодзи
# перед словом допустимы: не узнать подраздел дороже, чем узнать лишний.
DROPPED_HEADER = re.compile(r"^#+[\s\W]*(снят|dropped)", re.IGNORECASE)
# Заголовок критерия — только в начале своей строки, иначе фраза в прозе («Переводим
# заголовок «Done when»…») ложно засчитывается за настоящий критерий
CRIT_HEADER = re.compile(r"^[ \t]*(?:готово когда|done when)\s*:(.*)$", re.IGNORECASE | re.MULTILINE)


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
            raw = s and s.group(1).replace("🔨", "").strip()
            items[cur] = {"status": STATUS_ALIASES.get(raw, raw),
                          "head": m.group(2), "body": line}
        elif cur and line.startswith((" ", "\t")):
            items[cur]["body"] += "\n" + line
        else:
            cur = None
    for it in items.values():
        it["deps"] = [d.strip() for m in DEPS.finditer(it["body"]) for d in m.group(1).split(",")]
    return items, dups


def split_ledger(text):
    """ID из архива (docs/roadmap/DONE.md): (все, снятые).

    Снятые лежат под заголовком «Снято»/«Dropped». Их номер занят навсегда, как и
    у закрытых, но зависимость на снятый пункт не выполнена — работу бросили.
    """
    all_ids, dropped, in_dropped = [], [], False
    for line in text.splitlines():
        if line.startswith("#"):
            in_dropped = bool(DROPPED_HEADER.match(line.strip()))
        m = ITEM.match(line)
        if m:
            all_ids.append(m.group(1))
            if in_dropped:
                dropped.append(m.group(1))
    return all_ids, dropped


def ledger_ids(text):
    """ID всех пунктов архива — и закрытых, и снятых: номер занят теми и другими."""
    return split_ledger(text)[0]


def detect_lang(text):
    """Язык жалоб: русский, если в файле есть хоть один русский токен формата
    (смешанный файл считается русским), иначе английский."""
    lowered = text.lower()
    if any(t in lowered for t in ("запланирован", "в работе", "готов", "снят", "зависит от", "мои пути")):
        return "ru"
    if any(t in lowered for t in ("planned", "in progress", "done", "dropped", "depends on", "my paths")):
        return "en"
    return "ru"


def msg(lang, ru, en):
    return ru if lang == "ru" else en


DONE_WHEN_MISSING_EN = 'no "Done when"'
DONE_WHEN_NO_NUMBER_EN = '"Done when" has no number'
NO_LOCATION_EN = 'in progress, but location not specified — `worktree-…` or "main copy"'


def lint(text, ledger=""):
    items, dups = parse(text)
    all_archived, dropped_list = split_ledger(ledger)
    archived, dropped = set(all_archived), set(dropped_list)
    lang = detect_lang(text)
    errors = [f"{i}: {msg(lang, 'номер занят дважды', 'item number used twice')}" for i in dups]
    errors += [f"{i}: {msg(lang, 'номер занят, пункт уже в DONE.md', 'item number taken, already in DONE.md')}"
               for i in items if i in archived]
    for i, it in items.items():
        if not it["status"]:
            errors.append(f"{i}: {msg(lang, 'нет статуса', 'no status')}")
        crit_m = CRIT_HEADER.search(it["body"])
        if not crit_m:
            errors.append(f"{i}: {msg(lang, 'нет «Готово когда»', DONE_WHEN_MISSING_EN)}")
        elif not re.search(r"\d", crit_m.group(1)):
            errors.append(f"{i}: {msg(lang, 'в «Готово когда» нет числа', DONE_WHEN_NO_NUMBER_EN)}")
        if it["status"] == "в работе":
            if ("worktree-" not in it["head"] and "основная копия" not in it["head"]
                    and "main copy" not in it["head"]):
                errors.append(f"{i}: {msg(lang, 'в работе, но не указано где — `worktree-…` или «основная копия»', NO_LOCATION_EN)}")
            if "сессия" not in it["head"] and "session" not in it["head"]:
                errors.append(f"{i}: {msg(lang, 'в работе, но нет сессии', 'in progress, but no session')}")
            waiting = [d for d in it["deps"] if d in items and items[d]["status"] != "готов"]
            if waiting:
                w = ", ".join(waiting)
                errors.append(f"{i}: {msg(lang, f'взят в работу, но не готовы зависимости: {w}', f'taken into work, but dependencies not ready: {w}')}")
        if it["status"] == "готов" and f"worktree-{i}" in it["head"]:
            errors.append(f"{i}: {msg(lang, f'готов, но осталась пометка `worktree-{i}`', f'done, but still has the `worktree-{i}` mark')}")
        errors += [f"{i}: {msg(lang, f'зависит от несуществующего {d}', f'depends on nonexistent {d}')}"
                   for d in it["deps"] if d not in items and d not in archived]
        for d in it["deps"]:
            if d in dropped:
                errors.append(f"{i}: " + msg(
                    lang,
                    f"зависит от снятого {d} — убери зависимость или сними пункт",
                    f"depends on dropped {d} — remove the dependency or drop the item"))
    errors += [f"{msg(lang, 'цикл зависимостей', 'dependency cycle')}: {c}" for c in cycles(items)]
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
    all_archived, dropped = split_ledger(ledger)
    closed = set(all_archived) - set(dropped)

    def done(d):
        return d in closed or items.get(d, {}).get("status") == "готов"

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


def hooked_roadmap(path):
    """Какой роадмап проверять по правке файла `path`, или None.

    Архив проверяется вместе с роадмапом: занятые номера, снятые пункты и ссылки
    на `done/` живут в `DONE.md`, а хук видит правку только одного файла.
    """
    if path.name == "ROADMAP.md":
        return path
    if path.name == "DONE.md" and path.parent.name == "roadmap":
        return path.parent.parent.parent / "ROADMAP.md"
    return None


def from_head(project, rel):
    """Содержимое файла в HEAD; файла нет или это не репозиторий — пустая строка."""
    r = subprocess.run(["git", "-C", str(project), "show", f"HEAD:./{rel}"],
                       capture_output=True, text=True, encoding="utf-8")
    return r.stdout if r.returncode == 0 else ""


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
    roadmap = hooked_roadmap(path)
    if roadmap is None or not roadmap.is_file():
        return 0
    # Нарушения, которые уже были в HEAD, не показываем — их вносила не эта правка
    ledger = read_ledger(roadmap)
    content = roadmap.read_text(encoding="utf-8")
    old = set(lint(from_head(roadmap.parent, "ROADMAP.md"),
                   from_head(roadmap.parent, "docs/roadmap/DONE.md")))
    errors = [e for e in lint(content, ledger) if e not in old]
    errors += [e for e in orphans(ledger, roadmap.parent / "docs/roadmap")
               if e not in old]
    if errors:
        header = msg(detect_lang(content + ledger),
                     "Роадмап нарушает формат (скилл `mast:managing-roadmap-items-ru`), исправь:",
                     "The roadmap violates the format (skill `mast:managing-roadmap-items`), fix:")
        print(header + "\n" + "\n".join(f"- {e}" for e in errors), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
