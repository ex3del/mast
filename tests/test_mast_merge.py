"""`mast merge X-N` на git-фикстуре: вливание ровно названной ветки одной командой.

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


REVIEW = {"type": "result", "is_error": False, "usage": {
    "input_tokens": 10, "cache_creation_input_tokens": 1000, "cache_read_input_tokens": 0, "output_tokens": 200}}


def verdict(tmp_path, v="ok", reasons=("дифф выполняет критерий",), question=""):
    """Ответ заглушки на `claude -p` — так же, как живой `--output-format json --json-schema`."""
    (tmp_path / "review.json").write_text(json.dumps(
        {**REVIEW, "structured_output": {"verdict": v, "reasons": list(reasons), "question": question}},
        ensure_ascii=False), encoding="utf-8")


def ready(item, thesis="Отчёт рендерится 8 с → 2 с.", debt=None):
    """Последний коммит готовой ветки — в той форме, что велит скилл сессии пункта."""
    msg = f"[{item}] готов\n\nГотово когда: {CRIT[item]}\nЗамер: было 8 с → стало 2 с.\n\nТезис: {thesis}\n"
    return msg + (f"\nTECH_DEBT.md:\n{debt}\n" if debt else "")


@pytest.fixture
def env(tmp_path):
    """Окружение без глобального конфига git и с заглушкой `claude` в PATH."""
    fake = tmp_path / "fakebin"
    fake.mkdir()
    # `--bg` печатает id так же, как живой: с цветами, хотя stdout не терминал
    (fake / "claude").write_text(
        '#!/bin/sh\n'
        'if [ "$1" = agents ]; then cat "$FAKE_AGENTS" 2>/dev/null || echo "[]"; exit 0; fi\n'
        # ревьюер: аргументы по строке и вход — в файлы рядом с журналом, ответ — из файла
        'if [ "$1" = -p ]; then\n'
        '  printf "%s\\n" "$@" > "$FAKE_LOG.args"; cat > "$FAKE_LOG.input"; cat "$FAKE_REVIEW"; exit 0\n'
        'fi\n'
        'echo "$@" >> "$FAKE_LOG"\n'
        'if [ "$1" = --bg ]; then\n'
        '  if [ -n "$FAKE_BG_FAIL" ]; then echo "$FAKE_BG_FAIL" >&2; exit 1; fi\n'
        '  printf "backgrounded · \\033[36mfakeid01\\033[39m · x\\n'
        '\\033[2m  claude attach fakeid01  open in this terminal\\033[22m\\n"\n'
        'fi\n', encoding="utf-8")
    (fake / "claude").chmod(0o755)
    (tmp_path / "gitconfig").write_text("")
    verdict(tmp_path)
    # глобальный CLAUDE.md ревьюера — из каталога теста, а не того, кто гоняет тесты
    return {**os.environ, "FAKE_REVIEW": str(tmp_path / "review.json"),
            "CLAUDE_CONFIG_DIR": str(tmp_path / "claude-home"),
            "PATH": f"{fake}{os.pathsep}{os.environ['PATH']}",
            "GIT_CONFIG_GLOBAL": str(tmp_path / "gitconfig"), "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
            "FAKE_AGENTS": str(tmp_path / "agents.json"), "FAKE_LOG": str(tmp_path / "claude.log")}


class Project:
    def __init__(self, tmp_path, env):
        self.root, self.env, self.tmp = tmp_path / "p", env, tmp_path
        self.root.mkdir()
        self.write(self.root, {"ROADMAP.md": ROADMAP, "docs/roadmap/DONE.md": DONE, "TECH_DEBT.md": DEBT,
                               ".gitignore": ".claude/worktrees/\n", "reports/a.txt": "a\n"})
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
    return r


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


def test_часть_работы_уже_в_main_вливается_и_названа_в_архиве(p):
    """Второй заход или правка в основной копии: вливает сам, а ранние коммиты называет
    в тезисе и коммите закрытия — диапазон ветки в архиве не всё."""
    p.commit({"reports/early.py": "1\n"}, "[B-1] начало в основной копии")
    early = p.git("rev-parse", "--short=7", "HEAD")
    p.branch("B-1", ({"reports/pdf.py": "1\n"}, ready("B-1")))
    r = p.mast("merge", "B-1", "--no-push")
    assert r.returncode == 0, r.stdout + r.stderr
    tail = f"{early} [B-1] начало в основной копии"
    assert f"Отчёт рендерится 8 с → 2 с. Часть работы раньше в main: {tail}" in p.read("docs/roadmap/DONE.md")
    assert tail in p.git("log", "-1", "--format=%b")


def test_отказ_нет_ветки(p):
    refused(p, "B-1", "worktree-B-1")


def test_отказ_пункт_не_в_работе(p):
    refused(p, "B-3", "B-3")


@pytest.mark.parametrize("subject", ["[B-1] находка: токен не отзывается",
                                     "[B-1] заведён: токен не отзывается",
                                     "[B-1] [B-2] заведены: токен, выгрузка",
                                     "[B-1] взят в работу · opus"])
def test_учётные_коммиты_диспетчера_не_второй_заход(p, subject):
    """Диспетчер заводит пункт из находки вместе с её тестом, при взятии кладёт ресёрч —
    это учёт, а не часть работы пункта."""
    p.commit({"tests/test_x.py": "1\n", "docs/research/x.md": "1\n"}, subject)
    p.branch("B-1", ({"reports/pdf.py": "1\n"}, ready("B-1")))
    r = p.mast("merge", "B-1", "--no-push")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "раньше в main" not in p.read("docs/roadmap/DONE.md") + p.git("log", "-1", "--format=%b")


# --- вливание одной командой ---

def test_вливание_одной_командой(p, tmp_path):
    p.branch("B-1", ({"reports/pdf.py": "1\n"}, "[B-1] рендер"),
             ({"reports/pdf.py": "2\n"},
              ready("B-1", debt="- **Шрифты вшиты.** Грозит ростом образа.\n  **Чиним,** когда образ > 1 ГБ.\n"
                                "- **Кэш без TTL.** Грозит старыми данными.\n  **Чиним,** когда пожалуются.")))
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
    # записи в файле разделены пустой строкой — и перед первой новой, и между ними
    assert p.read("TECH_DEBT.md") == DEBT + (
        "\n- **Шрифты вшиты.** Грозит ростом образа.\n  **Чиним,** когда образ > 1 ГБ.\n"
        "\n- **Кэш без TTL.** Грозит старыми данными.\n  **Чиним,** когда пожалуются.\n")
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


def test_claude_rm_удалил_ветку_сам(p, tmp_path):
    """Живой `claude rm` убирает сессию вместе с её worktree и веткой. После коммита
    закрытия «Отказ, ничего не изменено» — ложь: диспетчер начнёт вливать заново."""
    (tmp_path / "fakebin" / "claude").write_text(
        '#!/bin/sh\n'
        'if [ "$1" = agents ]; then cat "$FAKE_AGENTS"; exit 0; fi\n'
        'if [ "$1" = -p ]; then cat > /dev/null; cat "$FAKE_REVIEW"; exit 0; fi\n'
        'git worktree remove --force .claude/worktrees/B-1 && git branch -D worktree-B-1\n')
    p.branch("B-1", ({"reports/pdf.py": "1\n"}, ready("B-1")))
    (tmp_path / "agents.json").write_text(json.dumps([{"id": "abcd1234", "cwd": str(p.worktree("B-1"))}]))
    tip = p.git("rev-parse", "worktree-B-1")

    r = p.mast("merge", "B-1", "--no-push")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "ничего не изменено" not in r.stdout + r.stderr
    assert p.git("log", "-1", "--format=%s") == "[B-1] закрыт" and p.git("rev-parse", "HEAD~1") == tip
    assert not p.worktree("B-1").exists() and p.git("branch", "--list", "worktree-B-1") == ""


def test_коммит_закрытия_не_прошёл_не_отказ(p):
    """Мердж уже сделан — «ничего не изменено» здесь ложь; вывод говорит, что доделать."""
    p.branch("B-1", ({"reports/pdf.py": "1\n"}, ready("B-1")))
    hook = p.root / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    r = p.mast("merge", "B-1", "--no-push")
    assert r.returncode == 1
    assert "ничего не изменено" not in r.stderr and "git commit" in r.stderr, r.stderr


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


# --- только названная ветка ---

@pytest.mark.parametrize("last", [ready("B-2"), "[B-2] в процессе"])
def test_вливается_только_названная_ветка(p, last):
    """Решение человека: `mast merge B-1` вливает ровно B-1. Ветку B-2, которую сдвинул
    мердж, — готовую или нет — скрипт не трогает, а печатает текст для её сессии."""
    p.branch("B-1", ({"reports/pdf.py": "1\n"}, ready("B-1")))
    p.branch("B-2", ({"csv/x.py": "1\n"}, last))
    tip = p.git("rev-parse", "worktree-B-2")
    r = p.mast("merge", "B-1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert p.git("log", "--format=%s").splitlines() == ["[B-1] закрыт", "[B-1] готов", "init"]
    assert "**B-2**" in p.read("ROADMAP.md") and not (p.root / "csv").exists()
    assert p.git("rev-parse", "worktree-B-2") == tip and p.worktree("B-2").exists()
    assert "B-2: ветку сдвинул мердж B-1" in r.stdout and "SendMessage" in r.stdout


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


def test_скилл_учит_форме_которую_разбирает_mast_merge():
    """Форму последнего коммита описывает скилл сессии пункта, а читает `mast merge`.
    Поменяют заголовок в тексте, не тронув разбор, — каждая ветка получит отказ."""
    for lang in ("ru", "en"):
        text = (ROOT / f"plugins/{lang}/locales/{lang}/skills/managing-roadmap-items-item.md").read_text(encoding="utf-8")
        heads = re.findall(r"^  - `([^`]+)`", text, re.M)
        assert len(heads) == 3, f"{lang}: блоки последнего коммита не найдены: {heads}"
        crit, thesis, debt = heads
        assert mast.CRIT_LINE.match(crit + "x"), f"{lang}: {crit!r}"
        assert mast.THESIS.match(thesis + "x"), f"{lang}: {thesis!r}"
        assert mast.DEBT_HEAD.match(debt), f"{lang}: {debt!r}"


def test_скилл_велит_класть_скрипт_замера_в_ветку():
    """Число вне тестов ревьюер принимает, только видя в диффе скрипт замера (A-22), а дифф
    он получает без исключений `REVIEWED`. Скилл сессии пункта называет их, иначе скрипт
    ляжет рядом со `STATUS.md` — и вопрос снова уйдёт человеку."""
    excluded = [x.split(")", 1)[1] for x in mast.REVIEWED if x.startswith(":(exclude)")]
    for lang, rule in (("ru", "**Число, которого нет в тестах, — скриптом в ветке.**"),
                       ("en", "**A number no test checks — a script in the branch.**")):
        text = (ROOT / f"plugins/{lang}/locales/{lang}/skills/managing-roadmap-items-item.md").read_text(encoding="utf-8")
        para = next((x for x in text.split("\n\n") if x.startswith(rule)), "")
        assert para, f"{lang}: нет правила «{rule}»"
        assert all(f"`{path}/`" in para for path in excluded), f"{lang}: {excluded}"


def test_раздел_вливание_короткий():
    """Механику делает `mast merge`, раздел — только как его звать и что он проверяет.
    Было 3514 (ru) и 3916 (en); английский той же мысли длиннее примерно на десятую.
    A-15 добавил ревью и ответ человека на «не уверен»: 803 → 1046 (ru), 903 → 1213 (en)."""
    for lang, head, limit in (("ru", "## Вливание", 1100), ("en", "## Merging", 1250)):
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


# --- ревью с чистым контекстом ---

def test_ревью_ок_в_выводе_и_в_коммите_закрытия(p):
    p.branch("B-1", ({"reports/pdf.py": "1\n"}, ready("B-1")))
    r = p.mast("merge", "B-1", "--no-push")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "ревью: ок · 1 210 токенов" in r.stdout
    assert p.git("log", "-1", "--format=%b") == "ревью: ок · 1 210 токенов"


@pytest.mark.parametrize("lang, head", [("ru", "# Ревью ветки перед вливанием"), ("en", "# Branch review before merging")])
def test_ревьюер_видит_строку_и_готов_но_не_историю(p, tmp_path, lang, head):
    """Строка пункта целиком — задание и решения человека, сообщение «готов» — заявления
    автора. История пункта — промежуточные коммиты, STATUS.md — не доходит; плагинов и
    инструментов нет."""
    p.branch("B-1", ({"reports/pdf.py": "print('рендер пакетами')\n"}, "[B-1] черновик: спорили с человеком"),
             ({"docs/roadmap/done/B-1/STATUS.md": "# B-1\nЖурнал: откатили weasyprint\n"}, ready("B-1")))
    assert p.mast("merge", "B-1", "--no-push", lang=lang).returncode == 0
    task = (tmp_path / "claude.log.input").read_text(encoding="utf-8")
    assert "+print('рендер пакетами')" in task
    for seen in ("- **B-1** Экспорт PDF", "Мои пути: reports/**", CRIT["B-1"],
                 "Замер: было 8 с → стало 2 с.", "Тезис: Отчёт рендерится"):
        assert seen in task, seen
    for secret in ("спорили с человеком", "weasyprint"):
        assert secret not in task, secret
    args = (tmp_path / "claude.log.args").read_text(encoding="utf-8").split("\n")
    for flag in ("--safe-mode", "--no-session-persistence", "--json-schema"):
        assert flag in args, flag
    assert args[args.index("--tools") + 1] == ""
    assert args[args.index("--system-prompt") + 1] == head


RULE = '---\npaths:\n  - "{}"\n---\n\n{}\n'


def test_ревьюер_видит_правила_проекта(p, tmp_path):
    """Память сессии, тронувшей файлы диффа, — из дерева ветки: проектный CLAUDE.md, правила
    без `paths:` и с задевающими дифф, глобальный CLAUDE.md. Лишних 0: ни правила с чужими
    `paths:` или с путями вне того, что видит ревьюер, ни скиллов, ни незакоммиченного."""
    p.commit({"CLAUDE.md": "ПРОЕКТ\n", ".claude/CLAUDE.md": "ВТОРОЙ\n", ".claude/rules/always.md": "ВСЕГДА\n",
              ".claude/rules/deep/reports.md": RULE.format("reports/**", "ОТЧЁТЫ"),
              ".claude/rules/code.md": RULE.format("**/*.{sql,py}", "СКОБКИ"),
              ".claude/rules/csv.md": RULE.format("csv/**", "ЧУЖОЕ"),
              ".claude/rules/roadmap.md": RULE.format("docs/roadmap/**", "ИСТОРИЯ"),
              ".claude/skills/x/SKILL.md": "СКИЛЛ\n"}, "правила")
    (tmp_path / "claude-home").mkdir()
    (tmp_path / "claude-home" / "CLAUDE.md").write_text("ГЛОБАЛЬНОЕ\n", encoding="utf-8")
    p.branch("B-1", ({"reports/pdf.py": "1\n", "docs/roadmap/B-1/STATUS.md": "журнал\n"}, ready("B-1")))
    (p.root / ".claude/rules/always.md").write_text("ГРЯЗЬ\n", encoding="utf-8")
    assert p.mast("merge", "B-1", "--no-push").returncode == 0
    task = (tmp_path / "claude.log.input").read_text(encoding="utf-8")
    assert sorted(re.findall(r'<file path="([^"]+)">', task)) == sorted([
        "CLAUDE.md", ".claude/CLAUDE.md", ".claude/rules/always.md", ".claude/rules/deep/reports.md",
        ".claude/rules/code.md", "~/.claude/CLAUDE.md"])
    for text in ("ПРОЕКТ", "ВТОРОЙ", "ВСЕГДА", "ОТЧЁТЫ", "СКОБКИ", "ГЛОБАЛЬНОЕ"):
        assert text in task, text
    for text in ("ЧУЖОЕ", "ИСТОРИЯ", "СКИЛЛ", "ГРЯЗЬ"):
        assert text not in task, text


def test_глобальный_claude_md_без_config_dir_из_home(p, tmp_path):
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "CLAUDE.md").write_text("ДОМАШНЕЕ\n", encoding="utf-8")
    p.env = {**{k: v for k, v in p.env.items() if k != "CLAUDE_CONFIG_DIR"}, "HOME": str(home)}
    p.branch("B-1", ({"reports/pdf.py": "1\n"}, ready("B-1")))
    assert p.mast("merge", "B-1", "--no-push").returncode == 0
    task = (tmp_path / "claude.log.input").read_text(encoding="utf-8")
    assert '<file path="~/.claude/CLAUDE.md">\nДОМАШНЕЕ\n</file>' in task


def test_сгенерированное_ревьюеру_не_идёт(p, tmp_path):
    """Пометка GitHub `linguist-generated` — lock-файлы, сборка: проверять в них нечего,
    а токенов они съедают много. Пометка бывает и без значения, и `=true`."""
    p.commit({".gitattributes": "*.lock linguist-generated\ndist/* linguist-generated=true\n"}, "пометки")
    p.branch("B-1", ({"reports/pdf.py": "РУКАМИ\n", "deps.lock": "ЛОК\n", "dist/app.js": "СБОРКА\n"}, ready("B-1")))
    assert p.mast("merge", "B-1", "--no-push").returncode == 0
    task = (tmp_path / "claude.log.input").read_text(encoding="utf-8")
    assert "+РУКАМИ" in task
    for gen in ("ЛОК", "СБОРКА", "deps.lock", "dist/app.js"):
        assert gen not in task, gen


def test_ревью_отказ_ничего_не_меняет(p, tmp_path):
    verdict(tmp_path, "refuse", ["csv/report.py: пустой отчёт — 404, а критерий требует 200"])
    p.branch("B-1", ({"reports/pdf.py": "1\n"}, ready("B-1")))
    r = refused(p, "B-1", "ревью: отказ · 1 210 токенов — csv/report.py: пустой отчёт — 404")
    assert "SendMessage" in r.stderr


def test_ревью_не_уверен_ставит_слот_и_не_вливает(p, tmp_path):
    verdict(tmp_path, "unsure", ["правило на весь reports/"], "Правило про\nпакетный рендер — на весь reports/?")
    p.branch("B-1", ({"reports/pdf.py": "1\n"}, ready("B-1")))
    head = p.head()
    r = p.mast("merge", "B-1", "--no-push")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "ничего не изменено" not in r.stderr and "Правило про пакетный рендер" in r.stderr, r.stderr
    # один коммит слота поверх прежнего HEAD, ветка не влита
    assert p.git("log", "-1", "--format=%s") == "[B-1] ждёт человека: ревью не уверено"
    assert p.git("rev-parse", "HEAD~1") == head and p.git("show", "--name-only", "--format=", "HEAD") == "ROADMAP.md"
    row = next(l for l in p.read("ROADMAP.md").splitlines() if l.startswith("- **B-1**"))
    assert row.endswith(" · с 20.09 · ждёт человека: ревью не уверено — Правило про пакетный рендер — на весь reports/?")
    waiting = subprocess.run([sys.executable, str(ROOT / "hooks/roadmap_lint.py"), "--waiting", "ROADMAP.md"],
                             cwd=p.root, capture_output=True, text=True).stdout
    assert waiting.startswith("B-1: ревью не уверено"), waiting
    # второй «не уверен» после rebase — слот заменяется, а не копится
    p.git("rebase", "-q", "main", cwd=p.worktree("B-1"))
    assert p.mast("merge", "B-1", "--no-push").returncode == 1
    assert p.read("ROADMAP.md").count("ждёт человека") == 1


@pytest.mark.parametrize("answer", [
    "не JSON", "",
    json.dumps({**REVIEW, "is_error": True, "result": "API Error: 529"}),
    json.dumps({**REVIEW, "result": "текст без схемы"}),
    json.dumps({**REVIEW, "structured_output": {"verdict": "может быть", "reasons": [], "question": ""}})])
def test_без_вердикта_не_вливает(p, tmp_path, answer):
    (tmp_path / "review.json").write_text(answer, encoding="utf-8")
    p.branch("B-1", ({"reports/pdf.py": "1\n"}, ready("B-1")))
    refused(p, "B-1", "нет вердикта ревью")


def test_нет_claude_не_вливает(p):
    p.branch("B-1", ({"reports/pdf.py": "1\n"}, ready("B-1")))
    p.env = {**p.env, "PATH": "/usr/bin:/bin"}
    refused(p, "B-1", "нет вердикта ревью")


def answer(p, text, subject="[B-1] решил человек"):
    """Диспетчер записывает ответ человека: `решил человек` вместо `ждёт человека`."""
    roadmap = re.sub(r" · ждёт человека:.*", "", p.read("ROADMAP.md"))
    roadmap = roadmap.replace("сессия `B-1` · с 20.09", f"сессия `B-1` · с 20.09 · решил человек: {text}")
    p.commit({"ROADMAP.md": roadmap}, subject)


def unsure_then_answer(p, tmp_path):
    """«Не уверен» → слот коммитом → «вливай» → rebase сессии; дальше ревьюер отказал бы."""
    verdict(tmp_path, "unsure", ["правило на весь reports/"], "Правило на весь reports/ — так задумано?")
    p.branch("B-1", ({"reports/pdf.py": "1\n"}, ready("B-1")))
    assert p.mast("merge", "B-1", "--no-push").returncode == 1
    answer(p, "вливай, так задумано")
    p.git("rebase", "-q", "main", cwd=p.worktree("B-1"))
    verdict(tmp_path, "refuse", ["ревьюер позван снова"])
    (tmp_path / "claude.log.args").unlink()


def test_решил_человек_вливает_без_ревьюера(p, tmp_path):
    unsure_then_answer(p, tmp_path)
    r = p.mast("merge", "B-1", "--no-push")
    assert r.returncode == 0, r.stdout + r.stderr
    assert not (tmp_path / "claude.log.args").exists(), "ревьюера звать не должны"
    assert p.git("log", "-1", "--format=%b") == (
        "вопрос ревью: Правило на весь reports/ — так задумано?\nрешил человек: вливай, так задумано")
    assert "**B-1**" not in p.read("ROADMAP.md")


def test_дифф_изменился_после_вопроса_ревью_заново(p, tmp_path):
    """Человек одобрил один дифф, сессия дописала коммит — вольётся другой. Ответ устарел:
    ревью заново, и новое «не уверен» заменяет и ответ, и старый вопрос."""
    unsure_then_answer(p, tmp_path)
    p.commit({"reports/pdf.py": "2\n"}, ready("B-1"), cwd=p.worktree("B-1"))
    verdict(tmp_path, "unsure", ["новая правка"], "А эта правка?")
    assert p.mast("merge", "B-1", "--no-push").returncode == 1
    assert (tmp_path / "claude.log.args").exists(), "ревьюера обязаны позвать"
    row = next(l for l in p.read("ROADMAP.md").splitlines() if l.startswith("- **B-1**"))
    assert row.endswith("· с 20.09 · ждёт человека: ревью не уверено — А эта правка?"), row


def test_решил_человек_не_на_вопрос_ревью_ревью_заново(p, tmp_path):
    """`ждёт человека` бывает и не от ревью: «какую библиотеку взять?» — ответ на него
    не одобряет дифф."""
    verdict(tmp_path, "refuse", ["reports/pdf.py: рендер построчный"])
    answer(p, "берём reportlab", "[B-1] ждёт человека: какую библиотеку взять")
    p.branch("B-1", ({"reports/pdf.py": "1\n"}, ready("B-1")))
    refused(p, "B-1", "ревью: отказ")
    assert (tmp_path / "claude.log.args").exists()


@pytest.mark.parametrize("flag", [["--force", "человек разрешил"], ["--skip-review"]])
def test_вливать_вопреки_ревью_флагом_нельзя(p, flag):
    """Решение человека 24.09: забытый флаг держится на памяти диспетчера, поэтому ответ
    человека живёт слотом `решил человек` в строке пункта, а флага нет."""
    p.branch("B-1", ({"reports/pdf.py": "1\n"}, ready("B-1")))
    r = p.mast("merge", "B-1", *flag)
    assert r.returncode == 2 and "использование" in r.stderr, r.stdout + r.stderr


def test_ждёт_человека_без_ответа_не_вливает(p, tmp_path):
    roadmap = p.read("ROADMAP.md").replace("сессия `B-1` · с 20.09", "сессия `B-1` · с 20.09 · ждёт человека: а шрифты?")
    p.commit({"ROADMAP.md": roadmap}, "[B-1] ждёт человека: шрифты")
    p.branch("B-1", ({"reports/pdf.py": "1\n"}, ready("B-1")))
    refused(p, "B-1", "ответ не записан")
    assert not (tmp_path / "claude.log.args").exists(), "без ответа платить за ревью незачем"


def test_строгая_планка_для_правил_агента(p, tmp_path):
    """Правила агента — `.claude/`, любой CLAUDE.md, скиллы; файл без расширения — не каталог."""
    files = {".claude/rules/reports.md": "x\n", "sub/CLAUDE.md": "x\n", "plugins/ru/skills/y/SKILL.md": "x\n",
             "bin/mast": "x\n", "reports/pdf.py": "1\n"}
    p.branch("B-1", (files, ready("B-1")))
    assert p.mast("merge", "B-1", "--no-push").returncode == 0
    task = (tmp_path / "claude.log.input").read_text(encoding="utf-8")
    strict = re.search(r"<strict_files>\n(.*?)</strict_files>", task, re.S).group(1).split()
    assert sorted(strict) == [".claude/rules/reports.md", "plugins/ru/skills/y/SKILL.md", "sub/CLAUDE.md"]
