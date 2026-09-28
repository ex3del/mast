"""Тексты `mast` на двух языках: ключ — (ru, en). Язык выбирает `mast.say()`."""

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
    "deploy": ("{i}: в `.claude/mast.md` объявлен прод — отправь сессии {i} через SendMessage: «{i} влит. "
               "Если пункт требует выкладки — выложи по процедуре проекта и пришли проверку.»",
               "{i}: `.claude/mast.md` declares prod — send the {i} session via SendMessage: \"{i} is merged. "
               "If the item needs a deploy, deploy it per the project's procedure and send back the check.\""),
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
