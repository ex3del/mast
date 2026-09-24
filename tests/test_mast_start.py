"""`mast start X-N` на git-фикстуре: отказы до любых изменений, пометка строки, коммит,
запуск фоновой сессии и `claude attach <id>` последней строкой.

Окружение и заглушка `claude` — из `test_mast_merge.py`: на `--bg` заглушка печатает
id с цветами, как живой `claude`, а аргументы вызова пишет в `FAKE_LOG`.
"""
import datetime
import json
import subprocess
import sys

import pytest

from test_mast_merge import BIN, ROOT, Project, env  # noqa: F401 — env нужен как фикстура

sys.path.insert(0, str(ROOT / "hooks"))
import mast  # noqa: E402
from roadmap_lint import lint  # noqa: E402

ROADMAP = """# Роадмап

## B. Отчёты

- **B-1** Экспорт PDF — 🔨 в работе · `worktree-B-1` · сессия `B-1` · с 20.09
  Мои пути: reports/**
  Готово когда: отчёт на 500 строк < 3 с.

- **B-2** Экспорт CSV — запланирован · —
  Мои пути: csv/**, api/routes/export.py
  Готово когда: пустой отчёт — 200 за < 50 мс.

- **B-3** Экспорт XLSX — запланирован · —
  Зависит от: B-1
  Мои пути: xlsx/**
  Готово когда: 10 листов < 1 с.

- **B-4** Шрифты PDF — запланирован · —
  Мои пути: reports/fonts/*.ttf
  Готово когда: кириллица в 3 шрифтах из 3.

- **B-5** Вход по токену — запланирован · —
  Мои пути: auth/login.py
  Готово когда: вход < 200 мс.

- **B-6** Правила агента — запланирован · —
  Мои пути: CLAUDE.md
  Готово когда: CLAUDE.md ≤ 200 строк.

- **B-7** Без путей — запланирован · —
  Готово когда: 1 из 1.
"""
DISPATCH = '---\npaths:\n  - "auth/**"\n---\n\n- `auth/**` — только opus: утечка сессий\n'
TODAY = datetime.date.today().strftime("%d.%m")


class Start(Project):
    def __init__(self, tmp_path, env):
        super().__init__(tmp_path, env)
        self.commit({"ROADMAP.md": ROADMAP}, "[B-1] взят в работу")

    def start(self, *args, lang="ru"):
        return self.mast("start", *args, lang=lang)

    def calls(self):
        log = self.tmp / "claude.log"
        return [l for l in log.read_text(encoding="utf-8").splitlines() if l.startswith("--bg")] \
            if log.exists() else []

    def row(self, item):
        return next(l for l in self.read("ROADMAP.md").splitlines() if l.startswith(f"- **{item}**"))


@pytest.fixture
def p(tmp_path, env):  # noqa: F811
    return Start(tmp_path, env)


def refused(p, needle, *args):
    before = p.state()
    r = p.start(*args)
    out = r.stdout + r.stderr
    assert r.returncode == 1, out
    assert out.startswith("Отказ, ничего не изменено"), out
    assert needle in out, out
    assert p.state() == before, "отказ обязан ничего не менять"
    assert p.calls() == [], "отказ не запускает сессию"


# --- четыре отказа из критерия ---

@pytest.mark.parametrize("item", ["B-3", "B-1"])
def test_отказ_неготовый_пункт(p, item):
    """B-3 ждёт B-1, который ещё в работе; B-1 уже взят."""
    refused(p, f"{item}: не готов к взятию", item)


def test_отказ_пересечение_путей_без_force(p):
    refused(p, "B-1 (`reports/**`)", "B-4")


@pytest.mark.parametrize("item, zone", [("B-5", "auth/**"), ("B-6", "CLAUDE.md")])
def test_отказ_sonnet_на_opus_зоне(p, item, zone):
    """Зона из dispatch.md проекта и правила агента — всегда opus, в любом проекте."""
    p.commit({".claude/rules/dispatch.md": DISPATCH}, "зоны")
    refused(p, zone, item, "--model", "sonnet")


def test_отказ_fable_у_sonnet(p):
    p.commit({".claude/rules/dispatch.md": DISPATCH}, "зоны")
    refused(p, "fable", "B-2", "--model", "sonnet", "--advisor", "fable")


# --- соседние отказы ---

def test_отказ_sonnet_без_dispatch_md(p):
    """Файла нет — всё идёт на opus: sonnet проект подключает осознанно."""
    refused(p, ".claude/rules/dispatch.md", "B-2", "--model", "sonnet")


def test_отказ_хвост_длиннее_300(p):
    refused(p, "301", "B-2", "я" * 301)


def test_отказ_нет_моих_путей(p):
    refused(p, "Мои пути", "B-7")


def test_отказ_имя_держит_живая_сессия(p):
    """Движок выдал бы `B-2-<слово>` — это симптом брошенного пункта, а не повод для суффикса."""
    (p.tmp / "agents.json").write_text(json.dumps([
        {"id": "old00001", "name": "B-2", "cwd": str(p.root), "state": "working", "pid": 1, "status": "busy"}]))
    refused(p, "old00001", "B-2")


def test_отказ_ветка_пункта_уже_есть(p):
    """Движок взял бы её базой вместе со старыми коммитами прошлого захода."""
    p.git("branch", "worktree-B-2")
    refused(p, "worktree-B-2", "B-2")


def test_отказ_из_worktree(p):
    p.git("worktree", "add", "-q", str(p.worktree("B-1")), "-b", "worktree-B-1")
    before = p.state()
    r = subprocess.run([str(BIN["ru"]), "start", "B-2"], cwd=p.worktree("B-1"), env=p.env,
                       capture_output=True, text=True)
    assert r.returncode == 1 and "основной копии" in r.stderr, r.stdout + r.stderr
    assert p.state() == before


# --- запуск ---

def test_запуск_помечает_строку_коммитит_и_стартует(p):
    r = p.start("B-2", "В main влит B-0: общий рендер.")
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip().splitlines()[-1] == "claude attach fakeid01", r.stdout
    assert p.row("B-2") == f"- **B-2** Экспорт CSV — 🔨 в работе · `worktree-B-2` · сессия `B-2` · с {TODAY}"
    assert p.git("log", "-1", "--format=%s") == "[B-2] взят в работу · opus"
    assert p.git("status", "--porcelain") == ""
    assert lint(p.read("ROADMAP.md"), p.read("docs/roadmap/DONE.md")) == []
    [call] = p.calls()
    # Upstream нет — push не было: worktree от локального HEAD, сессии — не пушить
    assert call.startswith('--bg --worktree B-2 --name B-2 --model opus --advisor fable '
                           '--settings {"worktree":{"baseRef":"head"}} '), call
    assert call.endswith("Веди пункт B-2 по скиллу mast-ru:managing-roadmap-items: строка в ROADMAP.md. "
                         "Первым шагом — базовый замер. Соседей по путям в работе нет. "
                         "Не пушь: rebase на локальный main. В main влит B-0: общий рендер."), call


def test_sonnet_с_советником_opus(p):
    p.commit({".claude/rules/dispatch.md": DISPATCH}, "зоны")
    r = p.start("B-2", "--model", "sonnet")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "--model sonnet --advisor opus" in p.calls()[0]
    assert p.git("log", "-1", "--format=%s") == "[B-2] взят в работу · sonnet"


def test_force_с_причиной_в_коммит_соседи_в_промпт(p):
    r = p.start("B-4", "--force", "шрифты рендер не трогают — решил человек")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "шрифты рендер не трогают — решил человек" in p.git("log", "-1", "--format=%b")
    assert "Соседи по путям в работе: B-1 (сессия `B-1`) — договаривайся напрямую." in p.calls()[0]


@pytest.fixture
def upstream(p):
    bare = p.tmp / "origin.git"
    p.git("init", "-q", "--bare", str(bare))
    p.git("remote", "add", "origin", str(bare))
    p.git("push", "-q", "-u", "origin", "main")
    return bare


def test_push_есть_upstream(p, upstream):
    r = p.start("B-2")
    assert r.returncode == 0, r.stdout + r.stderr
    assert p.git("rev-parse", "origin/main") == p.head()
    assert "Не пушь" not in p.calls()[0]


def test_no_push_при_upstream(p, upstream):
    before = p.git("rev-parse", "origin/main")
    r = p.start("B-2", "--no-push")
    assert r.returncode == 0, r.stdout + r.stderr
    assert p.git("rev-parse", "origin/main") == before
    assert "Не пушь: rebase на локальный main." in p.calls()[0]


def test_сессия_не_стартовала_после_коммита(p):
    """Коммит уже сделан — не «отказ, ничего не изменено», а что сделано и команда запуска."""
    p.env = {**p.env, "FAKE_BG_FAIL": "нет сети"}
    r = p.start("B-2")
    out = r.stdout + r.stderr
    assert r.returncode == 1 and not out.startswith("Отказ"), out
    assert "нет сети" in out and "claude --bg --worktree B-2 --name B-2" in out, out
    assert p.git("log", "-1", "--format=%s") == "[B-2] взят в работу · opus"


def test_английский_плагин(p):
    p.commit({"ROADMAP.md": "# Roadmap\n\n## B. Reports\n\n- **B-2** CSV export — planned · —\n"
                            "  My paths: csv/**\n  Done when: empty report — 200 in < 50 ms.\n"}, "en")
    r = p.start("B-2", lang="en")
    assert r.returncode == 0, r.stdout + r.stderr
    assert p.row("B-2") == f"- **B-2** CSV export — 🔨 in progress · `worktree-B-2` · session `B-2` · since {TODAY}"
    assert p.git("log", "-1", "--format=%s") == "[B-2] taken into work · opus"
    assert "Drive item B-2 per skill mast:managing-roadmap-items: its line in ROADMAP.md." in p.calls()[0]


# --- пересечение путей ---

@pytest.mark.parametrize("a, b, hit", [
    ("hooks/**", "hooks/mast.py", True),
    ("plugins/*/**", "plugins/ru/bin/mast", True),
    ("plugins/*/hooks/**", "plugins/*/locales/*/**", False),
    ("db/**/*.{sql,md}", "db/m/1.sql", True),
    ("db/**/*.{sql,md}", "db/m/1.py", False),
    ("reports", "reports/a.py", True),
    ("tests/**", "hooks/**", False),
    ("README.md", "README.ru.md", False),
])
def test_пересечение_путей(a, b, hit):
    assert mast.overlap(a, b) is hit
    assert mast.overlap(b, a) is hit
