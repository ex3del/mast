"""`mast status` на git-фикстуре: сверка сессий, пунктов «в работе» и worktree.

Окружение и заглушка `claude` — из `test_mast_merge.py`: заглушка отдаёт список
сессий из файла `FAKE_AGENTS`, как `claude agents --json --all`.
"""
import json
import os
import re
import subprocess
import time
from pathlib import Path

import pytest

from test_mast_merge import BIN, ROOT, Project, env  # noqa: F401 — env нужен как фикстура

ROADMAP = """# Роадмап

## B. Отчёты

- **B-1** Экспорт PDF — 🔨 в работе · `worktree-B-1` · сессия `B-1` · с 20.09
  Мои пути: reports/**
  Готово когда: отчёт на 500 строк < 3 с.

- **B-2** Экспорт CSV — 🔨 в работе · `worktree-B-2` · сессия `B-2` · с 21.09
  Мои пути: csv/**
  Готово когда: пустой отчёт — 200 за < 50 мс.

- **B-3** Экспорт XLSX — запланирован · — · ждёт человека: брать openpyxl или xlsxwriter?
  Готово когда: 10 листов < 1 с.
"""
NOW = time.time()


def agent(name, cwd, sid=None, state="working", started=NOW, live=True):
    """Запись `claude agents --json`: у живой — `pid` и `status`, у остановленной их нет."""
    a = {"cwd": str(cwd), "kind": "background" if sid else "interactive", "name": name,
         "startedAt": int(started * 1000), "sessionId": f"{name}-uuid"}
    if sid:
        a.update(id=sid, state=state)
    if live:
        a.update(pid=1, status="busy")
    return a


class Status(Project):
    def __init__(self, tmp_path, env):
        super().__init__(tmp_path, env)
        self.commit({"ROADMAP.md": ROADMAP}, "[B-1] [B-2] взяты в работу")

    def agents(self, *items):
        Path(self.env["FAKE_AGENTS"]).write_text(json.dumps(items))

    def item(self, item, commit_age=0):
        """Worktree пункта с одним коммитом `[X-N]` возрастом commit_age секунд."""
        date = f"@{int(NOW - commit_age)} +0000"
        self.git("worktree", "add", "-q", str(self.worktree(item)), "-b", f"worktree-{item}")
        self.env = {**self.env, "GIT_COMMITTER_DATE": date, "GIT_AUTHOR_DATE": date}
        self.commit({f"{item}.txt": "1\n"}, f"[{item}] шаг", cwd=self.worktree(item))
        self.env = {k: v for k, v in self.env.items() if not k.endswith("_DATE")}

    def status(self, lang="ru", cwd=None):
        r = subprocess.run([str(BIN[lang]), "status"], cwd=cwd or self.root, env=self.env,
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        return r.stdout


@pytest.fixture
def p(tmp_path, env):  # noqa: F811
    return Status(tmp_path, env)


def mismatches(out):
    return [l for l in out.splitlines() if re.match(r"^(B-\d+ брошен|сирота|лишняя)", l)]


def test_три_расхождения_найдены_лишних_нет(p, tmp_path):
    """Брошен (сессия остановлена), сирота (worktree без пункта «в работе»), лишняя
    (живая сессия с именем пункта не «в работе»). Шум вокруг не должен дать ни одной
    лишней строки: диспетчер в корне, чужой проект с тем же именем сессии, worktree
    субагента `agent-…`, живая сессия B-1 в своём worktree."""
    p.item("B-1")
    p.item("B-2")
    p.git("worktree", "add", "-q", str(p.worktree("B-3")), "-b", "worktree-B-3")
    p.git("worktree", "add", "-q", str(p.worktree("agent-a1b2")), "-b", "agent-a1b2")
    other = tmp_path / "other"
    p.agents(
        agent("B-1", p.worktree("B-1"), "aaaa1111"),
        agent("B-2", p.worktree("B-2"), "bbbb2222", state="done", live=False),
        agent("B-4", p.root, "dddd4444"),
        agent("p-dispatch", p.root),
        agent("B-2", other, "eeee5555"),
    )
    out = p.status()
    found = mismatches(out)
    assert len(found) == 3, out
    assert "B-2 брошен" in found[0] and "claude respawn bbbb2222" in found[0], out
    assert any(l.startswith("сирота") and ".claude/worktrees/B-3" in l for l in found), out
    assert any(l.startswith("лишняя") and "B-4" in l and "dddd4444" in l for l in found), out
    assert "eeee5555" not in out and "agent-a1b2" not in out, out


def test_брошен_без_всякой_сессии(p):
    p.item("B-1")
    p.item("B-2")
    p.agents(agent("B-1", p.worktree("B-1"), "aaaa1111"))
    found = mismatches(p.status())
    assert len(found) == 1 and found[0].startswith("B-2 брошен") and "respawn" not in found[0]


def test_сессия_закончила_ход_но_жива_не_брошена(p):
    """`state: done` при живом процессе — ход кончен, сессия ждёт промпта (например,
    написала «готов» диспетчеру). Брошенной её делает только смерть процесса."""
    p.item("B-1")
    p.item("B-2")
    p.agents(agent("B-1", p.worktree("B-1"), "aaaa1111"),
             agent("B-2", p.worktree("B-2"), "bbbb2222", state="done"))
    assert mismatches(p.status()) == []


def test_attach_для_каждой_живой_сессии_пункта(p):
    p.item("B-1")
    p.item("B-2")
    p.agents(agent("B-1", p.worktree("B-1"), "aaaa1111"),
             agent("B-2", p.worktree("B-2"), "bbbb2222", state="blocked"))
    out = p.status()
    assert re.search(r"^B-1 .*`claude attach aaaa1111`", out, re.M), out
    assert re.search(r"^B-2 .*`claude attach bbbb2222`", out, re.M), out


def test_сессия_пункта_узнаётся_по_имени_из_строки(p):
    """Пункт в основной копии: worktree нет, сессия интерактивная, id у неё нет."""
    p.commit({"ROADMAP.md": ROADMAP.replace("`worktree-B-2` · сессия `B-2`", "основная копия · сессия `csv-7`")},
             "[B-2] в основной копии")
    p.item("B-1")
    p.agents(agent("B-1", p.worktree("B-1"), "aaaa1111"), agent("csv-7", p.root))
    out = p.status()
    assert mismatches(out) == [], out
    assert re.search(r"^B-2 .*`csv-7`", out, re.M) and "attach None" not in out, out


def test_сессия_без_коммита_дольше_порога_помечена(p):
    p.item("B-1", commit_age=45 * 60)
    p.item("B-2")
    p.agents(agent("B-1", p.worktree("B-1"), "aaaa1111", started=NOW - 3600),
             agent("B-2", p.worktree("B-2"), "bbbb2222"))
    out = p.status()
    quiet = [l for l in out.splitlines() if "без коммита" in l]
    assert len(quiet) == 1 and quiet[0].startswith("B-1"), out
    # возраст — от NOW при импорте модуля: долгий прогон набора добавляет минуты
    assert 45 <= int(re.search(r"(\d+) мин", quiet[0]).group(1)) < 50, out


def test_свежий_старт_со_старым_коммитом_не_помечен(p):
    """Сессию перезапустили: коммиту ветки два часа, процессу — минута. Тишина
    считается от более позднего из двух, иначе каждый перезапуск — ложная пометка."""
    p.item("B-1", commit_age=2 * 3600)
    p.item("B-2")
    p.agents(agent("B-1", p.worktree("B-1"), "aaaa1111", started=NOW - 60),
             agent("B-2", p.worktree("B-2"), "bbbb2222"))
    assert "без коммита" not in p.status()


def quiet_b1(p, files):
    """Вывод `mast status`, где B-1 молчит 45 мин, а в основной копии лежат `files`."""
    p.write(p.root, files)
    p.item("B-1", commit_age=45 * 60)
    p.item("B-2")
    p.agents(agent("B-1", p.worktree("B-1"), "aaaa1111", started=NOW - 3600),
             agent("B-2", p.worktree("B-2"), "bbbb2222"))
    return p.status()


def test_порог_из_настроек_проекта(p):
    assert "без коммита" not in quiet_b1(p, {".claude/mast.md": "# Настройки MAST\n\nПорог тишины: 60 мин\n"})


def test_порог_в_правиле_моделей_не_действует(p):
    """Файл `dispatch.md` разрешает `sonnet`: заведённый ради порога, он молча открыл бы понижение."""
    assert "без коммита" in quiet_b1(p, {".claude/rules/dispatch.md": "# Модели\n\nПорог тишины: 60 мин\n"})


def test_ждёт_человека_и_inbox(p):
    p.write(p.root, {"docs/roadmap/inbox/24.09-pdf.md": "находка\n"})
    p.item("B-1")
    p.item("B-2")
    p.agents(agent("B-1", p.worktree("B-1"), "aaaa1111"), agent("B-2", p.worktree("B-2"), "bbbb2222"))
    out = p.status()
    assert "B-3: брать openpyxl или xlsxwriter?" in out
    assert "В docs/roadmap/inbox/ файлов: 1 — разбери" in out


def test_без_claude_сессии_не_сверены_а_не_брошены(p):
    p.item("B-1")
    p.item("B-2")
    p.env = {**p.env, "PATH": os.pathsep.join(d for d in p.env["PATH"].split(os.pathsep)
                                              if not (Path(d) / "claude").exists())}
    out = p.status()
    assert mismatches(out) == [] and "не сверены" in out, out


def test_из_worktree_сверяет_основную_копию(p):
    p.item("B-1")
    p.item("B-2")
    p.agents(agent("B-1", p.worktree("B-1"), "aaaa1111"), agent("B-2", p.worktree("B-2"), "bbbb2222"))
    assert p.status(cwd=p.worktree("B-1")) == p.status()


def test_английский_плагин(p):
    p.item("B-1")
    p.agents(agent("B-1", p.worktree("B-1"), "aaaa1111"))
    out = p.status(lang="en")
    assert re.search(r"^B-2 abandoned", out, re.M) and "`claude attach aaaa1111`" in out, out


def test_раздел_брошенные_пункты_короткий():
    """Сверку делает `mast status`, раздел — только когда его звать и что делать
    с выводом. Было 1024 (ru) и 1119 (en)."""
    for lang, head, limit in (("ru", "## Брошенные пункты", 300), ("en", "## Abandoned items", 330)):
        text = (ROOT / f"plugins/{lang}/locales/{lang}/skills/managing-roadmap-items-dispatcher.md").read_text(encoding="utf-8")
        found = re.search(rf"^{head}\n.*?(?=^## )", text, re.S | re.M)
        assert found, f"{lang}: нет раздела «{head}» — переименовали, поправь сторожа"
        assert len(found.group(0)) <= limit, f"{lang}: {len(found.group(0))} символов"
        assert "mast status" in found.group(0)


def test_пороги_в_шаблоне_настроек_а_не_в_правиле_моделей():
    import mast
    import restart
    for lang in ("ru", "en"):
        templates = ROOT / f"plugins/{lang}/locales/{lang}/templates"
        text = (templates / "mast.template.md").read_text(encoding="utf-8")
        for rx, default in ((mast.SILENCE, mast.SILENCE_DEFAULT), (restart.RESTART, restart.RESTART_DEFAULT)):
            m = rx.search(text)
            assert m and int(m.group(1)) == default, (lang, rx.pattern)
        rule = (templates / "dispatch.rule.template.md").read_text(encoding="utf-8")
        assert not mast.SILENCE.search(rule) and not restart.RESTART.search(rule), lang


# --- закрытый пункт: горячий час ---

def closed(p, age, sid="0000b0b0"):
    """Закрытый B-0 (есть в DONE.md, нет в ROADMAP.md) с worktree и сессией в нём;
    последнее сообщение сессии — age минут назад. Возвращает (сессия, время сообщения)."""
    p.git("worktree", "add", "-q", str(p.worktree("B-0")), "-b", "worktree-B-0")
    t = Path(p.env["CLAUDE_CONFIG_DIR"]) / "projects" / "-p-wt" / "B-0-uuid.jsonl"
    t.parent.mkdir(parents=True, exist_ok=True)
    t.write_text("{}\n")
    when = NOW - age * 60
    os.utime(t, (when, when))
    return agent("B-0", p.worktree("B-0"), sid, state="done"), when


def in_work(p):
    p.item("B-1")
    p.item("B-2")
    return agent("B-1", p.worktree("B-1"), "aaaa1111"), agent("B-2", p.worktree("B-2"), "bbbb2222")


def test_закрыт_горячий_час(p):
    """Сессия влитого пункта живёт час — срок кэша: её worktree не сирота, она не лишняя,
    а сессия с именем закрытого пункта вне worktree — вопрос после часа — тоже не лишняя."""
    b0, when = closed(p, age=10)
    p.agents(*in_work(p), b0, agent("B-0", p.root))
    out = p.status()
    until = time.strftime("%H:%M", time.localtime(when + 3600))
    assert re.search(rf"^B-0 закрыт, сессия открыта до {until} — `claude attach 0000b0b0`", out, re.M), out
    assert mismatches(out) == [], out


def test_закрыт_час_прошёл(p):
    b0, _ = closed(p, age=61)
    p.agents(*in_work(p), b0)
    out = p.status()
    line = next((l for l in out.splitlines() if l.startswith("B-0 закрыт, час прошёл")), "")
    assert "`claude --resume B-0-uuid --fork-session`" in line and "`claude rm 0000b0b0`" in line, out
    assert mismatches(out) == [], out


def test_status_не_убирает(p, tmp_path):
    """Сторож: сверка ничего не меняет — ни `claude rm`, ни `git worktree remove`,
    даже когда час сессии закрытого пункта прошёл."""
    b0, _ = closed(p, age=120)
    p.agents(*in_work(p), b0)
    p.status()
    log = tmp_path / "claude.log"
    assert not [l for l in (log.read_text().splitlines() if log.exists() else []) if l.startswith("rm")]
    assert p.worktree("B-0").exists() and p.git("branch", "--list", "worktree-B-0")


def test_снятый_с_worktree_сирота(p):
    p.write(p.root, {"docs/roadmap/DONE.md": p.read("docs/roadmap/DONE.md")
                     + "\n## Снято\n\n- **B-9** Экспорт ODS — снят 20.09: не нужен.\n"})
    p.git("worktree", "add", "-q", str(p.worktree("B-9")), "-b", "worktree-B-9")
    p.agents(*in_work(p))
    found = mismatches(p.status())
    assert len(found) == 1 and found[0].startswith("сирота") and "B-9" in found[0], found


def test_брошен_после_обрыва(p):
    """После обрыва API `state` остаётся `blocked`, а процесса нет — ни `pid`, ни `status`:
    пункт брошен, а не «в работе»."""
    b1, _ = in_work(p)
    p.agents(b1, agent("B-2", p.worktree("B-2"), "bbbb2222", state="blocked", live=False))
    found = mismatches(p.status())
    assert len(found) == 1 and found[0].startswith("B-2 брошен"), found
