"""Живой замер подсказки перезапуска (A-24) на установленном плагине: настоящий диспетчер
`claude -p --name a24-dispatch` вливает пункт из своего Bash, потом получает `/clear`.

Обычный `pytest` файл пропускает: платно (сессии на `sonnet`, ревьюер `mast merge` — `opus`).

  MAST_LIVE=1 MAST_BIN=<bin/mast установленного плагина> python3 -m pytest tests/test_restart_live.py -v -s

Каталог проекта — `MAST_LIVE_DIR` (по умолчанию `/private/tmp/mast-check-a24`): в нём уже
поставлен `mast-ru` через `tools/serve_marketplace.py` (`--scope local`, CLAUDE.md), репозитория
ещё нет. Контекст пробной сессии — десятки тысяч токенов, поэтому порог задаёт строка
`Порог перезапуска` в `.claude/mast.md`: 10 тыс. — контекст выше порога, 900 тыс. — ниже.
"""
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MAST = os.environ.get("MAST_BIN") or str(ROOT / "plugins" / "ru" / "bin" / "mast")
DIR = Path(os.environ.get("MAST_LIVE_DIR", "/private/tmp/mast-check-a24"))
NAME = "a24-dispatch"
HINT = "MAST: вливание прошло"
ROLE = "эта сессия — диспетчер роадмапа"
BASH = "Bash(mast *)"


def item(i):
    return (f"- **{i}** Проба {i} — 🔨 в работе · `worktree-{i}` · сессия `{i}` · с 25.09\n"
            f"  Мои пути: probe/{i}/**\n"
            f"  Готово когда: файл probe/{i}/done.txt есть — 1 из 1.\n")


ROADMAP = f"# Роадмап\n\n## X. Проба\n\n{item('X-1')}\n{item('X-2')}"

pytestmark = pytest.mark.skipif(os.environ.get("MAST_LIVE") != "1", reason="живой замер — MAST_LIVE=1")


def sh(*args, cwd=DIR, stdin=None, check=True):
    r = subprocess.run(args, cwd=cwd, input=stdin, capture_output=True, text=True)
    assert r.returncode == 0 or not check, f"{args}: {r.stdout}{r.stderr}"
    return r.stdout


def git(*args, cwd=DIR):
    return sh("git", "-c", "user.name=t", "-c", "user.email=t@t", *args, cwd=cwd)


def claude(prompt, *args, cwd=DIR):
    """Ход сессии `claude -p`; промпт — через stdin, иначе `--allowedTools` примет его за правило."""
    out = json.loads(sh("claude", "-p", "--model", "sonnet", "--output-format", "json", *args,
                        cwd=cwd, stdin=prompt))
    print(f"[{out['session_id']}] {out.get('result', '')[:600]}")
    return out["session_id"]


def records(sid):
    path = next((Path.home() / ".claude" / "projects").glob(f"*/{sid}.jsonl"))
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def hints(sid):
    """Записи транскрипта, где хук положил подсказку в контекст модели."""
    return [r for r in records(sid) if r.get("type") == "attachment" and HINT in json.dumps(r, ensure_ascii=False)]


def ready(i):
    """Ветка пункта с работой и последним коммитом для `mast merge`, на свежем main."""
    wt = DIR / ".claude" / "worktrees" / i
    if not wt.exists():
        git("worktree", "add", "-q", "-b", f"worktree-{i}", str(wt))
    git("rebase", "-q", "main", cwd=wt)
    (wt / "probe" / i).mkdir(parents=True)
    (wt / "probe" / i / "done.txt").write_text("проба\n", encoding="utf-8")
    git("add", ".", cwd=wt)
    git("commit", "-qm", f"[{i}] готов\n\nГотово когда: файл probe/{i}/done.txt есть — 1 из 1.\n"
        f"Замер: файла нет → есть, ls probe/{i}/done.txt.\n\nТезис: Проба пишет probe/{i}/done.txt: 0 → 1 файл.\n\n"
        f"Справка:\n- сделано: файл probe/{i}/done.txt.\n- для пользователя: ничего, это проба.\n"
        f"- проверить глазами: probe/{i}/done.txt не пустой.\n", cwd=wt)
    return wt


def threshold(k):
    (DIR / ".claude").mkdir(exist_ok=True)
    (DIR / ".claude" / "mast.md").write_text(f"# Настройки MAST\n\nПорог перезапуска: {k} тыс. токенов\n", encoding="utf-8")


@pytest.fixture
def project():
    """Проект с двумя пунктами «в работе». Каталог после пробы остаётся — плагин снимается из
    него же по CLAUDE.md."""
    assert not (DIR / ".git").exists(), f"{DIR} уже репозиторий — проба берёт чистый каталог"
    (DIR / "docs" / "roadmap").mkdir(parents=True, exist_ok=True)
    (DIR / "ROADMAP.md").write_text(ROADMAP, encoding="utf-8")
    (DIR / "docs" / "roadmap" / "DONE.md").write_text("# Закрытые пункты\n", encoding="utf-8")
    (DIR / ".gitignore").write_text(".claude/\n")
    git("init", "-q", "-b", "main")
    git("add", ".")
    git("commit", "-qm", "init")
    return DIR


def test_подсказка_после_вливания_и_справка_после_clear(project):
    sid = claude("Выполни `mast status` и ответь одним словом: готов.", "--name", NAME, "--allowedTools", BASH)
    prompt = ("Выполни `mast merge {i} --no-push` с таймаутом 600000 мс. Если после команды в контексте "
              "появилась подсказка MAST, перескажи её дословно; нет — ответь: подсказки нет.")

    # Выше порога: контекст сессии — десятки тысяч токенов, порог — 10 тыс.
    threshold(10)
    ready("X-1")
    claude(prompt.format(i="X-1"), "--resume", sid, "--allowedTools", BASH)
    above = hints(sid)
    print(f"выше порога: подсказок {len(above)}")
    assert len(above) == 1 and "`/clear`" in json.dumps(above, ensure_ascii=False)

    # Сессия пункта: `mast merge` из worktree отказывает, PostToolUse не приходит
    wt = ready("X-2")
    item_sid = claude(prompt.format(i="X-2"), "--name", "X-2", "--allowedTools", BASH, cwd=wt)
    print(f"сессия пункта: подсказок {len(hints(item_sid))}")
    # Справка пункта на старте — плагин в сессии пункта загружен, и молчание — не от его отсутствия
    assert any("эта сессия ведёт пункт X-2" in json.dumps(r, ensure_ascii=False) for r in records(item_sid))
    assert not hints(item_sid)

    # Ниже порога: тот же диспетчер, порог 900 тыс.
    threshold(900)
    claude(prompt.format(i="X-2"), "--resume", sid, "--allowedTools", BASH)
    print(f"ниже порога: подсказок {len(hints(sid)) - len(above)}")
    assert len(hints(sid)) == len(above)

    # `/clear` — новая сессия; справка на её старте — роль и вывод `mast status`
    before = set((Path.home() / ".claude" / "projects").glob("*/*.jsonl"))
    sh("claude", "-p", "--resume", sid, stdin="/clear")
    status = sh(MAST, "status").strip()
    fresh = set((Path.home() / ".claude" / "projects").glob("*/*.jsonl")) - before
    briefs = [a["attachment"] for p in fresh for a in records(p.stem)
              if a.get("type") == "attachment" and a["attachment"].get("hookName") == "SessionStart:clear"
              and ROLE in json.dumps(a, ensure_ascii=False)]
    print(f"после /clear: справок с ролью {len(briefs)}\n{json.dumps(briefs, ensure_ascii=False)[:1500]}")
    assert len(briefs) == 1
    brief = json.dumps(briefs[0], ensure_ascii=False)
    assert all(json.dumps(line, ensure_ascii=False)[1:-1] in brief for line in status.splitlines()), status
