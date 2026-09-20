# A-1 Плагин MAST: ядро в SessionStart, процедуры скиллами, команда /init-project

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development` (рекомендуется) или `superpowers:executing-plans`. Шаги отмечаются чекбоксами.

**Goal:** плагин MAST, который ставится из GitHub, вкладывает ядро метода в каждую сессию и разворачивает или причёсывает каркас проекта командой `/init-project`.

**Architecture:** ядро метода (≤ 6000 символов) вкладывает `SessionStart`-хук; тяжёлые процедуры лежат скиллами и грузятся по надобности; `roadmap_lint.py` висит на `PostToolUse` для `ROADMAP.md`; тексты в двух локалях, код общий; каркас в чужой проект пишет команда под надзором человека.

**Tech Stack:** Markdown, Python 3 (только stdlib), pytest, формат плагинов Claude Code.

**Spec:** [SPEC.md](SPEC.md)

**Мои пути:** `.claude-plugin/**`, `hooks/**`, `skills/**`, `commands/**`, `locales/**`, `tests/**`, `docs/roadmap/A-1/**`
**Не трогаю:** всё остальное
**Готово когда:** плагин ставится на чистой машине двумя командами и не меняет ни байта в `~/.claude/CLAUDE.md` и `~/.claude/settings.json`; текст ядра ≤ 6000 символов при лимите 10 000; `/init-project` в пустом каталоге разворачивает каркас за один прогон; `/init-project --check` на чужом проекте меняет 0 файлов; сторож локалей показывает 0 расхождений в структуре заголовков `ru` и `en`.

## Global Constraints

- Код рантайма — Python 3 **только stdlib**; pytest нужен лишь тестам.
- Любой путь внутри плагина — через `${CLAUDE_PLUGIN_ROOT}`. `$HOME/.claude/...` запрещён.
- Ядро любой локали — **≤ 6000 символов** (лимит площадки 10 000).
- Локали `ru` и `en` равноправны: одинаковый состав файлов и одинаковое дерево заголовков.
- Версия в `plugin.json` поднимается в том же коммите, что и изменение поведения.
- Минимальная версия Claude Code — **2.1.234**.
- Сообщения коммитов — `[A-1] описание`, без conventional commits и без соавторства Claude.
- Плагин не пишет в `~/.claude` пользователя и не трогает файлы его проекта без подтверждения.

## File Structure

| Путь | Ответственность |
|---|---|
| `.claude-plugin/plugin.json` | имя, версия, `userConfig.language` |
| `.claude-plugin/marketplace.json` | запись маркетплейса `ex3del`, источник `./` |
| `.mcp.json` | удалённый сервер Context7 |
| `hooks/hooks.json` | `SessionStart` → `core.py`, `PostToolUse` на `ROADMAP.md` → `roadmap_lint.py` |
| `hooks/core.py` | выбрать локаль, решить, вкладывать ли ядро, напечатать его |
| `hooks/roadmap_lint.py` | проверка формата роадмапа и очередь готовых пунктов |
| `locales/<язык>/core.md` | текст ядра |
| `locales/<язык>/skills/<имя>.md` | тела скиллов |
| `locales/<язык>/templates/*.md` | шаблоны каркаса: `CLAUDE.md`, `ROADMAP.md`, правило с `paths:` |
| `skills/<имя>/SKILL.md` | фронтматтер и указатель на локализованное тело |
| `commands/init-project.md` | сценарий разворачивания и ревизии |
| `tests/` | сторожа́ |

## Task 1: Скелет плагина и сторож манифестов

**Files:**
- Create: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `tests/test_plugin_manifest.py`

**Interfaces:**
- Produces: имя плагина `mast`, имя маркетплейса `ex3del`, ключ `userConfig.language` со значениями `ru`/`en`.

- [ ] **Шаг 1: Написать падающий тест**

```python
# tests/test_plugin_manifest.py
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(name):
    return json.loads((ROOT / ".claude-plugin" / name).read_text())


def test_манифест_плагина_объявляет_имя_версию_и_язык():
    m = load("plugin.json")
    assert m["name"] == "mast"
    assert m["version"].count(".") == 2          # семвер
    lang = m["userConfig"]["language"]
    assert lang["type"] == "string"
    assert lang["options"] == ["ru", "en"]
    assert lang["default"] == "ru"


def test_маркетплейс_ссылается_на_этот_же_репозиторий():
    m = load("marketplace.json")
    assert m["name"] == "ex3del"
    assert m["owner"]["name"]
    entry = next(p for p in m["plugins"] if p["name"] == "mast")
    assert entry["source"] == "./"
    assert entry["description"] and entry["license"]
```

- [ ] **Шаг 2: Прогнать и убедиться, что падает**

Запуск: `cd ~/Documents/mast && pytest tests/test_plugin_manifest.py -v`
Ожидаемо: FAIL — файла `.claude-plugin/plugin.json` нет.

- [ ] **Шаг 3: Написать манифесты**

```json
// .claude-plugin/plugin.json
{
  "name": "mast",
  "version": "0.1.0",
  "description": "Method for Agents, Sessions and Tasks — roadmap items, worktree per item, dispatcher, path-scoped rules",
  "license": "MIT",
  "userConfig": {
    "language": {
      "type": "string",
      "title": "Language of MAST texts",
      "options": ["ru", "en"],
      "default": "ru"
    }
  }
}
```

```json
// .claude-plugin/marketplace.json
{
  "name": "ex3del",
  "owner": { "name": "ex3del", "url": "https://github.com/ex3del" },
  "plugins": [
    {
      "name": "mast",
      "source": "./",
      "description": "Roadmap items with measurable criteria, worktree per item, dispatcher, path-scoped rules",
      "category": "productivity",
      "tags": ["workflow", "roadmap", "worktree", "planning"],
      "license": "MIT"
    }
  ]
}
```

- [ ] **Шаг 4: Прогнать тест — зелёный**

Запуск: `pytest tests/test_plugin_manifest.py -v` → PASS.

- [ ] **Шаг 5: Коммит**

```bash
git add .claude-plugin tests/test_plugin_manifest.py
git commit -m "[A-1] манифест плагина и маркетплейс ex3del"
```

## Task 2: Ядро в двух локалях и два сторожа

**Files:**
- Create: `locales/ru/core.md`, `locales/en/core.md`, `tests/test_core_size.py`, `tests/test_locales.py`
- Source: `~/Documents/claude/CLAUDE.md`, строки 37–59, 76–87, 109–117, 129–136

**Interfaces:**
- Produces: `locales/<язык>/core.md` — единственный текст, попадающий в каждую сессию.

- [ ] **Шаг 1: Написать падающие тесты**

```python
# tests/test_core_size.py
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIMIT = 6000          # наш потолок; лимит площадки 10 000


def test_ядро_каждой_локали_влезает_в_лимит():
    for core in sorted(ROOT.glob("locales/*/core.md")):
        size = len(core.read_text())
        assert size <= LIMIT, f"{core}: {size} символов"
```

```python
# tests/test_locales.py
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCALES = ROOT / "locales"


def files(lang):
    return {p.relative_to(LOCALES / lang) for p in (LOCALES / lang).rglob("*.md")}


def headings(path):
    return re.findall(r"^(#{1,6})(?= )", path.read_text(), re.M)


def test_состав_файлов_локалей_совпадает():
    assert files("ru") == files("en")


def test_дерево_заголовков_совпадает():
    for rel in sorted(files("ru")):
        assert headings(LOCALES / "ru" / rel) == headings(LOCALES / "en" / rel), rel
```

- [ ] **Шаг 2: Прогнать — падают оба**

Запуск: `pytest tests/test_core_size.py tests/test_locales.py -v`
Ожидаемо: FAIL — каталога `locales/` нет.

- [ ] **Шаг 3: Перенести четыре секции движка в `locales/ru/core.md`**

Дословно из `~/Documents/claude/CLAUDE.md`: «Где что записывать» (37–59), «Планирование» (76–87), «Кто занят задачей» (109–117), «Параллельные сессии в одной копии» (129–136). Правок при переносе ровно две:

1. Личные пути вида `~/.claude/skills/...` заменить на роль («скилл ведения пунктов»).
2. В конец добавить блок указателей:

```markdown
## Подробности — в скиллах

- структура документов проекта → скилл `mast:project-structure`
- цикл worktree, вливание ветки пункта, роль диспетчера → скилл `mast:worktree-flow`
- ведение пунктов, находки, закрытие → скилл `mast:managing-roadmap-items`
```

- [ ] **Шаг 4: Сделать английскую копию `locales/en/core.md`**

Перевод секция в секцию, дерево заголовков то же. `ROADMAP.md`, `worktree`, `paths:` не переводятся.

- [ ] **Шаг 5: Прогнать сторожа́ — зелёные**

Запуск: `pytest tests/test_core_size.py tests/test_locales.py -v` → PASS.
Фактический размер обеих локалей записать в `Журнал`.

- [ ] **Шаг 6: Коммит**

```bash
git add locales tests/test_core_size.py tests/test_locales.py
git commit -m "[A-1] ядро метода в двух локалях, сторожа размера и совпадения локалей"
```

## Task 3: Хук SessionStart

**Files:**
- Create: `hooks/core.py`, `hooks/hooks.json`, `tests/test_core_hook.py`

**Interfaces:**
- Consumes: `locales/<язык>/core.md` из Task 2.
- Produces: `hooks/core.py` с `pick_language(env) -> str` и `render(project_dir, root, lang) -> str`; печатает текст в stdout.

- [ ] **Шаг 1: Написать падающий тест**

```python
# tests/test_core_hook.py
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "hooks"))
import core  # noqa: E402


def test_язык_берётся_из_окружения_иначе_русский():
    assert core.pick_language({"CLAUDE_PLUGIN_OPTION_LANGUAGE": "en"}) == "en"
    assert core.pick_language({"CLAUDE_PLUGIN_OPTION_LANGUAGE": "de"}) == "ru"
    assert core.pick_language({}) == "ru"


def test_в_проекте_с_роадмапом_вкладывается_полное_ядро(tmp_path):
    (tmp_path / "ROADMAP.md").write_text("- **A-1** что-то\n")
    assert core.render(tmp_path, ROOT, "ru") == (ROOT / "locales/ru/core.md").read_text()


def test_в_проекте_без_метода_только_строка_указатель(tmp_path):
    out = core.render(tmp_path, ROOT, "ru")
    assert len(out) < 300
    assert "/init-project" in out
```

- [ ] **Шаг 2: Прогнать — падает**

Запуск: `pytest tests/test_core_hook.py -v` → FAIL, модуля `core` нет.

- [ ] **Шаг 3: Написать `hooks/core.py`**

```python
#!/usr/bin/env python3
"""SessionStart: вкладывает ядро метода MAST в контекст сессии."""
import os
import sys
from pathlib import Path

LANGS = ("ru", "en")
HINT = {
    "ru": "В этом проекте метод MAST не развёрнут. Развернуть — команда `/init-project`.",
    "en": "MAST is not set up in this project. Run `/init-project` to scaffold it.",
}


def pick_language(env):
    """Язык из настройки плагина; неизвестное значение — русский."""
    lang = env.get("CLAUDE_PLUGIN_OPTION_LANGUAGE", "ru")
    return lang if lang in LANGS else "ru"


def render(project_dir, root, lang):
    """Полное ядро там, где метод развёрнут, иначе одна строка-указатель."""
    project_dir = Path(project_dir)
    deployed = (project_dir / "ROADMAP.md").exists() or (project_dir / ".claude" / "rules").is_dir()
    if not deployed:
        return HINT[lang]
    return (Path(root) / "locales" / lang / "core.md").read_text()


def main():
    root = os.environ.get("CLAUDE_PLUGIN_ROOT", str(Path(__file__).resolve().parent.parent))
    project = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    print(render(project, root, pick_language(os.environ)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Шаг 4: Объявить хук**

```json
// hooks/hooks.json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup",
        "hooks": [
          { "type": "command", "command": "python3", "args": ["${CLAUDE_PLUGIN_ROOT}/hooks/core.py"] }
        ]
      }
    ]
  }
}
```

Exec-форма с `args` обязательна: в shell-форме подстановка настроек пользователя запрещена.

- [ ] **Шаг 5: Прогнать тесты — зелёные**

Запуск: `pytest tests/test_core_hook.py -v` → PASS.

- [ ] **Шаг 6: Проверить на живом плагине**

```bash
claude --plugin-dir ~/Documents/mast -p "перечисли правила метода, которые видишь в контексте"
```
Ожидаемо: в ответе видно содержание ядра. Результат — в `Журнал`.

- [ ] **Шаг 7: Коммит**

```bash
git add hooks tests/test_core_hook.py
git commit -m "[A-1] SessionStart-хук: ядро в контекст, вне развёрнутого проекта — одна строка"
```

## Task 4: Линт роадмапа на PostToolUse

**Files:**
- Create: `hooks/roadmap_lint.py` (перенос из `~/Documents/claude/skills/managing-roadmap-items/roadmap_lint.py`), `tests/test_roadmap_lint.py` (перенос из `~/Documents/claude/tests/`)
- Modify: `hooks/hooks.json`

**Interfaces:**
- Produces: `parse(text)`, `lint(text, ledger="") -> list[str]`, `ready(text, ledger="")`, CLI `roadmap_lint.py [--ready] ROADMAP.md`.

- [ ] **Шаг 1: Перенести и прогнать как есть**

```bash
cp ~/Documents/claude/skills/managing-roadmap-items/roadmap_lint.py hooks/
cp ~/Documents/claude/tests/test_roadmap_lint.py tests/
pytest tests/test_roadmap_lint.py -v
```
Ожидаемо: PASS. Упал импорт — поправить в тесте путь на `hooks/`, больше ничего не менять.

- [ ] **Шаг 2: Добавить падающий тест на новое требование**

```python
def test_критерий_без_числа_ловится():
    text = (
        "- **A-1** Экспорт — запланирован\n"
        "  Мои пути: src/**\n"
        "  Готово когда: работает хорошо.\n"
    )
    assert any("числ" in claim.lower() for claim in lint(text))
```

- [ ] **Шаг 3: Прогнать — падает**

Запуск: `pytest tests/test_roadmap_lint.py -k числ -v` → FAIL.

- [ ] **Шаг 4: Реализовать проверку**

В `lint()`: если строка «Готово когда» не содержит ни одной цифры — жалоба «критерий без числа: приёмка превратится в спор».

- [ ] **Шаг 5: Прогнать весь набор**

Запуск: `pytest -v` → PASS.

- [ ] **Шаг 6: Подключить хук**

В `hooks/hooks.json` в `PostToolUse` добавить **два отдельных условия** — на `Edit(**/ROADMAP.md)` и на `Write(**/ROADMAP.md)`: в одном условии `Write` не ловится. Команда — `python3` с аргументом `${CLAUDE_PLUGIN_ROOT}/hooks/roadmap_lint.py`.

- [ ] **Шаг 7: Коммит**

```bash
git add hooks tests/test_roadmap_lint.py
git commit -m "[A-1] линт роадмапа на PostToolUse, проверка числа в критерии"
```

## Task 5: Скиллы процедур

**Files:**
- Create: `skills/managing-roadmap-items/SKILL.md`, `skills/project-structure/SKILL.md`, `skills/worktree-flow/SKILL.md`
- Create: `locales/{ru,en}/skills/{managing-roadmap-items,project-structure,worktree-flow}.md`

**Interfaces:**
- Consumes: имена скиллов из указателей ядра (Task 2) — должны совпадать дословно.

- [ ] **Шаг 1: Проверить подстановку настройки в теле скилла**

Временный скилл с телом `язык = ${user_config.language}`, запуск `claude --plugin-dir ~/Documents/mast`, вызов скилла.
- Подставилось → тело каждого скилла = одна строка «прочитай `${CLAUDE_PLUGIN_ROOT}/locales/${user_config.language}/skills/<имя>.md` и следуй ему».
- Не подставилось → два комплекта: `skills/<имя>/` (английский) и `skills/<имя>-ru/`, ядро отсылает по языку.

Итог записать в `Принятые решения` с пометкой «проверено на живом плагине».

- [ ] **Шаг 2: Перенести тексты в русскую локаль**

- `managing-roadmap-items.md` — склейка `SKILL.md`, `item.md`, `dispatcher.md` из `~/Documents/claude/skills/managing-roadmap-items/`, личные пути заменены на `${CLAUDE_PLUGIN_ROOT}`.
- `project-structure.md` — секция «Структура проекта» (строки 60–75 исходного `CLAUDE.md`).
- `worktree-flow.md` — «Работа через worktree» (88–108) плюс «Диспетчер роадмапа» (118–128).

- [ ] **Шаг 3: Написать фронтматтеры**

`description` на английском с русскими ключевыми словами внутри — по нему скилл и выбирается:

```markdown
---
name: worktree-flow
description: Use when taking a roadmap item into work or merging its branch — worktree per item, commit prefix, merge by the main copy. Вызывать при взятии пункта в работу и вливании ветки.
---
```

- [ ] **Шаг 4: Английские копии текстов**

`locales/en/skills/*.md` с тем же деревом заголовков.

- [ ] **Шаг 5: Прогнать сторожа́**

Запуск: `pytest -v` → PASS, включая совпадение локалей.

- [ ] **Шаг 6: Коммит**

```bash
git add skills locales
git commit -m "[A-1] три скилла процедур и их тексты в двух локалях"
```

## Task 6: `/init-project` — разворачивание в новом проекте

**Files:**
- Create: `commands/init-project.md`, `locales/{ru,en}/templates/{CLAUDE.md,ROADMAP.md,rule.md}`, `tests/test_templates.py`

**Interfaces:**
- Consumes: линт из Task 4.
- Produces: сценарий команды и шаблоны, которые она копирует.

- [ ] **Шаг 1: Написать падающий тест на шаблоны**

```python
# tests/test_templates.py
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_шаблон_роадмапа_проходит_собственный_линт(tmp_path):
    dst = tmp_path / "ROADMAP.md"
    dst.write_text((ROOT / "locales/ru/templates/ROADMAP.md").read_text())
    r = subprocess.run([sys.executable, str(ROOT / "hooks/roadmap_lint.py"), str(dst)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_шаблон_правила_несёт_paths():
    assert (ROOT / "locales/ru/templates/rule.md").read_text().startswith("---\npaths:")
```

- [ ] **Шаг 2: Прогнать — падает**

Запуск: `pytest tests/test_templates.py -v` → FAIL, шаблонов нет.

- [ ] **Шаг 3: Написать шаблоны**

- `ROADMAP.md` — заголовок, раздел `## A.`, один пример пункта с «Готово когда» с числом; проходит линт.
- `CLAUDE.md` — скелет проектных правил: куда смотреть, стек, команды, инварианты, пометка «держать до 200 строк».
- `rule.md` — правило с фронтматтером `paths:` и одним правилом внутри.

- [ ] **Шаг 4: Написать `commands/init-project.md`, режим разворачивания**

Сценарий: разведка (стек, тесты, remote, какие файлы уже есть) → показать список того, что будет создано → создать после подтверждения → прогнать линт → напечатать, что человеку делать дальше. Явно: существующий файл не перезаписывается, такой случай уходит в режим ревизии (Task 7).

- [ ] **Шаг 5: Прогнать тесты и команду вживую**

```bash
pytest -v
mkdir -p /tmp/mast-new && cd /tmp/mast-new && git init -q
claude --plugin-dir ~/Documents/mast -p "/init-project"
```
Ожидаемо: каркас создан, линт зелёный. Сколько файлов и сколько вопросов — в `Журнал`.

- [ ] **Шаг 6: Коммит**

```bash
git add commands locales tests/test_templates.py
git commit -m "[A-1] /init-project: разворачивание каркаса в новом проекте"
```

## Task 7: `/init-project` — ревизия существующего проекта

**Files:**
- Modify: `commands/init-project.md`
- Create: `tests/test_init_check.py`, `tests/fixtures/legacy/` (образец чужого проекта)

**Interfaces:**
- Consumes: линт из Task 4, шаблоны из Task 6.
- Produces: три шага ревизии и четыре ограждения из спеки.

- [ ] **Шаг 1: Написать падающий тест на образец**

```python
# tests/test_init_check.py
import hashlib
from pathlib import Path

FIX = Path(__file__).resolve().parent / "fixtures" / "legacy"


def snapshot(root):
    return {p.relative_to(root): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def test_образец_содержит_все_случаи_ревизии():
    names = {p.name for p in FIX.rglob("*") if p.is_file()}
    assert {"CLAUDE.md", "TODO.md", "CHANGELOG.md"} <= names
    assert len((FIX / "CLAUDE.md").read_text().splitlines()) > 200
    rule = next(FIX.glob(".claude/rules/*.md"))
    assert not rule.read_text().startswith("---")      # правило без paths:


def test_снимок_образца_считается():
    """Тем же снимком проверяется вручную, что --check не изменил ни файла."""
    assert snapshot(FIX)
```

- [ ] **Шаг 2: Прогнать — падает**

Запуск: `pytest tests/test_init_check.py -v` → FAIL, образца нет.

- [ ] **Шаг 3: Создать образец `tests/fixtures/legacy/`**

`CLAUDE.md` на 200+ строк со смесью правил и справочника; `TODO.md` со списком задач прозой; `.claude/rules/db.md` без фронтматтера; `CHANGELOG.md` с закрытой работой; `.claude/worktrees/` без строки в `.gitignore`.

- [ ] **Шаг 4: Дописать в команду три шага ревизии**

Опись (что нашли и какую роль играет) → предложения по файлам, каждое диффом и отдельным вопросом → применение принятого и прогон линта. Дословно перенести четыре ограждения из спеки: числа в критериях не придумываются; дерево git должно быть чистым; молчаливой перезаписи нет; версия Claude Code проверяется.

- [ ] **Шаг 5: Прогон вживую на копии образца**

```bash
cp -R ~/Documents/mast/tests/fixtures/legacy /tmp/mast-legacy
cd /tmp/mast-legacy && git init -q && git add -A && git commit -qm init
claude --plugin-dir ~/Documents/mast -p "/init-project --check"
git status --porcelain      # ожидаемо пусто
```
Пустой `git status` — и есть выполнение критерия «`--check` меняет 0 файлов». В `Журнал`.

- [ ] **Шаг 6: Коммит**

```bash
git add commands tests
git commit -m "[A-1] /init-project: ревизия чужого проекта — опись, предложения, применение"
```

## Task 8: Context7, README и проверка установки

**Files:**
- Create: `.mcp.json`, `README.md`, `README.ru.md`
- Modify: `.claude-plugin/plugin.json` (версия `0.1.0` → `1.0.0`, ключ `context7_key`)

**Interfaces:**
- Consumes: всё предыдущее.
- Produces: устанавливаемый плагин.

- [ ] **Шаг 1: Добавить MCP-сервер**

```json
// .mcp.json
{
  "mcpServers": {
    "context7": {
      "type": "http",
      "url": "https://mcp.context7.com/mcp",
      "headers": { "CONTEXT7_API_KEY": "${user_config.context7_key}" }
    }
  }
}
```

В `userConfig` добавить `context7_key`: `"type": "string"`, `"sensitive": true`, **без** `required` — без ключа работает бесплатный режим.

- [ ] **Шаг 2: Написать README на двух языках**

Обязательно: три шага установки (добавить маркетплейс, поставить плагин, **включить автообновление**), требование Claude Code ≥ 2.1.234, что делает `/init-project`, чем ядро отличается от скиллов, как сменить язык.

- [ ] **Шаг 3: Проверить установку как посторонний**

```bash
md5 ~/.claude/CLAUDE.md ~/.claude/settings.json          # до
claude plugin marketplace add ex3del/mast
claude plugin install mast@ex3del --scope user
md5 ~/.claude/CLAUDE.md ~/.claude/settings.json          # после
```
Совпадение контрольных сумм — выполнение критерия «не меняет ни байта». В `Журнал`.

- [ ] **Шаг 4: Поднять версию и закоммитить**

```bash
git add -A
git commit -m "[A-1] Context7 комплектом, README на двух языках, версия 1.0.0"
```

## Ритм журнала

После каждой задачи — строка в `Журнал`: что сделано и какое число получено. Замеры снимаются теми же командами, что перечислены в шагах.

## Журнал

- 20.09 — базовый замер «до»: плагина нет, репозиторий пуст. Ядро в `~/.claude/CLAUDE.md` (строки 37–136) — **10 710 символов**, команда замера `sed -n '37,136p' CLAUDE.md | wc -m`; в одну вставку `SessionStart` (лимит 10 000) не помещается. `/init-project` в старом виде — 158 строк, вызовов за всю историю транскриптов (с 08.06) — 0.

## Проблемы

## Принятые решения

- **Метод едет плагином, а не через `install.sh`.** Плагин физически не может изменить `~/.claude/CLAUDE.md` и `settings.json` пользователя — именно это и нужно, чтобы отдавать метод посторонним. У `install.sh` такой защиты нет, и истории обновлений тоже.
- **Ядро отделено от процедур.** Лимит вставки `SessionStart` — 10 000 символов, движок весит 10 710. В ядро уходят четыре секции (≈4,3 тыс. символов), остальные три — в скиллы по надобности.
- **Каркас в проекте не обновляется вместе с плагином.** `ROADMAP.md` и правила пользователя принадлежат ему; команда пишет их один раз и потом только показывает расхождения.
- **Ветки «жить с чужим форматом» нет.** Линт ругается на любой невалидный `ROADMAP.md` одинаково. Либо человек принимает формат, либо не ставит плагин: каждое исключение — лишняя ветка поведения, которую потом никто не проверяет.
- **Ревизия мигрирует, а не отчитывается.** Причесать репозиторий к эталону — и есть смысл команды. Безопасность даёт не отказ от правок, а дифф на каждый файл, чистое дерево git перед применением и запрет придумывать числа в «Готово когда».
- **Context7 едет комплектом: правило и MCP-сервер.** Удалённое подключение без ключа; ключ — необязательное `sensitive`-поле. Правило ссылается на инструмент по роли, иначе у человека с уже настроенным Context7 будет два сервера.
- **Минимальная версия Claude Code — 2.1.234**: на ней `SendMessage` и `ListAgents` доехали до всех платформ, а без них нет ни диспетчера, ни правил про параллельные сессии. Поля в манифесте для этого нет, проверяет сама команда.
- **Версия в `plugin.json` поднимается при каждом релизе.** При явной версии обновление у пользователей происходит только при её повышении: коммиты без bump'а не доезжают вообще. Забыли поднять — выпустили релиз, которого никто не получил.
- **Автообновление сторонних маркетплейсов выключено по умолчанию** (включено только у официальных). Значит в README третий шаг: включить его в `/plugin` или прописать `extraKnownMarketplaces` с `autoUpdate: true`. Обещание «обновления приезжают сами» без этого шага неверно.
