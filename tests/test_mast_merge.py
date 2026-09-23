"""`mast merge X-N` на git-фикстуре: вливание одной командой и rebase очереди готовых веток.

Команда запускается через обёртку `plugins/<язык>/bin/mast` — так же, как её зовёт
диспетчер из Bash. Вместо живого `claude` в PATH лежит заглушка: она отдаёт список
сессий из файла и пишет в журнал каждый вызов `claude rm`.
"""
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "hooks"))
import mast  # noqa: E402

BIN = {lang: ROOT / "plugins" / lang / "bin" / "mast" for lang in ("ru", "en")}

CRIT = {"B-1": "отчёт на 500 строк < 3 с.", "B-2": "пустой отчёт — 200 за < 50 мс."}
ROADMAP = f"""# Роадмап

## B. Отчёты

- **B-1** Экспорт PDF — 🔨 в работе · `worktree-B-1` · сессия `B-1` · с 20.09
  Мои пути: reports/**
  Готово когда: {CRIT["B-1"]}

- **B-2** Экспорт CSV — 🔨 в работе · `worktree-B-2` · сессия `B-2` · с 21.09
  Мои пути: csv/**
  Готово когда: {CRIT["B-2"]}

- **B-3** Экспорт XLSX — запланирован · —
  Зависит от: B-1
  Готово когда: 10 листов < 1 с.
"""
DONE = """# Закрытые пункты

## B. Отчёты

- **B-0** Первый отчёт — 01.09 · `1111111..2222222`
  Отчётов 0 → 1.
"""
DEBT = "# Технический долг\n\n- **Старый долг.** Грозит ничем. **Чиним** никогда.\n"
# Тесты «падают», если в дереве есть файл FAIL
DISPATCH = "# Модели и чувствительные зоны\n\nТесты: `test ! -e FAIL`\n"


def ready(item, thesis="Отчёт рендерится 8 с → 2 с.", debt=None):
    """Последний коммит готовой ветки — в той форме, что велит скилл сессии пункта."""
    msg = f"[{item}] готов\n\nГотово когда: {CRIT[item]}\nЗамер: было 8 с → стало 2 с.\n\nТезис: {thesis}\n"
    return msg + (f"\nTECH_DEBT.md:\n{debt}\n" if debt else "")


@pytest.fixture
def env(tmp_path):
    """Окружение без глобального конфига git и с заглушкой `claude` в PATH."""
    fake = tmp_path / "fakebin"
    fake.mkdir()
    (fake / "claude").write_text(
        '#!/bin/sh\n'
        'if [ "$1" = agents ]; then cat "$FAKE_AGENTS" 2>/dev/null || echo "[]"; exit 0; fi\n'
        'echo "$@" >> "$FAKE_LOG"\n')
    (fake / "claude").chmod(0o755)
    (tmp_path / "gitconfig").write_text("")
    return {**os.environ,
            "PATH": f"{fake}{os.pathsep}{os.environ['PATH']}",
            "GIT_CONFIG_GLOBAL": str(tmp_path / "gitconfig"), "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
            "FAKE_AGENTS": str(tmp_path / "agents.json"), "FAKE_LOG": str(tmp_path / "claude.log")}


class Project:
    def __init__(self, tmp_path, env, dispatch=DISPATCH):
        self.root, self.env, self.tmp = tmp_path / "p", env, tmp_path
        self.root.mkdir()
        files = {"ROADMAP.md": ROADMAP, "docs/roadmap/DONE.md": DONE, "TECH_DEBT.md": DEBT,
                 ".gitignore": ".claude/worktrees/\n", "reports/a.txt": "a\n"}
        if dispatch:
            files[".claude/rules/dispatch.md"] = dispatch
        self.write(self.root, files)
        self.git("init", "-q", "-b", "main")
        self.git("add", ".")
        self.git("commit", "-qm", "init")

    def git(self, *args, cwd=None, check=True):
        r = subprocess.run(["git", *args], cwd=cwd or self.root, env=self.env,
                           capture_output=True, text=True)
        assert r.returncode == 0 or not check, r.stderr
        return r.stdout.strip()

    @staticmethod
    def write(where, files):
        for rel, text in files.items():
            (where / rel).parent.mkdir(parents=True, exist_ok=True)
            (where / rel).write_text(text, encoding="utf-8")

    def worktree(self, item):
        return self.root / ".claude" / "worktrees" / item

    def branch(self, item, *commits):
        """Ветка пункта в своём worktree; каждый коммит — (файлы, сообщение)."""
        self.git("worktree", "add", "-q", str(self.worktree(item)), "-b", f"worktree-{item}")
        for files, msg in commits:
            self.commit(files, msg, cwd=self.worktree(item))

    def commit(self, files, msg, cwd=None):
        cwd = cwd or self.root
        self.write(cwd, files)
        self.git("add", ".", cwd=cwd)
        self.git("commit", "-qm", msg, cwd=cwd)

    def mast(self, *args, lang="ru"):
        return subprocess.run([str(BIN[lang]), *args], cwd=self.root, env=self.env,
                              capture_output=True, text=True)

    def read(self, rel):
        return (self.root / rel).read_text(encoding="utf-8")

    def head(self):
        return self.git("rev-parse", "HEAD")

    def state(self):
        """Всё, что вливание могло бы изменить: HEAD, три файла, ветки."""
        return (self.head(), self.read("ROADMAP.md"), self.read("docs/roadmap/DONE.md"),
                self.read("TECH_DEBT.md"), self.git("branch", "--list"))


@pytest.fixture
def p(tmp_path, env):
    return Project(tmp_path, env)


def refused(p, item, needle):
    before = p.state()
    r = p.mast("merge", item)
    assert r.returncode == 1, r.stdout + r.stderr
    assert needle in r.stdout + r.stderr, r.stdout + r.stderr
    assert p.state() == before, "отказ обязан ничего не менять"


# --- четыре отказа из критерия и соседние ---

def test_отказ_не_fast_forward(p):
    """Обычная причина — диспетчер закоммитил строку другого пункта после rebase ветки.
    Отказ обязан говорить про rebase, а не «ветка правит ROADMAP.md»."""
    p.branch("B-1", ({"reports/pdf.py": "1\n"}, ready("B-1")))
    p.commit({"ROADMAP.md": ROADMAP.replace("Экспорт XLSX", "Экспорт XLSX и ODS")}, "[B-3] взят в работу")
    refused(p, "B-1", "сессия пункта делает rebase")


def test_отказ_чужой_коммит_в_диапазоне(p):
    p.branch("B-1", ({"csv/x.py": "1\n"}, "[B-2] чужая правка"),
             ({"reports/pdf.py": "1\n"}, ready("B-1")))
    refused(p, "B-1", "[B-2] чужая правка")


@pytest.mark.parametrize("rel", ["ROADMAP.md", "docs/roadmap/DONE.md", "TECH_DEBT.md"])
def test_отказ_ветка_задела_файлы_роадмапа(p, rel):
    p.branch("B-1", ({rel: "правка из ветки\n"}, "[B-1] правлю чужое"),
             ({"reports/pdf.py": "1\n"}, ready("B-1")))
    refused(p, "B-1", rel)


def test_отказ_последний_коммит_без_готово_когда(p):
    p.branch("B-1", ({"reports/pdf.py": "1\n"}, "[B-1] готов\n\nТезис: отчёт 8 с → 2 с.\n"))
    refused(p, "B-1", "Готово когда")


def test_отказ_критерий_пересказан(p):
    p.branch("B-1", ({"reports/pdf.py": "1\n"},
                     ready("B-1").replace(CRIT["B-1"], "отчёт быстрее трёх секунд")))
    refused(p, "B-1", "дословно")


def test_отказ_без_замеров(p):
    p.branch("B-1", ({"reports/pdf.py": "1\n"},
                     ready("B-1").replace("Замер: было 8 с → стало 2 с.", "Замер: быстро.")
                                 .replace("8 с → 2 с", "стало 2 с")))
    refused(p, "B-1", "было → стало")


def test_отказ_без_тезиса(p):
    p.branch("B-1", ({"reports/pdf.py": "1\n"}, f"[B-1] готов\n\nГотово когда: {CRIT['B-1']}\n8 с → 2 с.\n"))
    refused(p, "B-1", "Тезис")


def test_отказ_часть_работы_уже_в_main(p):
    """Второй заход или правка в основной копии — нестандартный случай, к человеку."""
    p.commit({"reports/early.py": "1\n"}, "[B-1] начало в основной копии")
    p.branch("B-1", ({"reports/pdf.py": "1\n"}, ready("B-1")))
    refused(p, "B-1", "[B-1] начало в основной копии")


def test_отказ_нет_ветки(p):
    refused(p, "B-1", "worktree-B-1")


def test_отказ_пункт_не_в_работе(p):
    refused(p, "B-3", "B-3")


@pytest.mark.parametrize("subject", ["[B-1] находка: токен не отзывается",
                                     "[B-1] заведён: токен не отзывается",
                                     "[B-1] взят в работу · opus"])
def test_учётные_коммиты_диспетчера_не_второй_заход(p, subject):
    """Диспетчер заводит пункт из находки вместе с её тестом, при взятии кладёт ресёрч —
    это учёт, а не часть работы пункта."""
    p.commit({"tests/test_x.py": "1\n", "docs/research/x.md": "1\n"}, subject)
    p.branch("B-1", ({"reports/pdf.py": "1\n"}, ready("B-1")))
    r = p.mast("merge", "B-1", "--no-push")
    assert r.returncode == 0, r.stdout + r.stderr


# --- вливание одной командой ---

def test_вливание_одной_командой(p, tmp_path):
    p.branch("B-1", ({"reports/pdf.py": "1\n"}, "[B-1] рендер"),
             ({"reports/pdf.py": "2\n"},
              ready("B-1", debt="- **Шрифты вшиты.** Грозит ростом образа.\n  **Чиним,** когда образ > 1 ГБ.")))
    (tmp_path / "agents.json").write_text(json.dumps([
        {"id": "abcd1234", "kind": "background", "name": "B-1", "cwd": str(p.worktree("B-1"))},
        {"id": "ffff0000", "kind": "background", "name": "B-1", "cwd": "/elsewhere"}]))
    base, tip = p.head()[:7], p.git("rev-parse", "--short=7", "worktree-B-1")

    r = p.mast("merge", "B-1")
    assert r.returncode == 0, r.stdout + r.stderr

    today = datetime.date.today().strftime("%d.%m")
    assert p.read("docs/roadmap/DONE.md") == DONE.replace(
        "## B. Отчёты\n\n",
        f"## B. Отчёты\n\n- **B-1** Экспорт PDF — {today} · `{base}..{tip}`\n"
        "  Отчёт рендерится 8 с → 2 с.\n\n")
    assert "**B-1**" not in p.read("ROADMAP.md")
    assert "**B-2**" in p.read("ROADMAP.md") and "\n\n\n" not in p.read("ROADMAP.md")
    assert p.read("TECH_DEBT.md") == DEBT + (
        "\n- **Шрифты вшиты.** Грозит ростом образа.\n  **Чиним,** когда образ > 1 ГБ.\n")
    # одна правка трёх файлов — один коммит поверх вершины ветки
    assert p.git("log", "-1", "--format=%s") == "[B-1] закрыт"
    assert p.git("rev-parse", "--short=7", "HEAD~1") == tip
    assert sorted(p.git("show", "--name-only", "--format=", "HEAD").split()) == [
        "ROADMAP.md", "TECH_DEBT.md", "docs/roadmap/DONE.md"]
    assert p.git("status", "--porcelain") == ""
    # уборка: сессия пункта по своему worktree, сам worktree и ветка
    assert (tmp_path / "claude.log").read_text().split("\n")[0] == "rm abcd1234"
    assert not p.worktree("B-1").exists()
    assert p.git("branch", "--list", "worktree-B-1") == ""


def test_после_вливания_линт_без_жалоб(p):
    """Тезис и удаление строки — одна правка: промежуточного состояния, на которое
    ругался линт, больше нет, а `Зависит от: B-1` у B-3 указывает в архив."""
    p.branch("B-1", ({"reports/pdf.py": "1\n"}, ready("B-1")))
    assert p.mast("merge", "B-1").returncode == 0
    lint = subprocess.run([sys.executable, str(ROOT / "hooks/roadmap_lint.py"), "ROADMAP.md"],
                          cwd=p.root, capture_output=True, text=True)
    assert (lint.returncode, lint.stdout) == (0, "\n"), lint.stdout
    ready_list = subprocess.run([sys.executable, str(ROOT / "hooks/roadmap_lint.py"), "--ready", "ROADMAP.md"],
                                cwd=p.root, capture_output=True, text=True).stdout.split()
    assert ready_list == ["B-3"]


def test_ссылки_на_status_и_adr_из_ветки(p):
    p.branch("B-1", ({"docs/roadmap/done/B-1/STATUS.md": "# B-1\n",
                      "docs/adr/B-1-reportlab.md": "# ADR\n"}, ready("B-1")))
    assert p.mast("merge", "B-1").returncode == 0
    line = next(l for l in p.read("docs/roadmap/DONE.md").splitlines() if l.startswith("- **B-1**"))
    assert line.endswith("· [STATUS](done/B-1/STATUS.md) · [ADR](../adr/B-1-reportlab.md)")


def test_старая_форма_последнего_коммита_принимается(p):
    """Так писали A-11 и A-18: пометка в скобках у критерия, перенос по 80 символов,
    «Черновик тезиса для DONE.md:» с шапкой строки и отступом."""
    msg = ("[B-1] готов: замеры\n\nГотово когда (дословно из origin/main): отчёт на 500\n"
           "строк < 3 с.\n\nЧерновик тезиса для DONE.md:\n"
           "- **B-1** Экспорт PDF — 23.09 · <диапазон>\n"
           "  Отчёт рендерится 8 с → 2 с,\n  память 210 МБ.\n\n"
           "Правил не нужно.\n")
    p.branch("B-1", ({"reports/pdf.py": "1\n"}, msg))
    r = p.mast("merge", "B-1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "\n  Отчёт рендерится 8 с → 2 с, память 210 МБ.\n" in p.read("docs/roadmap/DONE.md")
    assert p.read("TECH_DEBT.md") == DEBT


# --- очередь готовых веток ---

def test_вторая_готовая_ветка_переребейзена_и_влита(p, tmp_path):
    p.branch("B-1", ({"reports/pdf.py": "1\n"}, ready("B-1")))
    p.branch("B-2", ({"csv/x.py": "1\n"}, "[B-2] выгрузка"), ({"csv/x.py": "2\n"}, ready("B-2")))
    r = p.mast("merge", "B-1")
    assert r.returncode == 0, r.stdout + r.stderr
    subjects = p.git("log", "--format=%s", "-6").splitlines()
    assert subjects[:5] == ["[B-2] закрыт", "[B-2] готов", "[B-2] выгрузка", "[B-1] закрыт", "[B-1] готов"]
    assert "**B-2**" not in p.read("ROADMAP.md")
    assert p.read("csv/x.py") == "2\n"
    done = p.read("docs/roadmap/DONE.md")
    assert done.index("- **B-2**") < done.index("- **B-1**") < done.index("- **B-0**")
    # сессии B-2 ничего не пишем: в выводе нет текста для неё
    assert "SendMessage" not in r.stdout
    assert not p.worktree("B-2").exists() and p.git("branch", "--list", "worktree-B-2") == ""


def test_ветка_с_конфликтом_возвращена_сессии(p):
    p.branch("B-1", ({"reports/a.txt": "из B-1\n"}, ready("B-1")))
    p.branch("B-2", ({"reports/a.txt": "из B-2\n", "csv/x.py": "1\n"}, ready("B-2")))
    tip = p.git("rev-parse", "worktree-B-2")
    r = p.mast("merge", "B-1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "B-2" in r.stdout and "reports/a.txt" in r.stdout and "SendMessage" in r.stdout
    assert "**B-2**" in p.read("ROADMAP.md")
    # ветка и worktree сессии не тронуты, временная копия убрана
    assert p.git("rev-parse", "worktree-B-2") == tip and p.worktree("B-2").exists()
    assert len(p.git("worktree", "list").splitlines()) == 2


def test_красные_тесты_возвращают_ветку(p):
    p.branch("B-1", ({"reports/pdf.py": "1\n"}, ready("B-1")))
    p.branch("B-2", ({"csv/x.py": "1\n", "FAIL": "1\n"}, ready("B-2")))
    r = p.mast("merge", "B-1")
    assert r.returncode == 0
    assert "test ! -e FAIL" in r.stdout and "SendMessage" in r.stdout
    assert "**B-2**" in p.read("ROADMAP.md") and not (p.root / "FAIL").exists()


def test_без_команды_тестов_ветка_возвращена(tmp_path, env):
    p = Project(tmp_path, env, dispatch=None)
    p.branch("B-1", ({"reports/pdf.py": "1\n"}, ready("B-1")))
    p.branch("B-2", ({"csv/x.py": "1\n"}, ready("B-2")))
    r = p.mast("merge", "B-1")
    assert r.returncode == 0
    assert ".claude/rules/dispatch.md" in r.stdout and "**B-2**" in p.read("ROADMAP.md")


def test_неготовая_ветка_не_трогается(p):
    p.branch("B-1", ({"reports/pdf.py": "1\n"}, ready("B-1")))
    p.branch("B-2", ({"csv/x.py": "1\n"}, "[B-2] в процессе"))
    tip = p.git("rev-parse", "worktree-B-2")
    r = p.mast("merge", "B-1")
    assert r.returncode == 0 and "B-2" not in r.stdout
    assert p.git("rev-parse", "worktree-B-2") == tip


# --- push и язык ---

def test_push_и_удаление_удалённой_ветки(p, tmp_path):
    p.git("init", "-q", "--bare", str(tmp_path / "origin.git"))
    p.git("remote", "add", "origin", str(tmp_path / "origin.git"))
    p.git("push", "-qu", "origin", "main")
    p.branch("B-1", ({"reports/pdf.py": "1\n"}, ready("B-1")))
    p.git("push", "-q", "origin", "worktree-B-1")
    assert p.mast("merge", "B-1").returncode == 0
    assert p.git("rev-parse", "origin/main") == p.head()
    assert p.git("ls-remote", "--heads", "origin") .count("refs/heads/") == 1


def test_no_push_ничего_не_отправляет(p, tmp_path):
    p.git("init", "-q", "--bare", str(tmp_path / "origin.git"))
    p.git("remote", "add", "origin", str(tmp_path / "origin.git"))
    p.git("push", "-qu", "origin", "main")
    before = p.git("ls-remote", "origin")
    p.branch("B-1", ({"reports/pdf.py": "1\n"}, ready("B-1")))
    assert p.mast("merge", "B-1", "--no-push").returncode == 0
    assert p.git("ls-remote", "origin") == before


def test_шаблон_dispatch_объявляет_команду_тестов():
    """Строку `Тесты:` шаблона читает `mast merge` — разъедутся, и очередь молча встанет."""
    for lang in ("ru", "en"):
        text = (ROOT / f"plugins/{lang}/locales/{lang}/templates/dispatch.rule.template.md").read_text(encoding="utf-8")
        assert mast.TESTS.search(text), f"{lang}: в шаблоне нет строки с командой тестов"


def test_раздел_вливание_короткий():
    """Механику делает `mast merge`, раздел — только как его звать и что он проверяет.
    Было 3514 (ru) и 3916 (en); английский той же мысли длиннее примерно на десятую."""
    for lang, head, limit in (("ru", "## Вливание", 900), ("en", "## Merging", 1000)):
        text = (ROOT / f"plugins/{lang}/locales/{lang}/skills/managing-roadmap-items-dispatcher.md").read_text(encoding="utf-8")
        found = re.search(rf"^{head}\n.*?(?=^## )", text, re.S | re.M)
        assert found, f"{lang}: нет раздела «{head}» — переименовали, поправь сторожа"
        assert len(found.group(0)) <= limit, f"{lang}: {len(found.group(0))} символов"
        assert "mast merge" in found.group(0)


def test_английский_плагин(p):
    p.branch("B-1", ({"reports/pdf.py": "1\n"}, ready("B-1")))
    p.commit({"other.txt": "x\n"}, "moved on")
    r = p.mast("merge", "B-1", lang="en")
    assert r.returncode == 1 and "not a fast-forward" in r.stdout + r.stderr
