# A-13 Хук роли диспетчера: вопрос человеку и запись в основной копии

**Мои пути:** hooks/**, plugins/*/**, tests/**
**Не трогаю:** `hooks/core.py`, `hooks/roadmap_lint.py`, `hooks/roadmap_watch.py` (A-12); `hooks/mast.py`, `plugins/*/bin/mast`, разделы «Вливание» и «Снятие пункта» скилла диспетчера, шаги 4–5 `worktree-flow.md`, «Последний коммит несёт всё для архива» в скилле сессии пункта (A-14); `ROADMAP.md`, `DONE.md`, `TECH_DEBT.md` — основная копия.
**Готово когда:** на установленном плагине в сессии `--name <x>-dispatch`: `AskUserQuestion` — отказ с причиной 1 из 1; Edit `README.md` в основной копии — отказ 1 из 1; Edit `ROADMAP.md` — проходит 1 из 1; правка `README.md` субагентом с `isolation: worktree` — проходит 1 из 1; в сессии без роли те же 4 вызова — 0 отказов; роль определена у `--bg`-сессии 1 из 1 (каким путём — в коммите); ядро ≤ 8200 символов в обоих языках.

## Задачи

1. `hooks/dispatcher.py`: SessionStart пишет файл роли `${CLAUDE_PLUGIN_DATA}/<session_id>.role`, если `session_title` кончается на `-dispatch`; PreToolUse у диспетчера (файл роли или `MAST_ROLE=dispatcher`) — deny `AskUserQuestion` и Edit/Write в основной копии вне `ROADMAP.md`, `docs/roadmap/**`, `TECH_DEBT.md`; путь под `.claude/worktrees/` и вне проекта — пропуск. Тесты — `tests/test_dispatcher.py`, subprocess с временными `CLAUDE_PLUGIN_DATA`/`CLAUDE_PROJECT_DIR`.
2. Разводка `plugins/*/hooks/hooks.json`: второй элемент SessionStart, группа PreToolUse `AskUserQuestion|Edit|Write`; `tests/test_hooks_wiring.py`; `tools/sync_plugins.py`; бамп версии.
3. Скилл диспетчера, раздел «Когда спрашивать человека» — одно предложение о хуке, оба языка.
4. Живая проверка через `tools/serve_marketplace.py`: сессия `--bg --name <x>-dispatch` и сессия без роли, по 4 вызова.

## Журнал

- 23.09 — базовый замер на `405029a` (плагин 3.3.3 в дереве, 3.3.2 установлен):
  - `grep -c PreToolUse plugins/{en,ru}/hooks/hooks.json` → 0 и 0; `grep -rl AskUserQuestion hooks/` → пусто: хука нет, отказов 0 из 4 по построению.
  - `wc -m plugins/*/locales/*/core.md` → en 8147, ru 7485.
  - Проба сигнала роли: проект с `.claude/settings.json`, хуки SessionStart/UserPromptSubmit/PreToolUse пишут stdin в файл; `claude -p --name probe-dispatch` и `claude --bg --name probe-dispatch` (2.1.281) — `session_title: "probe-dispatch"` есть в SessionStart (`source: startup`) и UserPromptSubmit, **нет в PreToolUse**; `session_id` один на все три события. `CLAUDE_CODE_SESSION_NAME` до хуков не доходит: в бинаре он в списке переменных, вырезаемых из env дочерних процессов.
  - Фоновой сессии нужен доверенный корень git ровно по пути (родитель не считается): живые прогоны — в `/private/tmp/mast-check-new` и `/private/tmp/mast-check-legacy`.
  - Живой «до» на установленном `mast-ru@ex3del` 3.3.2, проект `git init` + `ROADMAP.md` + `README.md`, промпт «ровно 4 вызова: Edit README, Edit ROADMAP, `Agent` с `isolation: worktree` правит README, `AskUserQuestion`», разбор — по транскрипту `~/.claude/projects/<slug>/<id>.jsonl`:
    - `claude --bg --name before-dispatch`: Edit README и Edit ROADMAP — отказ **площадки**, не метода: «This background session hasn't isolated its changes yet. Call EnterWorktree first»; субагент правит `.claude/worktrees/agent-<id>/README.md` — прошло; `AskUserQuestion` — модальный вопрос, сессия в `blocked`. Отказов хука 0 из 4.
    - `claude -p --name before-p-dispatch`: Edit README, Edit ROADMAP, субагент — прошли 3 из 3; `AskUserQuestion` в `-p` недоступен вовсе.

- 23.09 — хук `hooks/dispatcher.py`, разводка, сторожа, фраза в скилле диспетчера, 3.3.4 (коммит «[A-13] хук роли диспетчера»). `pytest` — 140 passed. Мутации хука ловятся тестами 4 из 4: `ask` вместо `deny` (10 падений), без правила worktree (1), без `resolve()` (1), роль по префиксу вместо суффикса (2). Накладные на Edit/Write у сессии без роли — медиана 18,5 мс из 30 запусков (`python3 -c pass` — 13,2 мс).

## План живой проверки «после»

Встроенный запрет `--bg`-сессии на правку основной копии снимается только настройкой проекта `"worktree": {"bgIsolation": "none"}`; её выключение отклонил классификатор режима auto — не обхожу. Поэтому: три правки — в `claude -p --name <x>-dispatch` и в `-p` без роли; `AskUserQuestion` и определение роли — в `claude --bg --name <x>-dispatch` и в `--bg` без роли.

## Проблемы

## Принятые решения

- Роль — файлом `${CLAUDE_PLUGIN_DATA}/<session_id>.role` из SessionStart, а не чтением транскрипта в PreToolUse: `session_title` в PreToolUse не приходит, транскрипт на каждый Edit читать дорого. Переменная берётся из env хука, а не из `args`: сторож разводки пропускает в `args` только пути от `${CLAUDE_PLUGIN_ROOT}`.
- Роль следует за именем на каждом SessionStart: переименованная сессия файл роли теряет.
- Субагент с `isolation: worktree` приходит с тем же `session_id`, что диспетчер, — его отличает только путь: всё под `.claude/worktrees/` не основная копия. Файлы вне проекта (память, scratchpad) — тоже не основная копия, пропуск.
- Сбой хука не отказывает: необработанное исключение — exit 1, а площадка считает его неблокирующим. Без `CLAUDE_PLUGIN_DATA` (не Claude Code) хук падает так же — отдельной обработки нет.
- Предложение в скилле диспетчера («Когда спрашивать человека») описывает пол, а не потолок: отказ хука диспетчер предвидит, а не узнаёт после вызова. Ядро не тронуто: у en запас 53 символа.
