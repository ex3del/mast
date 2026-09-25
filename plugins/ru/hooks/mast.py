#!/usr/bin/env python3
# Сгенерировано tools/sync_plugins.py из hooks/mast.py — правь там, здесь затрётся
"""CLI метода поверх roadmap_lint: запуск и вливание пункта одной командой, сверка сессий.

  mast start X-N [--model opus|sonnet] [--advisor M] [--force "причина"] [--no-push] ["хвост"]
                               — из основной копии; по умолчанию opus с советником fable
  mast merge X-N [--no-push]   — из основной копии, на ветке по умолчанию
  mast status                  — из любой копии; ничего не меняет

Первым аргументом обёртка `bin/mast` передаёт язык своего плагина (`ru`/`en`).
Всё проверяется до мерджа, отказ ничего не меняет. Последняя проверка — ревью
с чистым контекстом (`review.py`): `отказ` — отказ с причинами для сессии,
`не уверен` — слот «ждёт человека» коммитом, без вердикта — отказ. Ответ человека
`решил человек` вливает без ревьюера, только пока дифф тот же, о котором спрашивали:
отпечаток диффа — в теле коммита слота. Потом ff-мердж, тезис в
DONE.md, удаление строки из ROADMAP.md и записи долга — одним коммитом; в его теле и
в выводе — справка сессии, `git diff --stat` и команда вопроса к сессии. Потом push.
Сессия влитого пункта живёт час — срок кэша: её, worktree и ветку убирают следующие
`mast merge` и `mast start` после успеха, когда час прошёл. Вливается ровно названная ветка: для веток
других пунктов «в работе», которые сдвинул мердж, в выводе — текст для их сессий.
Сбой после мерджа — не отказ: вывод говорит, что сделано и что доделать.

`mast start` отказывает до любых изменений: пункт не готов к взятию, «Мои пути»
пересекаются с пунктом «в работе» без `--force`, `sonnet` на opus-зоне или с
советником `fable`, хвост промпта длиннее предела. Потом строка «в работе», коммит,
push и `claude --bg` с промптом из шаблона; последняя строка вывода —
`claude attach <id>`. Worktree — всегда от локального HEAD: в нём строка пункта,
даже если push не было.

`mast status` сверяет пункты «в работе» основной копии, её worktree и сессии из
`claude agents --json --all`: брошен, сирота, лишняя; закрытый пункт с worktree —
до какого часа его сессия отвечает из кэша и чем её спросить потом. Сессия пункта без коммита
дольше порога — пометка, а не отказ: ложная тревога дороже медленного обнаружения.
"""
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import shlex
import textwrap
import time
from fnmatch import fnmatchcase
from pathlib import Path

from plugin_names import PLUGIN
from review import NoVerdict, ask
from roadmap_lint import ITEM, STATUS, WAITING, criterion, detect_lang, lint, parse, ready, split_ledger, waiting

ROADMAP, DONE, DEBT = "ROADMAP.md", "docs/roadmap/DONE.md", "TECH_DEBT.md"
ID = re.compile(r"^[A-Z]-\d+$")
# Блоки тела последнего коммита. Разбор терпит старую форму: «Готово когда
# (дословно из origin/main):», «Черновик тезиса для DONE.md:» с шапкой строки
CRIT_LINE = re.compile(r"^\s*(?:готово когда|done when)[^:\n]*:", re.I | re.M)
THESIS = re.compile(r"^\s*(?:черновик\s+)?(?:тезис|(?:draft\s+)?thesis)[^:\n]*:(.*)$", re.I)
DEBT_HEAD = re.compile(r"^\s*[^:\n]*TECH_DEBT\.md`?\s*:\s*$")
BRIEF = re.compile(r"^\s*(?:справка|brief)[^:\n]*:(.*)$", re.I)
# Справка человеку — беглый взгляд, а не отчёт: предел — текст блока без заголовка
BRIEF_LIMIT = 800
# Срок кэша Claude Code от последнего сообщения: столько живёт сессия закрытого пункта
HOUR = 3600
PREFIX = re.compile(r"(?:\[[A-Z]-\d+\]\s*)+")
# Коммиты пункта в main, которые делает диспетчер по скиллу (завёл, взял, поменял
# критерий, перенёс находку с её тестом) или сессия находкой, — не часть работы пункта
BOOKKEEPING = re.compile(r"завед|взят|критерий изменён|находк|opened|taken into work|criterion changed|finding", re.I)
# Слот сессии в строке пункта и порог тишины в `.claude/rules/dispatch.md` — на обоих языках
SESSION = re.compile(r"(?:сессия|session)\s+`([^`]+)`")
SILENCE = re.compile(r"(?:порог тишины|silence threshold)\s*:\s*(\d+)", re.I)
SILENCE_DEFAULT = 30
# Имя сессии пункта; `B-2-<слово>` движок выдаёт, когда имя `B-2` занято
ITEM_NAME = re.compile(r"^([A-Z]-\d+)(?:-|$)")
DISPATCH = ".claude/rules/dispatch.md"
PATHS = re.compile(r"^[ \t]*(?:мои пути|my paths)\s*:(.*)$", re.I | re.M)
# Строка зоны в dispatch.md: пути перед «— только opus»
ZONE = re.compile(r"^[-*\t ]*(.+?)\s+[—–-]\s+(?:только opus|opus only)", re.I | re.M)
# Файлы, которые агенты читают как правила, — opus в любом проекте
ALWAYS_OPUS = ["CLAUDE.md", ".claude/**"]
# Правка этих файлов меняет каждую будущую сессию — планка ревью строже
RULE_FILES = [".claude/**", "**/CLAUDE.md", "**/skills/**"]
# Память сессии для ревьюера: проектный CLAUDE.md там, где его ищет площадка, правила
# `.claude/rules/` и глобальный CLAUDE.md — `CLAUDE_CONFIG_DIR` переносит `~/.claude` целиком
PROJECT_MEMORY = ["CLAUDE.md", ".claude/CLAUDE.md", ".claude/rules"]
CLAUDE_HOME = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
FRONT = re.compile(r"---\n(.*?)\n---", re.S)
RULE_PATHS = re.compile(r"^paths:[ \t]*(.*)((?:\n[ \t]*-.*)*)", re.M)
# Дифф для ревьюера: без истории пункта и сгенерированного (`linguist-generated`
# без значения или `=true`) — проверять в нём нечего
REVIEWED = [".", ":(exclude)docs/roadmap", ":(exclude,attr:linguist-generated)",
            ":(exclude,attr:linguist-generated=true)"]
# Ответ человека на «не уверен» — слот вместо «ждёт человека»; вопрос и отпечаток
# диффа — в теле коммита слота, который ставит скрипт
DECIDED = re.compile(r"(?:—|·)\s*(?:решил человек|human decided)\s*:(.*)$", re.I)
ASKED = re.compile(r"^(?:вопрос ревью|review question):\s*(.*)$", re.M)
PRINT = re.compile(r"^(?:отпечаток диффа|diff fingerprint):\s*(\S+)$", re.M)
# Свободный хвост промпта старта: координация, а не контекст пункта — тот в строке
TAIL_LIMIT = 300
BASE_HEAD = '{"worktree":{"baseRef":"head"}}'
# `claude --bg` красит id, даже когда stdout не терминал
ANSI = re.compile(r"\x1b\[[0-9;]*m")
ATTACH = re.compile(r"claude attach (\S+)")

LANG = "ru"
T = {
    "usage": ("использование: mast start X-N [--model opus|sonnet] [--advisor M] [--force \"причина\"] "
              "[--no-push] [\"хвост\"] | mast merge X-N [--no-push] | mast status",
              "usage: mast start X-N [--model opus|sonnet] [--advisor M] [--force \"reason\"] "
              "[--no-push] [\"tail\"] | mast merge X-N [--no-push] | mast status"),
    "refused": ("Отказ, ничего не изменено: ", "Refused, nothing changed: "),
    "main_copy": ("mast {c} запускается из основной копии, а не из worktree",
                  "mast {c} runs from the main copy, not from a worktree"),
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
    "no_brief": ("в последнем коммите {b} нет блока «Справка:» для человека",
                 'the last commit of {b} has no "Brief:" block for the human'),
    "long_brief": ("справка в последнем коммите {b} — {n} символов при пределе {t}",
                   "the brief in the last commit of {b} is {n} characters, the limit is {t}"),
    "brief": ("Справка:\n{b}", "Brief:\n{b}"),
    "files": ("Файлы:\n{s}", "Files:\n{s}"),
    "resume": ("Вопрос сессии: `{c}`", "Ask the session: `{c}`"),
    "ask_hot": ("Вопрос сессии: `claude attach {id}` — из кэша до {t}, позже — `{c}`",
                "Ask the session: `claude attach {id}` — from the cache until {t}, later — `{c}`"),
    "no_session": ("Сессии пункта нет — спросить некого", "No item session — nobody to ask"),
    "swept": ("{i}: час после вливания прошёл — сессия, worktree и ветка убраны",
              "{i}: the hour after the merge is over — session, worktree and branch removed"),
    "earlier": ("Часть работы раньше в main: {c}", "Part of the work was in main earlier: {c}"),
    "lint": ("после вливания линт нашёл бы: {e}", "after the merge the lint would report: {e}"),
    "v_ok": ("ок", "ok"),
    "v_refuse": ("отказ", "refused"),
    "v_unsure": ("не уверен", "unsure"),
    "review": ("ревью: {v} · {t} токенов", "review: {v} · {t} tokens"),
    "no_verdict": ("нет вердикта ревью — без него не вливаю: {e}", "no review verdict — not merging without one: {e}"),
    "review_refused": ("{r} — {w}\nВерни сессии {i} через SendMessage: «Ревью отказало: {w}. Исправь, сделай "
                       "rebase, прогони весь набор тестов и напиши, что готов»",
                       "{r} — {w}\nSend the {i} session via SendMessage: \"The review refused: {w}. Fix it, "
                       "rebase, run the whole test suite and report ready.\""),
    "slot": ("ждёт человека: ревью не уверено — {q}", "waiting on human: review unsure — {q}"),
    "slot_commit": ("[{i}] ждёт человека: ревью не уверено", "[{i}] waiting on human: review unsure"),
    "slot_body": ("{r} — {w}\nвопрос ревью: {q}\nотпечаток диффа: {p}", "{r} — {w}\nreview question: {q}\ndiff fingerprint: {p}"),
    "unsure": ("{r} — {w}\n{i} не влит: слот «ждёт человека» закоммичен ({h}). Спроси человека: «{q}» "
               "«Вливай» — замени слот на `решил человек: <ответ>`, закоммить и отправь сессии {i} через "
               "SendMessage: «сделай rebase на свежий main и прогони весь набор тестов»; «не вливай» или "
               "«поправь» — сними слот и отдай ответ сессии",
               "{r} — {w}\n{i} not merged: the \"waiting on human\" slot is committed ({h}). Ask the human: \"{q}\" "
               "\"Merge\" — replace the slot with `human decided: <answer>`, commit and send the {i} session via "
               "SendMessage: \"rebase onto a fresh main and run the whole test suite\"; \"don't merge\" or "
               "\"fix it\" — drop the slot and pass the answer to the session"),
    "no_answer": ("{i} ждёт человека, а ответ не записан — «вливай» пишется слотом `решил человек: <ответ>` "
                  "вместо `ждёт человека`",
                  "{i} is waiting on human and no answer is recorded — \"merge\" goes in as the slot "
                  "`human decided: <answer>` in place of `waiting on human`"),
    "decided": ("вопрос ревью: {q}\nрешил человек: {a}", "review question: {q}\nhuman decided: {a}"),
    "commit_failed": ("мердж сделан, файлы записаны, но коммит не прошёл: {e}\nЗакоммить: git commit -m \"{m}\" -- {f}",
                      "merged and files written, but the commit failed: {e}\nCommit: git commit -m \"{m}\" -- {f}"),
    "closed": ("[{i}] закрыт", "[{i}] closed"),
    "merged": ("{i} влит: `{r}`", "{i} merged: `{r}`"),
    "rebase": ("{i}: ветку сдвинул мердж {m} — отправь сессии {i} через SendMessage: «{m} в main. "
               "Сделай git rebase на свежий main и прогони весь набор тестов, прежде чем писать, что готов.»",
               "{i}: the merge of {m} moved its branch — send the {i} session via SendMessage: \"{m} is in main. "
               "Rebase onto a fresh main and run the whole test suite before reporting ready.\""),
    "pushed": ("push: {r}", "push: {r}"),
    "no_push": ("push пропущен: {w}", "push skipped: {w}"),
    "no_upstream": ("у ветки нет upstream", "the branch has no upstream"),
    "push_failed": ("push не прошёл: {e}", "push failed: {e}"),
    "cleanup": ("уборка {i}: {w}", "cleanup of {i}: {w}"),
    "waited": ("Ждали {i}: {l} — их живым сессиям: «{i} в main, сделай rebase»",
               "Waited on {i}: {l} — tell their live sessions: \"{i} is in main, rebase\""),
    "ready": ("Готовы к взятию: {l}", "Ready to take: {l}"),
    "inbox": ("В docs/roadmap/inbox/ файлов: {n} — разбери", "Files in docs/roadmap/inbox/: {n} — triage them"),
    "live": ("{i} в работе: сессия `{n}` {s}", "{i} in progress: session `{n}` {s}"),
    "attach": (" · `claude attach {id}`", " · `claude attach {id}`"),
    "abandoned": ("{i} брошен: в работе, а живой сессии `{n}` нет", "{i} abandoned: in progress, but no live session `{n}`"),
    "respawn": ("; последняя {id} — `claude respawn {id}`, затем `claude attach {id}`",
                "; the last one is {id} — `claude respawn {id}`, then `claude attach {id}`"),
    "orphan": ("сирота: worktree `.claude/worktrees/{i}`, а пункта {i} «в работе» нет — не удаляй сам, "
               "там могут быть незакоммиченные правки",
               "orphan: worktree `.claude/worktrees/{i}`, but item {i} is not in progress — don't delete it "
               "yourself, it may hold uncommitted changes"),
    "stray": ("лишняя: живая сессия `{n}` ({id}) не ведёт ни один пункт «в работе» — держит имя, "
              "новая сессия пункта получит суффикс",
              "stray: live session `{n}` ({id}) runs no in-progress item — it holds the name, "
              "a new session for the item gets a suffix"),
    "quiet": ("{i} тихо: без коммита {m} мин при пороге {t} — пометка, а не приговор: спроси сессию",
              "{i} quiet: no commit for {m} min, threshold {t} — a flag, not a verdict: ask the session"),
    "no_agents": ("сессии не сверены: нет `claude` или его вывод не JSON — брошенные и лишние не проверены",
                  "sessions not checked: no `claude` or its output isn't JSON — abandoned and stray not checked"),
    "hot": ("{i} закрыт, сессия открыта до {t} — `claude attach {id}`",
            "{i} closed, the session is open until {t} — `claude attach {id}`"),
    "cold": ("{i} закрыт, час прошёл", "{i} closed, the hour is over"),
    "gone": ("{i} закрыт, сессия остановлена", "{i} closed, the session is stopped"),
    "cold_ask": (" — вопрос: `{c}`", " — ask: `{c}`"),
    "cold_rm": (" · убрать: `claude rm {id}`", " · remove: `claude rm {id}`"),
    "waiting": ("ждёт человека — {w}", "waiting on human — {w}"),
    "clean": ("Брошенных, сирот и лишних нет", "No abandoned items, orphans or strays"),
    "not_ready": ("{i}: не готов к взятию — статус «{s}», зависимости: {d}; очередь — roadmap_lint.py --ready",
                  "{i}: not ready to take — status \"{s}\", dependencies: {d}; the queue is roadmap_lint.py --ready"),
    "no_paths": ("{i}: нет «Мои пути» — пересечение с пунктами в работе не проверить",
                 "{i}: no \"My paths\" — overlap with items in progress can't be checked"),
    "overlap": ("«Мои пути» пересекаются с пунктами в работе: {l} — параллельно их не запускают; "
                "решил человек — --force \"причина\"",
                "\"My paths\" overlap items in progress: {l} — they don't run in parallel; "
                "if the human decided otherwise — --force \"reason\""),
    "no_dispatch": ("{m} без .claude/rules/dispatch.md: файла нет — всё идёт на opus",
                    "{m} without .claude/rules/dispatch.md: no file — everything runs on opus"),
    "opus_zone": ("{m} на opus-зоне: {z} — эти пути ведёт только opus",
                  "{m} on an opus zone: {z} — these paths are opus only"),
    "fable_sonnet": ("советник fable у {m}: его унаследуют субагенты, выйдет дороже opus — советник opus",
                     "advisor fable for {m}: subagents inherit it, costlier than opus — use advisor opus"),
    "tail": ("хвост промпта {n} символов при пределе {t}: в нём только координация — что сдвинулось "
             "в main, окна на общие ресурсы; контекст разговора с человеком — в описание строки",
             "prompt tail is {n} characters, the limit is {t}: coordination only — what moved in main, "
             "windows on shared resources; the context of the conversation goes in the line's description"),
    "name_taken": ("имя {i} держит живая сессия {id} — брошенный пункт? mast status",
                   "live session {id} holds the name {i} — an abandoned item? mast status"),
    "branch_taken": ("ветка {b} уже есть — след прошлого захода? mast status",
                     "branch {b} already exists — left from an earlier run? mast status"),
    "row": ("🔨 в работе · `worktree-{i}` · сессия `{i}` · с {d}",
            "🔨 in progress · `worktree-{i}` · session `{i}` · since {d}"),
    "taken": ("[{i}] взят в работу · {m}", "[{i}] taken into work · {m}"),
    "started": ("{i} взят в работу · {m}: {h}", "{i} taken into work · {m}: {h}"),
    "prompt": ("Веди пункт {i} по скиллу {p}:managing-roadmap-items: строка в ROADMAP.md. "
               "Первым шагом — базовый замер.",
               "Drive item {i} per skill {p}:managing-roadmap-items: its line in ROADMAP.md. "
               "First step — the baseline measurement."),
    "alone": ("Соседей по путям в работе нет.", "No neighbors on nearby paths in progress."),
    "neighbors": ("Соседи по путям в работе: {l} — договаривайся напрямую.",
                  "Neighbors on nearby paths in progress: {l} — negotiate directly."),
    "neighbor": ("{i} (сессия `{n}`)", "{i} (session `{n}`)"),
    "dont_push": ("Не пушь: rebase на локальный {b}.", "Don't push: rebase onto the local {b}."),
    "start_failed": ("строка {i} помечена и закоммичена ({h}), а сессия не запустилась: {e}\nЗапусти: {c}",
                     "the {i} line is marked and committed ({h}), but the session didn't start: {e}\nRun: {c}"),
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


def paragraph(lines, first):
    """Строки блока до пустой строки или заголовка другого блока."""
    para = [first]
    for nxt in lines:
        if not nxt.strip() or any(h.match(nxt) for h in (THESIS, BRIEF, DEBT_HEAD, CRIT_LINE)):
            break
        para.append(nxt)
    return para


def blocks(body):
    """Тезис одной строкой, записи долга и справка из тела коммита; нет тезиса или справки — None."""
    lines, thesis, debt, brief = body.splitlines(), None, [], None
    for i, line in enumerate(lines):
        m, b = THESIS.match(line), BRIEF.match(line)
        if m and thesis is None:
            # Шапку строки DONE.md строит скрипт — из черновика берём только текст
            thesis = " ".join(p.strip() for p in paragraph(lines[i + 1:], m.group(1))
                              if p.strip() and not ITEM.match(p.strip()))
        elif b and brief is None:
            brief = textwrap.dedent("\n".join(paragraph(lines[i + 1:], b.group(1)))).strip()
        elif DEBT_HEAD.match(line):
            for nxt in lines[i + 1:]:
                if nxt.strip() and not nxt.startswith((" ", "\t", "- ")):
                    break
                debt.append(nxt)
    # Записи в TECH_DEBT.md разделены пустой строкой, а сессия пишет их в коммит подряд
    debt = re.sub(r"\s*\n(?=- )", "\n\n", textwrap.dedent("\n".join(debt)).strip())
    return thesis or None, debt, brief or None


def check(item, base, tip, crit):
    """Отказы по ветке: диапазон, файлы роадмапа, последний коммит. Возвращает (тезис, долг, справка)."""
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
    # Форма замера, не его правдивость: цифры смотрит диспетчер
    if "→" not in body and "->" not in body:
        raise Refusal(say("no_measure", b=b))
    thesis, debt, brief = blocks(body)
    if not thesis:
        raise Refusal(say("no_thesis", b=b))
    if not brief:
        raise Refusal(say("no_brief", b=b))
    if len(brief) > BRIEF_LIMIT:
        raise Refusal(say("long_brief", b=b, n=len(brief), t=BRIEF_LIMIT))
    return thesis, debt, brief


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


def ask_human(roadmap, item, question):
    """Слот «ждёт человека» последним в шапке строки пункта; прежний слот и устаревший ответ уходят."""
    lines = roadmap.split("\n")
    n = next(k for k, line in enumerate(lines) if (m := ITEM.match(line)) and m.group(1) == item)
    lines[n] = f"{DECIDED.sub('', WAITING.sub('', lines[n])).rstrip()} · {say('slot', q=question)}"
    return "\n".join(lines)


def fingerprint(diff):
    """Отпечаток диффа: rebase его не меняет, любая правка кода — меняет."""
    r = subprocess.run(["git", "patch-id", "--stable"], input=diff + "\n", capture_output=True, text=True,
                       encoding="utf-8")
    return (r.stdout.split() or [""])[0]


def asked(item):
    """(вопрос, отпечаток) из последнего коммита слота ревью этого пункта; нет — None."""
    body = git("log", "-1", "--format=%B", "-E", "--all-match", f"--grep=^\\[{item}\\] ",
               "--grep=^(отпечаток диффа|diff fingerprint): ", "HEAD")
    q, fp = ASKED.search(body), PRINT.search(body)
    return (q.group(1).strip(), fp.group(1)) if q and fp else None


def rule_paths(text):
    """Шаблоны `paths:` правила — списком или одним значением; поля нет — None: грузится всегда."""
    front = FRONT.match(text)
    m = front and RULE_PATHS.search(front.group(1))
    if not m:
        return None
    items = re.findall(r"-[ \t]*(.+)", m.group(2)) or [m.group(1)]
    return [x.strip().strip("\"'") for x in items if x.strip().strip("\"'")]


def memory(tip, files):
    """[(путь, текст)] — что получила бы сессия, тронувшая `files`: проектный CLAUDE.md и
    правила из дерева `tip` без `paths:` или с задевающими `files`, глобальный CLAUDE.md."""
    found = []
    for f in git("ls-tree", "-r", "--name-only", tip, "--", *PROJECT_MEMORY).splitlines():
        if f.startswith(".claude/rules/") and not f.endswith(".md"):
            continue
        text = git("show", f"{tip}:{f}")
        paths = rule_paths(text) if f.startswith(".claude/rules/") else None
        if paths is None or any(meet(segments(z), x.split("/")) for p in paths for z in braces(p) for x in files):
            found.append((f, text))
    glob = CLAUDE_HOME / "CLAUDE.md"
    if glob.is_file():
        found.append(("~/.claude/CLAUDE.md", glob.read_text(encoding="utf-8")))
    return found


def verdict(item, base, tip, body, head, do_push, roadmap, done):
    """Ревью с чистым контекстом. `ок` — строка вердикта; `отказ` или нет вердикта — отказ;
    `не уверен` — слот «ждёт человека» коммитом и выход. `решил человек` в ответ на вопрос
    ревью о том же диффе — вливание без ревьюера."""
    files = git("diff", "--name-only", base, tip).splitlines()
    strict = [f for f in files if any(meet(segments(z), f.split("/")) for z in RULE_FILES)]
    # STATUS.md, находки и промежуточные коммиты пункта — его история: до ревьюера не доходит.
    # Строка пункта — задание, сообщение последнего коммита — заявления автора
    diff = git("diff", "--no-color", base, tip, "--", *REVIEWED)
    fp = fingerprint(diff)
    decided = DECIDED.search(head)
    if decided:
        was = asked(item)
        # Дифф изменился после вопроса или вопрос был не от ревью — ответ не про этот дифф
        if was and was[1] == fp:
            return say("decided", q=was[0], a=decided.group(1).strip())
    elif WAITING.search(head):
        raise Refusal(say("no_answer", i=item))
    try:
        rules = memory(tip, git("diff", "--name-only", base, tip, "--", *REVIEWED).splitlines())
        v, reasons, question, tokens = ask(LANG, diff, body, git("log", "-1", "--format=%B", tip), rules, strict)
    except NoVerdict as e:
        raise Refusal(say("no_verdict", e=e))
    line, why = say("review", v=say(f"v_{v}"), t=f"{tokens:,}".replace(",", " ")), "; ".join(reasons)
    if v == "ok":
        return line
    if v == "refuse":
        raise Refusal(say("review_refused", r=line, w=why, i=item))
    question = " ".join((question or why).split())
    new = ask_human(roadmap, item, question)
    old = set(lint(roadmap, done, LANG))
    errors = [e for e in lint(new, done, LANG) if e not in old]
    if errors:
        raise Refusal(say("lint", e="; ".join(errors)))
    write(ROADMAP, new)
    r = run("git", "commit", "-q", "-m", say("slot_commit", i=item),
            "-m", say("slot_body", r=line, w=why, q=question, p=fp), "--", ROADMAP)
    if r.returncode:
        write(ROADMAP, roadmap)
        raise Refusal(f"git commit: {(r.stderr or r.stdout).strip()}")
    notes = push([]) if do_push else [say("no_push", w="--no-push")]
    sys.exit("\n".join([say("unsure", r=line, w=why, i=item, h=git("rev-parse", "--short=7", "HEAD"),
                            q=question)] + notes))


def close(item, tip, do_push, a):
    """Отказы и ревью, затем ff-мердж и одна правка трёх файлов одним коммитом. В его теле —
    справка, файлы и команда вопроса к сессии `a`. Возвращает диапазон, вердикт ревью и
    справку с файлами."""
    base = git("rev-parse", "HEAD")
    roadmap, done, debt_text = read(ROADMAP), read(DONE), read(DEBT)
    row = parse(roadmap)[0][item]
    crit = criterion(row["body"])
    thesis, debt, brief = check(item, base, tip, crit)
    # Список файлов — от git, а не пересказ модели
    told = [say("brief", b=brief), say("files", s=run("git", "diff", "--stat", base, tip).stdout.rstrip())]
    # Второй заход или работа в основной копии: диапазон ветки — не вся работа, архив называет остальное
    earlier = earlier_work(item)
    tail = [say("earlier", c="; ".join(earlier))] if earlier else []
    new_roadmap = drop_row(roadmap, item)
    new_done = add_thesis(done, section(roadmap, item), thesis_entry(item, row, base, tip, " ".join([thesis] + tail)))
    old = set(lint(roadmap, done, LANG))
    errors = [e for e in lint(new_roadmap, new_done, LANG) if e not in old]
    if errors:
        raise Refusal(say("lint", e="; ".join(errors)))
    review = verdict(item, base, tip, row["body"], row["head"], do_push, roadmap, done)

    git("merge", "-q", "--ff-only", tip)
    changed = [ROADMAP, DONE] + ([DEBT] if debt else [])
    write(ROADMAP, new_roadmap)
    write(DONE, new_done)
    if debt:
        write(DEBT, (debt_text.rstrip("\n") + "\n\n" if debt_text else "") + debt + "\n")
    # В коммит — команда, которая переживёт уборку сессии: полный sessionId
    ask = [say("resume", c=resume(a))] if a and a.get("sessionId") else []
    msg = "\n\n".join([say("closed", i=item), review] + tail + told + ask)
    r = run("git", "add", "--", *changed)
    r = r if r.returncode else run("git", "commit", "-q", "-m", msg, "--", *changed)
    if r.returncode:
        # Мердж уже сделан: не «отказ, ничего не изменено», а выход с тем, что доделать
        sys.exit(say("commit_failed", e=(r.stderr or r.stdout).strip(), m=msg, f=" ".join(changed)))
    return f"{base[:7]}..{tip[:7]}", review, told


def worktree_path(item):
    return Path.cwd() / ".claude" / "worktrees" / item


def agents():
    """Сессии из `claude agents --json --all`; нет `claude` или вывод не JSON — None."""
    if not shutil.which("claude"):
        return None
    try:
        return json.loads(run("claude", "agents", "--json", "--all").stdout)
    except ValueError:
        return None


def session(path, listed):
    """Сессия из `listed`, чей cwd — worktree пункта: живая раньше, свежая раньше; нет — None."""
    real = os.path.realpath(path)
    own = sorted((a for a in listed or [] if os.path.realpath(a.get("cwd") or "/") == real),
                 key=lambda a: (not alive(a), -a.get("startedAt", 0)))
    return own[0] if own else None


def resume(a):
    """Вопрос сессии после часа: работает и после `claude rm`, и при живой `--bg` сессии —
    её саму `--resume` не поднимает, форк получает всю историю."""
    return f"claude --resume {a['sessionId']} --fork-session"


def last_message(sid):
    """Время последней записи транскрипта сессии — от него живёт кэш; транскрипта нет — 0."""
    found = (CLAUDE_HOME / "projects").glob(f"*/{sid}.jsonl") if sid else []
    return max((f.stat().st_mtime for f in found), default=0)


def clock(ts):
    return time.strftime("%H:%M", time.localtime(ts))


def ask_line(a):
    """Чем спросить сессию влитого пункта: в горячий час — `claude attach`, потом — форк."""
    if not a or not a.get("sessionId"):
        return say("no_session")
    until = last_message(a["sessionId"]) + HOUR
    if alive(a) and a.get("id") and until > time.time():
        return say("ask_hot", id=a["id"], t=clock(until), c=resume(a))
    return say("resume", c=resume(a))


def item_trees():
    """Пункты с worktree в `.claude/worktrees/`; worktree субагентов (`agent-…`) — не пункты."""
    trees = os.path.realpath(os.path.join(os.getcwd(), ".claude", "worktrees"))
    paths = (os.path.realpath(line[9:]) for line in git("worktree", "list", "--porcelain").splitlines()
             if line.startswith("worktree "))
    return {Path(p).name for p in paths if os.path.dirname(p) == trees and ID.match(Path(p).name)}


def closed_items():
    """Закрытые пункты: в DONE.md вне «Снято» и не в ROADMAP.md."""
    archived, dropped = split_ledger(read(DONE))
    return set(archived) - set(dropped) - set(parse(read(ROADMAP))[0])


def closed_trees(listed):
    """[(пункт, его сессия или None)] — закрытые пункты, чей worktree ещё на месте."""
    return [(i, session(worktree_path(i), listed)) for i in sorted(item_trees() & closed_items())]


def sweep(merged=None):
    """Уборка закрытых пунктов, чей час прошёл, кроме только что влитого. Зовут `mast merge`
    и `mast start` после успеха: отказ ничего не меняет, а `mast status` только сверяет."""
    notes = []
    for item, a in closed_trees(agents()):
        if item != merged and (last_message(a.get("sessionId")) if a else 0) + HOUR < time.time():
            notes += [say("swept", i=item)] + [say("cleanup", i=item, w=n) for n in cleanup(item, a)]
    return notes


def cleanup(item, a):
    """Сессия `a`, worktree и ветка пункта. Сбой уборки не отменяет вливание — он в вывод."""
    path, branch, notes = worktree_path(item), f"worktree-{item}", []
    if a and a.get("id"):
        r = run("claude", "rm", a["id"])
        if r.returncode:
            notes.append(f"claude rm {a['id']}: {(r.stderr or r.stdout).strip()}")
    listed = [os.path.realpath(line[9:]) for line in git("worktree", "list", "--porcelain").splitlines()
              if line.startswith("worktree ")]
    if os.path.realpath(path) in listed:
        r = run("git", "worktree", "remove", str(path))
        if r.returncode:
            notes.append(r.stderr.strip())
    # `claude rm` удаляет сессию вместе с её worktree и веткой — ветки может уже не быть.
    # `-d`, а не `-D`: ветка, ушедшая вперёд после вливания, остаётся с причиной в выводе
    if ok("rev-parse", "-q", "--verify", branch):
        r = run("git", "branch", "-d", branch)
        if r.returncode:
            notes.append(r.stderr.strip())
    return notes


def moved(old_head, item):
    """Текст для сессий пунктов «в работе», чьи ветки сдвинул этот мердж: их база — old_head."""
    return [say("rebase", i=other, m=item) for other, row in parse(read(ROADMAP))[0].items()
            if row["status"] == "в работе" and ok("merge-base", "--is-ancestor", old_head, f"worktree-{other}")]


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


def main_copy(cmd):
    """Переход в корень основной копии; из worktree или без роадмапа — отказ."""
    os.chdir(git("rev-parse", "--show-toplevel"))
    if os.path.realpath(git("rev-parse", "--git-dir")) != os.path.realpath(git("rev-parse", "--git-common-dir")):
        raise Refusal(say("main_copy", c=cmd))
    if not Path(ROADMAP).is_file():
        raise Refusal(say("no_roadmap"))


def merge(item, do_push):
    main_copy("merge")
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
    a = session(worktree_path(item), agents())
    span, review, told = close(item, tip, do_push, a)
    out = [say("merged", i=item, r=span), review] + told + [ask_line(a)]
    # Коммит закрытия сделан: «отказ, ничего не изменено» отсюда — ложь, сбой идёт строкой вывода
    try:
        out += push([branch]) if do_push else [say("no_push", w="--no-push")]
        out += sweep(item)
        out += moved(old_head, item)
    except Refusal as e:
        out.append(str(e))
    waited = [j for j, r in parse(read(ROADMAP))[0].items() if item in r["deps"]]
    if waited:
        out.append(say("waited", i=item, l=", ".join(waited)))
    free = ready(read(ROADMAP), read(DONE))
    if free:
        out.append(say("ready", l=", ".join(free)))
    inbox = [p for p in Path("docs/roadmap/inbox").glob("*") if p.is_file()]
    if inbox:
        out.append(say("inbox", n=len(inbox)))
    print("\n".join(out))
    return 0


def braces(pattern):
    """`db/*.{sql,md}` → `db/*.sql`, `db/*.md`."""
    m = re.search(r"\{([^{}]*)\}", pattern)
    if not m:
        return [pattern]
    return [p for alt in m.group(1).split(",") for p in braces(pattern[:m.start()] + alt + pattern[m.end():])]


def segments(pattern):
    """Сегменты шаблона; путь без маски и расширения — каталог, `reports` = `reports/**`."""
    segs = pattern.strip().strip("`").strip("/").split("/")
    return segs + ["**"] if not re.search(r"[*?\[]|.\.", segs[-1]) else segs


def meet(a, b):
    """Есть путь, подходящий под оба списка сегментов; `**` — любое их число."""
    if a and a[0] == "**":
        return meet(a[1:], b) or bool(b) and meet(a, b[1:])
    if b and b[0] == "**":
        return meet(b, a)
    if not a or not b:
        return not a and not b
    return (fnmatchcase(a[0], b[0]) or fnmatchcase(b[0], a[0])) and meet(a[1:], b[1:])


def overlap(a, b):
    """Два шаблона путей задевают общий файл — по самим шаблонам, без файлов на диске:
    пересечение с ещё не созданными файлами тоже пересечение."""
    return any(meet(segments(x), segments(y)) for x in braces(a) for y in braces(b))


def paths_of(row):
    m = PATHS.search(row["body"])
    return [p.strip() for p in m.group(1).split(",") if p.strip()] if m else []


def zones():
    """Пути, которые ведёт только opus: из dispatch.md проекта и правила агента."""
    found = [z for m in ZONE.finditer(read(DISPATCH)) for z in re.split(r"[\s·,`]+", m.group(1)) if z]
    return found + ALWAYS_OPUS


def mark(roadmap, item):
    """Строка пункта «в работе»: слоты где, сессия и дата — на месте статуса и прочерка."""
    lines = roadmap.split("\n")
    n = next(k for k, line in enumerate(lines) if (m := ITEM.match(line)) and m.group(1) == item)
    s = STATUS.search(lines[n])
    rest = re.sub(r"^\s*·\s*—(?=\s*(?:·|$))", "", lines[n][s.end():])
    lines[n] = f"{lines[n][:s.start() + 1]} {say('row', i=item, d=datetime.date.today().strftime('%d.%m'))}{rest}"
    return "\n".join(lines)


def start(item, model, advisor, force, tail, do_push):
    """Отказы, затем строка «в работе» коммитом, push и фоновая сессия пункта."""
    main_copy("start")
    roadmap, done = read(ROADMAP), read(DONE)
    items = parse(roadmap)[0]
    row = items.get(item)
    if not row:
        raise Refusal(say("no_item", i=item))
    if item not in ready(roadmap, done):
        raise Refusal(say("not_ready", i=item, s=row["status"], d=", ".join(row["deps"]) or "—"))
    mine = paths_of(row)
    if not mine:
        raise Refusal(say("no_paths", i=item))
    near = {}
    for other, r in items.items():
        hit = r["status"] == "в работе" and next((q for q in paths_of(r) if any(overlap(q, p) for p in mine)), None)
        if hit:
            m = SESSION.search(r["head"])
            near[other] = (hit, m.group(1) if m else other)
    if near and not force:
        raise Refusal(say("overlap", l=", ".join(f"{i} (`{q}`)" for i, (q, _) in near.items())))
    if model != "opus":
        if not Path(DISPATCH).is_file():
            raise Refusal(say("no_dispatch", m=model))
        hot = [z for z in zones() if any(overlap(z, p) for p in mine)]
        if hot:
            raise Refusal(say("opus_zone", m=model, z=", ".join(hot)))
        if advisor == "fable":
            raise Refusal(say("fable_sonnet", m=model))
    if len(tail) > TAIL_LIMIT:
        raise Refusal(say("tail", n=len(tail), t=TAIL_LIMIT))
    root = os.path.realpath(os.getcwd()) + os.sep
    holder = next((a for a in agents() or [] if a.get("name") == item and alive(a)
                   and (os.path.realpath(a.get("cwd") or "/") + os.sep).startswith(root)), None)
    if holder:
        raise Refusal(say("name_taken", i=item, id=holder.get("id") or f"pid {holder.get('pid')}"))
    branch = f"worktree-{item}"
    if ok("rev-parse", "-q", "--verify", branch):
        raise Refusal(say("branch_taken", b=branch))
    if git("status", "--porcelain", "--", ROADMAP):
        raise Refusal(say("dirty", f=ROADMAP))
    base = git("symbolic-ref", "--short", "HEAD")
    new = mark(roadmap, item)
    old = set(lint(roadmap, done, LANG))
    errors = [e for e in lint(new, done, LANG) if e not in old]
    if errors:
        raise Refusal(say("lint", e="; ".join(errors)))

    write(ROADMAP, new)
    msg = say("taken", i=item, m=model) + (f"\n\n--force: {force}" if force else "")
    r = run("git", "commit", "-q", "-m", msg, "--", ROADMAP)
    if r.returncode:
        write(ROADMAP, roadmap)
        raise Refusal(f"git commit: {(r.stderr or r.stdout).strip()}")
    head = git("rev-parse", "HEAD")
    out = [say("started", i=item, m=model, h=head[:7])]
    out += push([]) if do_push else [say("no_push", w="--no-push")]
    pushed = run("git", "rev-parse", "-q", "--verify", "@{u}").stdout.strip() == head

    prompt = [say("prompt", i=item, p=PLUGIN[LANG])]
    prompt.append(say("neighbors", l=", ".join(say("neighbor", i=i, n=n) for i, (_, n) in near.items()))
                  if near else say("alone"))
    prompt += [] if pushed else [say("dont_push", b=base)]
    prompt += [tail] if tail else []
    cmd = ["claude", "--bg", "--worktree", item, "--name", item, "--model", model, "--advisor", advisor,
           "--settings", BASE_HEAD, " ".join(prompt)]
    r = run(*cmd) if shutil.which("claude") else None
    sid = r and ATTACH.search(ANSI.sub("", r.stdout))
    out += sweep() if sid else []
    print("\n".join(out))
    if not sid:
        # Коммит уже сделан: не «отказ, ничего не изменено», а что сделано и как запустить
        sys.exit(say("start_failed", i=item, h=head[:7], e=(r.stderr or r.stdout).strip() if r else "no claude",
                     c=shlex.join(cmd)))
    print(f"claude attach {sid.group(1)}")
    return 0


def alive(a):
    """Процесс сессии жив — у него есть `pid` или `status`. `state` не в счёт: `claude stop`
    оставляет `done`, обрыв API — `blocked`, а процесса нет; `done` с живым процессом — ход
    кончен, сессия ждёт промпта."""
    return a.get("pid") is not None or a.get("status") is not None


def silence_threshold():
    m = SILENCE.search(read(".claude/rules/dispatch.md"))
    return int(m.group(1)) if m else SILENCE_DEFAULT


def quiet_minutes(item, started_ms):
    """Минуты с последнего коммита `[X-N]` или старта сессии — что позже: после
    перезапуска старый коммит ветки тишиной не считается."""
    branch = f"worktree-{item}"
    ref = branch if ok("rev-parse", "-q", "--verify", branch) else "HEAD"
    last = run("git", "log", "-1", "--format=%ct", "-F", f"--grep=[{item}]", ref).stdout.strip()
    return int((time.time() - max(int(last or 0), started_ms / 1000)) // 60)


def status():
    """Текст сверки. Корень — основная копия: из worktree пункта сверяется то же самое."""
    tree = git("worktree", "list", "--porcelain").splitlines()
    root = os.path.realpath(tree[0][len("worktree "):])
    os.chdir(root)
    if not Path(ROADMAP).is_file():
        raise Refusal(say("no_roadmap"))
    in_work = {i: r for i, r in parse(read(ROADMAP))[0].items() if r["status"] == "в работе"}
    trees = os.path.join(root, ".claude", "worktrees")
    listed = agents()
    # Сессии других проектов на машине сверку не касаются
    mine = [a for a in listed or [] if (os.path.realpath(a.get("cwd") or "/") + os.sep).startswith(root + os.sep)]
    threshold, out, bad, taken = silence_threshold(), [], [], set()
    for item, row in in_work.items():
        if listed is None:
            break
        m = SESSION.search(row["head"])
        name, wt = m.group(1) if m else item, os.path.join(trees, item)
        # Живая раньше мёртвой, по имени раньше, чем по cwd, свежая раньше старой
        own = sorted((a for a in mine if a.get("name") == name or os.path.realpath(a.get("cwd") or "/") == wt),
                     key=lambda a: (not alive(a), a.get("name") != name, -a.get("startedAt", 0)))
        if not own or not alive(own[0]):
            dead = own[0].get("id") if own else None
            bad.append(say("abandoned", i=item, n=name) + (say("respawn", id=dead) if dead else ""))
            continue
        a = own[0]
        taken.add(a.get("sessionId"))
        state = "/".join(filter(None, (a.get("state"), a.get("status"))))
        out.append(say("live", i=item, n=a.get("name"), s=state) + (say("attach", id=a["id"]) if a.get("id") else ""))
        quiet = quiet_minutes(item, a.get("startedAt", 0))
        if quiet > threshold:
            out.append(say("quiet", i=item, m=quiet, t=threshold))
    closed = closed_trees(mine)
    for item, a in closed if listed is not None else []:
        taken |= {a.get("sessionId")} if a else set()
        out.append(closed_line(item, a))
    bad += [say("orphan", i=i) for i in sorted(item_trees() - set(in_work) - {i for i, _ in closed})]
    # Имя закрытого пункта держать незачем: его не возьмут снова — сессия вопроса к нему не лишняя
    done = closed_items()
    bad += [say("stray", n=a["name"], id=a.get("id") or f"pid {a.get('pid')}") for a in mine
            if alive(a) and (m := ITEM_NAME.match(a.get("name") or "")) and m.group(1) not in done
            and a.get("sessionId") not in taken]
    out += bad
    if listed is None:
        out.append(say("no_agents"))
    elif not bad:
        out.append(say("clean"))
    out += [say("waiting", w=w) for w in waiting(read(ROADMAP))]
    inbox = [p for p in Path("docs/roadmap/inbox").glob("*") if p.is_file()]
    if inbox:
        out.append(say("inbox", n=len(inbox)))
    return "\n".join(out)


def closed_line(item, a):
    """Строка сверки закрытого пункта: до какого часа сессия отвечает из кэша, потом — чем спросить."""
    until = (last_message(a.get("sessionId")) if a else 0) + HOUR
    if a and alive(a) and a.get("id") and until > time.time():
        return say("hot", i=item, t=clock(until), id=a["id"])
    line = say("cold" if a and alive(a) else "gone", i=item)
    line += say("cold_ask", c=resume(a)) if a and a.get("sessionId") else ""
    return line + (say("cold_rm", id=a["id"]) if a and a.get("id") else "")


def start_args(args):
    """(модель, советник, причина --force, хвост) из аргументов после X-N; не разобрать — None."""
    opts, tail, it = {}, [], iter(args)
    for a in it:
        if a in ("--model", "--advisor", "--force"):
            opts[a] = next(it, None)
            if opts[a] is None:
                return None
        elif a.startswith("--"):
            return None
        else:
            tail.append(a)
    model = opts.get("--model", "opus")
    if model not in ("opus", "sonnet"):
        return None
    advisor = opts.get("--advisor") or ("fable" if model == "opus" else "opus")
    return model, advisor, opts.get("--force"), " ".join(tail).strip()


def main():
    global LANG
    args = sys.argv[1:]
    lang = args.pop(0) if args[:1] and args[0] in PLUGIN else None
    do_push = "--no-push" not in args
    args = [a for a in args if a != "--no-push"]
    LANG = lang or detect_lang(read(ROADMAP))
    started = args[:1] == ["start"] and len(args) > 1 and ID.match(args[1]) and start_args(args[2:])
    if args != ["status"] and not started and (len(args) != 2 or args[0] != "merge" or not ID.match(args[1])):
        print(say("usage"), file=sys.stderr)
        return 2
    try:
        if args == ["status"]:
            print(status())
            return 0
        if started:
            return start(args[1], *started, do_push)
        return merge(args[1], do_push)
    except Refusal as e:
        print(say("refused") + str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
