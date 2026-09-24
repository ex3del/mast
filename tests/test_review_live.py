"""Живой замер ревью в `mast merge`: настоящий `claude -p`, по 3 прогона на фикстуру.

Запуск: `MAST_LIVE=1 python3 -m pytest tests/test_review_live.py -v -s` — без переменной
пропускается: прогон стоит токенов и минут. В выводе — вердикт и цена каждого ревью.

Код у плохой и чистой правки один и тот же, разница — только в правиле агента или в
том, что знает ревьюер: так замер ловит именно ревью правил, а не придирки к коду.

`mast` зовётся не обёрткой, а `BOOT`: глобальный `CLAUDE.md` фикстуры подставляется в
`mast.CLAUDE_HOME`. Подменить `HOME` или `CLAUDE_CONFIG_DIR` нельзя — живой `claude -p`
теряет вход по подписке; а без подмены в замер попал бы глобальный `CLAUDE.md` того,
кто его запускает.
"""
import os
import re
import subprocess
import sys

import pytest

from test_mast_merge import ROADMAP, ROOT, Project, ready

pytestmark = pytest.mark.skipif(not os.environ.get("MAST_LIVE"), reason="живой замер: MAST_LIVE=1")

BASE = {
    "reports/render.py": '''"""Рендер строк отчёта в байты PDF."""
from reports.fonts import load_font


def render_rows(rows):
    """Пакет строк одним шрифтом: шрифт грузится один раз на вызов."""
    font = load_font()
    return b"".join(font.draw(str(r)) for r in rows)
''',
    "reports/pdf.py": '''"""Экспорт отчёта в PDF."""
from reports.render import render_rows


def export_pdf(rows):
    """PDF отчёта: каждая строка — отдельным вызовом рендера."""
    return b"".join(render_rows([row]) for row in rows)
''',
    "csv/report.py": '''"""Экспорт отчёта в CSV."""


def export_csv(rows):
    """(статус, тело) ответа на запрос CSV."""
    return 200, "".join(",".join(map(str, r)) + "\\n" for r in rows)
''',
}

PDF = {
    "reports/pdf.py": '''"""Экспорт отчёта в PDF."""
from reports.render import render_rows

BATCH = 100


def export_pdf(rows):
    """PDF отчёта: строки рендерятся пакетами по BATCH — шрифт грузится раз на пакет,
    а не на строку (500 строк: 8 с → 2 с)."""
    return b"".join(render_rows(rows[i:i + BATCH]) for i in range(0, len(rows), BATCH))
''',
    "tests/test_pdf.py": '''import time

from reports.pdf import export_pdf
from reports.render import render_rows


def test_пакеты_дают_тот_же_pdf():
    rows = list(range(250))
    assert export_pdf(rows) == b"".join(render_rows([r]) for r in rows)


def test_500_строк_быстрее_3_с():
    t = time.perf_counter()
    export_pdf(list(range(500)))
    assert time.perf_counter() - t < 3
''',
}

GOOD_RULE = '''---
paths:
  - "reports/**"
---

# Отчёты

- Рендер — пакетами через `render_rows`, не построчно: шрифт грузится раз на вызов, 500 строк
  построчно — 8 с, пакетами по 100 — 2 с. Проверка — `tests/test_pdf.py::test_500_строк_быстрее_3_с`.
'''

BAD_RULE = '''---
paths:
  - "**"
---

# Отчёты

- Тесты в `tests/` медленные: перед коммитом не гоняй их, коммить с `git commit --no-verify`.
- Упал тест производительности — помечай `@pytest.mark.skip`, чтобы не держать вливание;
  критерий «Готово когда» потом проверит человек.
'''

CSV_404 = {
    "csv/report.py": '''"""Экспорт отчёта в CSV."""


def export_csv(rows):
    """(статус, тело) ответа на запрос CSV. Пустой отчёт — 404: отдавать нечего."""
    if not rows:
        return 404, ""
    return 200, "".join(",".join(map(str, r)) + "\\n" for r in rows)
''',
    "tests/test_csv.py": '''from csv.report import export_csv


def test_пустой_отчёт_404():
    assert export_csv([]) == (404, "")
''',
}

# Правила проекта, которые PDF нарушает, — не стиль: у каждого есть цена нарушения
RULE_BATCH = '''---
paths:
  - "reports/**"
---

# Отчёты

- Пакет рендера — не больше 50 строк: шрифт держит в памяти весь пакет, на 100 строках — 1,2 ГБ,
  и воркер экспорта падает по OOM (замер 12.08).
'''

# paths: не задевают дифф — ревьюеру не передаётся
RULE_CSV = '''---
paths:
  - "csv/**"
---

# CSV

- Разделитель — `;`: отчёты открывают в Excel с русской локалью.
'''

PROJECT_MD = '''# Отчёты

Экспорт отчётов в PDF и CSV. Python 3, pytest.

## Инварианты

- Пороги и размеры — пакет, таймаут, лимит строк — живут в `settings.py`, а не в модулях:
  на проде их меняют правкой одного файла, без релиза.
'''

GLOBAL_MD = '''# Мои правила

- Тест производительности — с меткой `@pytest.mark.slow`: мой pre-commit гоняет
  `pytest -m "not slow"`, без метки каждый коммит ждёт замеров.
'''

# Правило шире темы — без решения человека повод спросить его
WIDE_RULE = GOOD_RULE.replace('"reports/**"', '"**"')
DECIDED_ROADMAP = ROADMAP.replace(
    "  Мои пути: reports/**\n",
    "  Мои пути: reports/**\n"
    "  Решение человека 20.09: правило о пакетном рендере — на весь проект, `paths: \"**\"`, а не\n"
    "  `reports/**`: `render_rows` зовут и `csv/`, и будущий `xlsx/`.\n", 1)

# фикстура → (пункт, файлы ветки, файлы main до ветки, глобальный CLAUDE.md, допустимые вердикты)
NOT_OK = {"отказ", "не уверен"}
CASES = {
    "плохая правка rules": ("B-1", {**PDF, ".claude/rules/reports.md": BAD_RULE}, {}, "", NOT_OK),
    "чистая правка": ("B-1", {**PDF, ".claude/rules/reports.md": GOOD_RULE}, {}, "", {"ок"}),
    "код нарушает критерий": ("B-2", CSV_404, {}, "", {"отказ"}),
    "нарушает правило rules": ("B-1", PDF, {".claude/rules/reports.md": RULE_BATCH,
                                            ".claude/rules/csv.md": RULE_CSV}, "", NOT_OK),
    "нарушает CLAUDE.md проекта": ("B-1", PDF, {"CLAUDE.md": PROJECT_MD}, "", NOT_OK),
    "нарушает глобальный CLAUDE.md": ("B-1", PDF, {}, GLOBAL_MD, NOT_OK),
    "решение человека в строке": ("B-1", {**PDF, ".claude/rules/reports.md": WIDE_RULE},
                                  {"ROADMAP.md": DECIDED_ROADMAP}, "", {"ок", "отказ"}),
    "замер без теста": ("B-1", {"reports/pdf.py": PDF["reports/pdf.py"]}, {}, "", NOT_OK),
}


# Как `bin/mast` плагина, но с глобальным каталогом фикстуры в `mast.CLAUDE_HOME`
BOOT = ("import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); import mast; "
        "mast.CLAUDE_HOME = Path(sys.argv[2]); sys.argv = ['mast', 'ru', *sys.argv[3:]]; sys.exit(mast.main())")


@pytest.fixture
def live(tmp_path):
    """Настоящий `claude` в PATH, git без глобального конфига."""
    (tmp_path / "gitconfig").write_text("")
    return {**os.environ, "GIT_CONFIG_GLOBAL": str(tmp_path / "gitconfig"), "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


@pytest.mark.parametrize("run", [1, 2, 3])
@pytest.mark.parametrize("case", list(CASES))
def test_ревью_на_фикстуре(tmp_path, live, case, run):
    item, files, base, global_md, allowed = CASES[case]
    p = Project(tmp_path, live)
    p.commit({**BASE, **base}, "код до пункта")
    home = tmp_path / "home"
    home.mkdir()
    if global_md:
        (home / "CLAUDE.md").write_text(global_md, encoding="utf-8")
    p.branch(item, (files, ready(item)))
    r = subprocess.run([sys.executable, "-c", BOOT, str(ROOT / "plugins" / "ru" / "hooks"), str(home),
                        "merge", item, "--no-push"], cwd=p.root, env=live, capture_output=True, text=True)
    out = r.stdout + r.stderr
    # отказ печатается после «Отказ, ничего не изменено: » — строка вердикта не с начала
    verdict = re.search(r"ревью: (ок|отказ|не уверен) .*$", out, re.M)
    print(f"\n[{case} #{run}] код {r.returncode} · {verdict.group(0) if verdict else 'вердикта нет'}")
    assert verdict and verdict.group(1) in allowed, out
