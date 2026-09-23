#!/usr/bin/env python3
"""CLI метода поверх roadmap_lint: вливание ветки пункта одной командой.

  mast merge X-N [--no-push]   — из основной копии, на ветке по умолчанию

Первым аргументом обёртка `bin/mast` передаёт язык своего плагина (`ru`/`en`).
Всё проверяется до мерджа, отказ ничего не меняет. Потом ff-мердж, тезис в
DONE.md, удаление строки из ROADMAP.md и записи долга — одним коммитом, push,
уборка сессии, worktree и ветки. Следом — готовые ветки, которые этот мердж
сдвинул: rebase и тесты во временной копии; чисто — вливаются тем же путём,
иначе в выводе текст для их сессии.
"""
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

from plugin_names import PLUGIN
from roadmap_lint import ITEM, STATUS, criterion, detect_lang, lint, parse, ready

ROADMAP, DONE, DEBT = "ROADMAP.md", "docs/roadmap/DONE.md", "TECH_DEBT.md"
DISPATCH = ".claude/rules/dispatch.md"
ID = re.compile(r"^[A-Z]-\d+$")
# Блоки тела последнего коммита. Разбор терпит старую форму: «Готово когда
# (дословно из origin/main):», «Черновик тезиса для DONE.md:» с шапкой строки
CRIT_LINE = re.compile(r"^\s*(?:готово когда|done when)[^:\n]*:", re.I | re.M)
THESIS = re.compile(r"^\s*(?:черновик\s+)?(?:тезис|(?:draft\s+)?thesis)[^:\n]*:(.*)$", re.I)
DEBT_HEAD = re.compile(r"^\s*[^:\n]*TECH_DEBT\.md`?\s*:\s*$")
TESTS = re.compile(r"^\s*(?:тесты|tests)\s*:\s*`([^`]+)`", re.I | re.M)
PREFIX = re.compile(r"(?:\[[A-Z]-\d+\]\s*)+")
# Коммиты пункта в main, которые делает диспетчер по скиллу (завёл, взял, поменял
# критерий, перенёс находку с её тестом) или сессия находкой, — не часть работы пункта
BOOKKEEPING = re.compile(r"заведён|взят|критерий изменён|находк|opened|taken into work|criterion changed|finding", re.I)

LANG = "ru"
T = {
    "usage": ("использование: mast merge X-N [--no-push]", "usage: mast merge X-N [--no-push]"),
    "refused": ("Отказ, ничего не изменено: ", "Refused, nothing changed: "),
    "main_copy": ("mast merge запускается из основной копии, а не из worktree",
                  "mast merge runs from the main copy, not from a worktree"),
    "no_roadmap": ("нет ROADMAP.md в корне репозитория", "no ROADMAP.md at the repository root"),
    "no_item": ("{i}: строки нет в ROADMAP.md", "{i}: no such line in ROADMAP.md"),
    "not_in_work": ("{i}: пункт не «в работе»", "{i}: the item is not in progress"),
    "no_branch": ("{i}: нет ветки {b}", "{i}: no branch {b}"),
    "dirty": ("незакоммиченные правки в {f} — закоммить или убери", "uncommitted changes in {f} — commit or drop them"),
    "empty": ("в {b} нет новых коммитов — уже влита?", "{b} has no new commits — already merged?"),
    "not_ff": ("{b} — не fast-forward от HEAD: сессия пункта делает rebase на свежий main",
               "{b} is not a fast-forward of HEAD: the item session rebases onto a fresh main"),
    "foreign": ("в диапазоне чужие коммиты: {c}", "foreign commits in the range: {c}"),
    "touched": ("ветка правит {f} — их правит только основная копия, запись — в последний коммит",
                "the branch edits {f} — only the main copy does, entries go in the last commit"),
    "no_crit": ("в последнем коммите {b} нет «Готово когда»", 'the last commit of {b} has no "Done when"'),
    "not_verbatim": ("в последнем коммите {b} нет критерия из ROADMAP.md дословно: {c}",
                     "the last commit of {b} lacks the ROADMAP.md criterion verbatim: {c}"),
    "no_measure": ("в последнем коммите {b} нет замеров «было → стало»",
                   'the last commit of {b} has no "before → after" measurements'),
    "no_thesis": ("в последнем коммите {b} нет абзаца «Тезис:» для DONE.md",
                  'the last commit of {b} has no "Thesis:" paragraph for DONE.md'),
    "earlier": ("часть работы {i} уже в main: {c} — нестандартный случай, вливай руками с человеком",
                "part of {i} is already in main: {c} — a non-standard case, merge by hand with the human"),
    "lint": ("после вливания линт нашёл бы: {e}", "after the merge the lint would report: {e}"),
    "commit_failed": ("мердж сделан, файлы записаны, но коммит не прошёл: {e}\nЗакоммить: git commit -m \"{m}\" -- {f}",
                      "merged and files written, but the commit failed: {e}\nCommit: git commit -m \"{m}\" -- {f}"),
    "closed": ("[{i}] закрыт", "[{i}] closed"),
    "merged": ("{i} влит: `{r}`", "{i} merged: `{r}`"),
    "rebased": ("{i} переребейзен, тесты зелёные, влит: `{r}`", "{i} rebased, tests green, merged: `{r}`"),
    "conflict": ("конфликт при rebase в {f}", "rebase conflict in {f}"),
    "no_tests": ("команда тестов не объявлена — строка «Тесты: `<команда>`» в {f}",
                 "no test command declared — a line \"Tests: `<command>`\" in {f}"),
    "red": ("тесты `{c}` красные:\n{o}", "tests `{c}` are red:\n{o}"),
    "back": ("{i} не влит — {w}\n  Отправь сессии {i} через SendMessage: «{b} не влилась следом за {m}: {w}. "
             "Сделай git rebase на свежий main, прогони весь набор тестов и снова напиши, что готов.»",
             "{i} not merged — {w}\n  Send the {i} session via SendMessage: \"{b} did not merge after {m}: {w}. "
             "Rebase onto a fresh main, run the whole test suite and report ready again.\""),
    "pushed": ("push: {r}", "push: {r}"),
    "no_push": ("push пропущен: {w}", "push skipped: {w}"),
    "no_upstream": ("у ветки нет upstream", "the branch has no upstream"),
    "push_failed": ("push не прошёл: {e}", "push failed: {e}"),
    "cleanup": ("уборка {i}: {w}", "cleanup of {i}: {w}"),
    "waited": ("Ждали {i}: {l} — их живым сессиям: «{i} в main, сделай rebase»",
               "Waited on {i}: {l} — tell their live sessions: \"{i} is in main, rebase\""),
    "ready": ("Готовы к взятию: {l}", "Ready to take: {l}"),
    "inbox": ("В docs/roadmap/inbox/ файлов: {n} — разбери", "Files in docs/roadmap/inbox/: {n} — triage them"),
}


class Refusal(Exception):
    pass


def say(key, **kw):
    return T[key][LANG == "en"].format(**kw)


def run(*args, cwd=None):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8")


def git(*args):
    """stdout git-команды; ошибка git — отказ с её текстом."""
    r = run("git", *args)
    if r.returncode:
        raise Refusal(f"git {' '.join(args)}: {(r.stderr or r.stdout).strip()}")
    return r.stdout.strip()


def ok(*args):
    return run("git", *args).returncode == 0


def read(rel):
    path = Path(rel)
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def write(rel, text):
    # Байтами: на Windows write_text превратил бы каждый \n в \r\n
    Path(rel).parent.mkdir(parents=True, exist_ok=True)
    Path(rel).write_bytes(text.encode("utf-8"))


def norm(text):
    return " ".join(text.split())


def blocks(body):
    """Тезис одной строкой и записи долга из тела коммита; тезиса нет — None."""
    lines, thesis, debt = body.splitlines(), None, []
    for i, line in enumerate(lines):
        m = THESIS.match(line)
        if m and thesis is None:
            para = [m.group(1)]
            for nxt in lines[i + 1:]:
                if not nxt.strip() or DEBT_HEAD.match(nxt) or CRIT_LINE.match(nxt):
                    break
                para.append(nxt)
            # Шапку строки DONE.md строит скрипт — из черновика берём только текст
            thesis = " ".join(p.strip() for p in para if p.strip() and not ITEM.match(p.strip()))
        elif DEBT_HEAD.match(line):
            for nxt in lines[i + 1:]:
                if nxt.strip() and not nxt.startswith((" ", "\t", "- ")):
                    break
                debt.append(nxt)
    return thesis or None, textwrap.dedent("\n".join(debt)).strip()


def check(item, base, tip, crit):
    """Отказы по ветке: диапазон, файлы роадмапа, последний коммит. Возвращает (тезис, долг)."""
    b = f"worktree-{item}"
    subjects = git("log", "--format=%h %s", f"{base}..{tip}").splitlines()
    if not subjects:
        raise Refusal(say("empty", b=b))
    foreign = [s for s in subjects if not s.split(" ", 1)[1].startswith(f"[{item}]")]
    if foreign:
        raise Refusal(say("foreign", c="; ".join(foreign)))
    touched = sorted(set(git("diff", "--name-only", base, tip).splitlines()) & {ROADMAP, DONE, DEBT})
    if touched:
        raise Refusal(say("touched", f=", ".join(touched)))
    body = git("log", "-1", "--format=%B", tip)
    if not CRIT_LINE.search(body):
        raise Refusal(say("no_crit", b=b))
    if norm(crit or "") not in norm(body):
        raise Refusal(say("not_verbatim", b=b, c=crit))
    # Форма замера, не его правдивость: очередь вливает ветки, которых диспетчер не смотрел
    if "→" not in body and "->" not in body:
        raise Refusal(say("no_measure", b=b))
    thesis, debt = blocks(body)
    if not thesis:
        raise Refusal(say("no_thesis", b=b))
    return thesis, debt


def earlier_work(item):
    """Коммиты пункта в main вне файлов роадмапа: второй заход или работа в основной копии.
    Эвристика по теме коммита: учётные коммиты диспетчера и находки заходом не считаются."""
    out = git("log", "-F", f"--grep=[{item}]", "--format=%x00%h %s", "--name-only", "HEAD")
    hits = []
    for chunk in out.split("\x00")[1:]:
        head, *files = chunk.strip().splitlines()
        subject = head.split(" ", 1)[1]
        prefix = PREFIX.match(subject)
        if (prefix and f"[{item}]" in prefix.group(0) and not BOOKKEEPING.search(subject)
                and any(f and f not in (ROADMAP, DEBT) and not f.startswith("docs/roadmap/") for f in files)):
            hits.append(head)
    return hits


def thesis_entry(item, row, base, tip, thesis):
    """Строка тезиса для DONE.md: шапка по строке пункта и дереву ветки, текст — из коммита."""
    s = STATUS.search(row["head"])
    title = (row["head"][:s.start()] if s else row["head"]).strip()
    files = git("ls-tree", "-r", "--name-only", tip).splitlines()
    links = [f"[STATUS](done/{item}/STATUS.md)"] if f"docs/roadmap/done/{item}/STATUS.md" in files else []
    links += [f"[ADR](../adr/{Path(f).name})" for f in files if f.startswith(f"docs/adr/{item}-")]
    date = datetime.date.today().strftime("%d.%m")
    head = f"- **{item}** {title} — {date} · `{base[:7]}..{tip[:7]}`" + "".join(f" · {l}" for l in links)
    return f"{head}\n  {thesis}\n"


def section(roadmap, item):
    """Заголовок раздела `## …`, под которым стоит пункт."""
    header = None
    for line in roadmap.splitlines():
        if line.startswith("## "):
            header = line
        m = ITEM.match(line)
        if m and m.group(1) == item:
            return header
    return None


def add_thesis(done, header, entry):
    """Тезис — первым под заголовком своего раздела; раздела нет — новый в конце."""
    if not done:
        done = "# Закрытые пункты\n" if LANG == "ru" else "# Closed items\n"
    m = header and re.search(rf"^{re.escape(header)}\n", done, re.M)
    if not m:
        return done.rstrip("\n") + (f"\n\n{header}" if header else "") + f"\n\n{entry}"
    return done[:m.end()] + "\n" + entry + "\n" + done[m.end():].lstrip("\n")


def drop_row(roadmap, item):
    """Строка пункта с продолжением и одна пустая строка рядом."""
    lines = roadmap.split("\n")
    start = next(i for i, line in enumerate(lines) if (m := ITEM.match(line)) and m.group(1) == item)
    end = start + 1
    while end < len(lines) and lines[end].startswith((" ", "\t")):
        end += 1
    if end < len(lines) and not lines[end].strip():
        end += 1
    elif start and not lines[start - 1].strip():
        start -= 1
    return "\n".join(lines[:start] + lines[end:])


def close(item, tip):
    """Отказы, затем ff-мердж и одна правка трёх файлов одним коммитом. Возвращает диапазон."""
    base = git("rev-parse", "HEAD")
    roadmap, done, debt_text = read(ROADMAP), read(DONE), read(DEBT)
    row = parse(roadmap)[0][item]
    thesis, debt = check(item, base, tip, criterion(row["body"]))
    earlier = earlier_work(item)
    if earlier:
        raise Refusal(say("earlier", i=item, c="; ".join(earlier)))
    new_roadmap = drop_row(roadmap, item)
    new_done = add_thesis(done, section(roadmap, item), thesis_entry(item, row, base, tip, thesis))
    old = set(lint(roadmap, done, LANG))
    errors = [e for e in lint(new_roadmap, new_done, LANG) if e not in old]
    if errors:
        raise Refusal(say("lint", e="; ".join(errors)))

    git("merge", "-q", "--ff-only", tip)
    changed = [ROADMAP, DONE] + ([DEBT] if debt else [])
    write(ROADMAP, new_roadmap)
    write(DONE, new_done)
    if debt:
        write(DEBT, (debt_text.rstrip("\n") + "\n\n" if debt_text else "") + debt + "\n")
    msg = say("closed", i=item)
    r = run("git", "add", "--", *changed)
    r = r if r.returncode else run("git", "commit", "-q", "-m", msg, "--", *changed)
    if r.returncode:
        raise Refusal(say("commit_failed", e=(r.stderr or r.stdout).strip(), m=msg, f=" ".join(changed)))
    return f"{base[:7]}..{tip[:7]}"


def worktree_path(item):
    return Path.cwd() / ".claude" / "worktrees" / item


def session(path):
    """id фоновой сессии, чей cwd — worktree пункта; нет `claude` — None."""
    if not shutil.which("claude"):
        return None
    try:
        agents = json.loads(run("claude", "agents", "--json", "--all").stdout)
    except ValueError:
        return None
    real = os.path.realpath(path)
    return next((a["id"] for a in agents
                 if a.get("id") and os.path.realpath(a.get("cwd") or "/") == real), None)


def cleanup(item, tip, rebased):
    """Сессия, worktree и ветка пункта. Сбой уборки не отменяет вливание — он в вывод."""
    path, branch, notes = worktree_path(item), f"worktree-{item}", []
    sid = session(path)
    if sid:
        r = run("claude", "rm", sid)
        if r.returncode:
            notes.append(f"claude rm {sid}: {(r.stderr or r.stdout).strip()}")
    listed = [os.path.realpath(line[9:]) for line in git("worktree", "list", "--porcelain").splitlines()
              if line.startswith("worktree ")]
    if os.path.realpath(path) in listed:
        r = run("git", "worktree", "remove", str(path))
        if r.returncode:
            notes.append(r.stderr.strip())
    if git("rev-parse", branch) != tip:
        notes.append(f"{branch} сдвинулась после проверки — не удаляю" if LANG == "ru"
                     else f"{branch} moved after the check — not deleting")
    else:
        # Переребейзенная копия влита, а сама ветка — нет: -d её не удалит
        r = run("git", "branch", "-D" if rebased else "-d", branch)
        if r.returncode:
            notes.append(r.stderr.strip())
    return notes


def tests_command():
    m = TESTS.search(read(DISPATCH))
    return m and m.group(1)


def rebase_and_test(item, tip):
    """Rebase ветки на HEAD во временной копии, не трогая worktree её сессии, и тесты.
    Возвращает (вершина после rebase, None) или (None, почему не вышло)."""
    cmd = tests_command()
    if not cmd:
        return None, say("no_tests", f=DISPATCH)
    tmp = tempfile.mkdtemp(prefix="mast-")
    copy = os.path.join(tmp, item)
    try:
        git("worktree", "add", "-q", "--detach", copy, tip)
        if run("git", "-C", copy, "rebase", "-q", git("rev-parse", "HEAD")).returncode:
            files = git("-C", copy, "diff", "--name-only", "--diff-filter=U").split()
            run("git", "-C", copy, "rebase", "--abort")
            return None, say("conflict", f=", ".join(files))
        t = run("sh", "-c", cmd, cwd=copy)
        if t.returncode:
            tail = "\n".join((t.stdout + t.stderr).strip().splitlines()[-15:])
            return None, say("red", c=cmd, o=textwrap.indent(tail, "    "))
        return git("-C", copy, "rev-parse", "HEAD"), None
    finally:
        run("git", "worktree", "remove", "--force", copy)
        shutil.rmtree(tmp, ignore_errors=True)


def queue(old_head, merged):
    """Готовые ветки пунктов «в работе», которые сдвинул этот мердж: их база — old_head."""
    for item, row in parse(read(ROADMAP))[0].items():
        branch = f"worktree-{item}"
        if row["status"] != "в работе" or item in merged or not ok("rev-parse", "-q", "--verify", branch):
            continue
        tip = git("rev-parse", branch)
        body = git("log", "-1", "--format=%B", tip)
        if ok("merge-base", "--is-ancestor", old_head, tip) and CRIT_LINE.search(body) and blocks(body)[0]:
            yield item, tip


def push(branches):
    """push ветки по умолчанию и удаление влитых веток на удалённом."""
    if not ok("rev-parse", "-q", "--verify", "@{u}"):
        return [say("no_push", w=say("no_upstream"))]
    remote = git("config", f"branch.{git('symbolic-ref', '--short', 'HEAD')}.remote")
    r = run("git", "push", "-q")
    if r.returncode:
        return [say("push_failed", e=r.stderr.strip())]
    gone = [b for b in branches if run("git", "ls-remote", "--heads", remote, b).stdout.strip()]
    if gone:
        run("git", "push", "-q", remote, "--delete", *gone)
    return [say("pushed", r=", ".join([git("rev-parse", "--short=7", "HEAD")] + gone))]


def merge(item, do_push):
    top = git("rev-parse", "--show-toplevel")
    os.chdir(top)
    if os.path.realpath(git("rev-parse", "--git-dir")) != os.path.realpath(git("rev-parse", "--git-common-dir")):
        raise Refusal(say("main_copy"))
    if not Path(ROADMAP).is_file():
        raise Refusal(say("no_roadmap"))
    row = parse(read(ROADMAP))[0].get(item)
    if not row:
        raise Refusal(say("no_item", i=item))
    if row["status"] != "в работе":
        raise Refusal(say("not_in_work", i=item))
    branch = f"worktree-{item}"
    if not ok("rev-parse", "-q", "--verify", branch):
        raise Refusal(say("no_branch", i=item, b=branch))
    dirty = git("status", "--porcelain", "--", ROADMAP, DONE, DEBT)
    if dirty:
        raise Refusal(say("dirty", f=", ".join(line[3:] for line in dirty.splitlines())))
    tip = git("rev-parse", branch)
    if not ok("merge-base", "--is-ancestor", "HEAD", tip):
        raise Refusal(say("not_ff", b=branch))

    old_head = git("rev-parse", "HEAD")
    out, merged = [say("merged", i=item, r=close(item, tip))], {item: (tip, False)}
    for other, other_tip in list(queue(old_head, merged)):
        new_tip, why = rebase_and_test(other, other_tip)
        if new_tip:
            try:
                out.append(say("rebased", i=other, r=close(other, new_tip)))
                merged[other] = (other_tip, True)
                continue
            except Refusal as e:
                why = str(e)
        out.append(say("back", i=other, b=f"worktree-{other}", m=", ".join(merged), w=why))

    out += push([f"worktree-{i}" for i in merged]) if do_push else [say("no_push", w="--no-push")]
    for i, (i_tip, rebased) in merged.items():
        out += [say("cleanup", i=i, w=n) for n in cleanup(i, i_tip, rebased)]
    roadmap = parse(read(ROADMAP))[0]
    for i in merged:
        waited = [j for j, r in roadmap.items() if i in r["deps"]]
        if waited:
            out.append(say("waited", i=i, l=", ".join(waited)))
    free = ready(read(ROADMAP), read(DONE))
    if free:
        out.append(say("ready", l=", ".join(free)))
    inbox = [p for p in Path("docs/roadmap/inbox").glob("*") if p.is_file()]
    if inbox:
        out.append(say("inbox", n=len(inbox)))
    print("\n".join(out))
    return 0


def main():
    global LANG
    args = sys.argv[1:]
    lang = args.pop(0) if args[:1] and args[0] in PLUGIN else None
    do_push = "--no-push" not in args
    args = [a for a in args if a != "--no-push"]
    LANG = lang or detect_lang(read(ROADMAP))
    if len(args) != 2 or args[0] != "merge" or not ID.match(args[1]):
        print(say("usage"), file=sys.stderr)
        return 2
    try:
        return merge(args[1], do_push)
    except Refusal as e:
        print(say("refused") + str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
