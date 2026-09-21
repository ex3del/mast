"""Тесты guard-скрипта формата ROADMAP.md. Запуск: python3 -m unittest discover tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "hooks/roadmap_lint.py"
sys.path.insert(0, str(SCRIPT.parent))
from roadmap_lint import lint, orphans, ready  # noqa: E402

# Верхний слой архива: по 2 строки на закрытый пункт
LEDGER = """# Сделано

## A. Авторизация

- **A-9** Ротация ключей — 12.08 · `1111111..2222222` · [STATUS](done/A-9/STATUS.md)
  Ключи меняются раз в сутки, ручных операций 3 → 0.
"""

OK = """# Roadmap

## A. Авторизация

- **A-1** Логин — `M` · готов · 01.09 · a1b2c3d..e4f5a6b
  Готово когда: логин < 200 мс → 150 мс.

- **A-2** Отзыв токенов — 🔨 в работе · `worktree-A-2` · сессия `A-2 [1a2b3c]` · с 10.09
  Готово когда: 0 живых токенов после смены пароля.
  Зависит от: A-1

## B. Отчёты

- **B-1** Экспорт PDF — запланирован · — · зависит от: A-2
  Готово когда: 500 строк < 3 с.

- **B-2** Экспорт CSV — запланирован · —
  Готово когда: пустой отчёт → 200.
"""


class LintTest(unittest.TestCase):
    def test_valid_roadmap(self):
        self.assertEqual(lint(OK), [])

    def test_duplicate_id(self):
        text = OK + "\n- **B-2** Дубль — запланирован · —\n  Готово когда: 1 шт.\n"
        self.assertIn("B-2: номер занят дважды", lint(text))

    def test_missing_status(self):
        text = OK.replace("Экспорт CSV — запланирован · —", "Экспорт CSV — —")
        self.assertIn("B-2: нет статуса", lint(text))

    def test_missing_done_criterion(self):
        text = OK.replace("  Готово когда: пустой отчёт → 200.\n", "")
        self.assertIn("B-2: нет «Готово когда»", lint(text))

    def test_in_work_without_worktree_or_session(self):
        text = OK.replace("`worktree-A-2` · сессия `A-2 [1a2b3c]` · ", "")
        errors = lint(text)
        self.assertIn("A-2: в работе, но не указано где — `worktree-…` или «основная копия»", errors)
        self.assertIn("A-2: в работе, но нет сессии", errors)

    def test_in_work_in_main_copy_or_foreign_worktree(self):
        text = OK.replace("`worktree-A-2`", "основная копия")
        self.assertEqual(lint(text), [])
        self.assertEqual(lint(OK.replace("`worktree-A-2`", "`worktree-B-1`")), [])

    def test_dropped_status(self):
        text = OK.replace("Экспорт CSV — запланирован · —", "Экспорт CSV — `S` · снят 17.09 · перенесён в TECH_DEBT.md")
        self.assertEqual(lint(text), [])
        self.assertEqual(ready(text), [])

    def test_dropped_status_with_parenthesis(self):
        text = OK.replace("Экспорт CSV — запланирован · —", "Экспорт CSV — снят (перенесён в TECH_DEBT.md)")
        self.assertEqual(lint(text), [])

    def test_done_criterion_without_number(self):
        text = OK.replace("Готово когда: пустой отчёт → 200.", "Готово когда: экспорт работает.")
        self.assertIn("B-2: в «Готово когда» нет числа", lint(text))

    def test_критерий_без_числа_ловится(self):
        text = (
            "- **A-1** Экспорт — запланирован\n"
            "  Мои пути: src/**\n"
            "  Готово когда: работает хорошо.\n"
        )
        self.assertTrue(any("числ" in claim.lower() for claim in lint(text)))

    def test_done_keeps_worktree(self):
        text = OK.replace("готов · 01.09", "готов · `worktree-A-1` · 01.09")
        self.assertIn("A-1: готов, но осталась пометка `worktree-A-1`", lint(text))

    def test_unknown_dependency(self):
        text = OK.replace("зависит от: A-2", "зависит от: A-2, C-7")
        self.assertIn("B-1: зависит от несуществующего C-7", lint(text))

    def test_dependency_cycle(self):
        text = OK.replace("  Готово когда: 500 строк", "  Зависит от: B-2\n  Готово когда: 500 строк")
        text = text.replace("Экспорт CSV — запланирован · —", "Экспорт CSV — запланирован · — · зависит от: B-1")
        self.assertTrue(any("цикл зависимостей" in e for e in lint(text)))

    def test_taken_while_blocked(self):
        text = OK.replace("Экспорт PDF — запланирован · —", "Экспорт PDF — 🔨 в работе · `worktree-B-1` · сессия `B-1` · с 12.09")
        self.assertIn("B-1: взят в работу, но не готовы зависимости: A-2", lint(text))

    def test_status_word_in_title_is_not_status(self):
        text = OK.replace("Экспорт CSV — запланирован · —", "Отчёт готов к печати — запланирован · —")
        self.assertEqual(lint(text), [])

    def test_ready_queue(self):
        # B-1 ждёт A-2 (в работе), B-2 свободен
        self.assertEqual(ready(OK), ["B-2"])

    def test_dependency_on_archived_item(self):
        # Закрытый пункт уехал в DONE.md — зависимость на него законна
        text = OK.replace("Готово когда: пустой отчёт → 200.", "Готово когда: пустой отчёт → 200.\n  Зависит от: A-9")
        self.assertEqual(lint(text, LEDGER), [])
        self.assertIn("B-2: зависит от несуществующего A-9", lint(text))

    def test_ready_with_archived_dependency(self):
        text = OK.replace("Готово когда: пустой отчёт → 200.", "Готово когда: пустой отчёт → 200.\n  Зависит от: A-9")
        self.assertEqual(ready(text, LEDGER), ["B-2"])

    def test_снятая_зависимость_не_делает_пункт_готовым(self):
        # Снятый пункт тоже в DONE.md, но работа брошена, а не сделана
        ledger = LEDGER + "\n### Снято\n\n- **A-8** Свой рендерер — 11.08 · headless Chrome дешевле.\n"
        text = OK.replace("Готово когда: пустой отчёт → 200.", "Готово когда: пустой отчёт → 200.\n  Зависит от: A-8")
        self.assertEqual(ready(text, ledger), [])
        self.assertIn("B-2: зависит от снятого A-8 — убери зависимость или сними пункт", lint(text, ledger))

    def test_заголовок_снято_распознаётся_с_хвостом_и_эмодзи(self):
        # Заголовок пишет сессия прозой; не узнать подраздел — значит зачесть
        # брошенную работу за выполненную зависимость
        text = OK.replace("Готово когда: пустой отчёт → 200.",
                          "Готово когда: пустой отчёт → 200.\n  Зависит от: A-8")
        for header in ("## Снято", "## Снято (архив)", "### Снятые пункты",
                       "## Dropped items", "## 🗑 Снято"):
            ledger = LEDGER + f"\n{header}\n\n- **A-8** Свой рендерер — 11.08 · причина.\n"
            self.assertEqual(ready(text, ledger), [], header)

    def test_номер_снятого_пункта_занят_навсегда(self):
        ledger = LEDGER + "\n### Снято\n\n- **B-2** Экспорт CSV — 11.08 · формат не нужен.\n"
        self.assertIn("B-2: номер занят, пункт уже в DONE.md", lint(OK, ledger))

    def test_duplicate_id_across_ledger(self):
        # Номер, уже уехавший в архив, переиспользовать нельзя
        ledger = LEDGER.replace("A-9", "B-2")
        self.assertIn("B-2: номер занят, пункт уже в DONE.md", lint(OK, ledger))

    def test_ledger_link_must_resolve(self):
        # Ссылки тезиса ведут в существующие файлы; относительны к папке DONE.md
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "done/A-9").mkdir(parents=True)
            (Path(d) / "done/A-9/STATUS.md").write_text("x", encoding="utf-8")
            self.assertEqual(orphans(LEDGER, Path(d)), [])
            self.assertIn("A-14: ссылка done/A-14/STATUS.md никуда не ведёт",
                          orphans(LEDGER.replace("A-9", "A-14"), Path(d)))

    def test_ledger_entry_without_status_is_fine(self):
        # Мелкий пункт закрылся в одну сессию: STATUS.md не было, ссылки нет — это норма
        ledger = LEDGER.replace(" · [STATUS](done/A-9/STATUS.md)", "")
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(orphans(ledger, Path(d)), [])

    def test_английский_роадмап_проходит_линт(self):
        text = (
            "- **A-1** Export to PDF — planned\n"
            "  My paths: src/**\n"
            "  Done when: a 500-row report renders in under 3 s.\n"
        )
        self.assertEqual(lint(text), [])

    def test_английский_критерий_без_числа_ловится(self):
        text = (
            "- **A-1** Export to PDF — planned\n"
            "  My paths: src/**\n"
            "  Done when: it works well.\n"
        )
        self.assertTrue(any("числ" in c.lower() or "number" in c.lower() for c in lint(text)))

    def test_фраза_заголовка_в_прозе_не_считается_критерием(self):
        # «Done when» упомянут в прозе, не как заголовок своей строки — критерия на самом деле нет
        text = (
            "- **A-1** Локализация линта — запланирован · —\n"
            "  Мои пути: hooks/**\n"
            "  Переводим заголовок «Done when» на 3 языка.\n"
        )
        self.assertIn("A-1: нет «Готово когда»", lint(text))

    def test_критерий_на_своей_строке_по_прежнему_проходит(self):
        text = (
            "- **A-1** Локализация линта — запланирован · —\n"
            "  Мои пути: hooks/**\n"
            "  Готово когда: заголовок переведён на 3 языка.\n"
        )
        self.assertEqual(lint(text), [])

    def test_английский_черновик_без_статуса_определяется_по_my_paths(self):
        # Ни статуса, ни «Готово когда», ни зависимостей — язык узнаётся по «My paths»
        text = "- **A-1** Export to PDF\n  My paths: src/**\n"
        errors = lint(text)
        self.assertIn("A-1: no status", errors)
        self.assertFalse(any("нет статуса" in e for e in errors))


class HookTest(unittest.TestCase):
    def run_hook(self, file_path, lang=None):
        payload = json.dumps({"tool_name": "Edit", "tool_input": {"file_path": str(file_path)}})
        cmd = [sys.executable, str(SCRIPT)] + ([lang] if lang else [])
        return subprocess.run(cmd, input=payload, capture_output=True, text=True)

    def broken(self, d):
        path = Path(d) / "ROADMAP.md"
        path.write_text(OK.replace("  Готово когда: пустой отчёт → 200.\n", ""), encoding="utf-8")
        return path

    def test_язык_плагина_задаёт_весь_вывод_а_не_только_заголовок(self):
        """Русский роадмап под английским плагином: и скилл в заголовке, и сами
        жалобы — того плагина, что позвал линт. Иначе половина вывода зовёт в
        скилл, которого у пользователя не установлено."""
        with tempfile.TemporaryDirectory() as d:
            result = self.run_hook(self.broken(d), "en")
        self.assertEqual(result.returncode, 2)
        self.assertIn("skill `mast:managing-roadmap-items`", result.stderr)
        self.assertIn('no "Done when"', result.stderr)
        self.assertNotIn("Готово когда", result.stderr)

    def test_русский_плагин_зовёт_свой_скилл(self):
        with tempfile.TemporaryDirectory() as d:
            result = self.run_hook(self.broken(d), "ru")
        self.assertEqual(result.returncode, 2)
        self.assertIn("скилл `mast-ru:managing-roadmap-items`", result.stderr)

    def test_hook_ignores_other_files(self):
        self.assertEqual(self.run_hook("/tmp/README.md").returncode, 0)

    def test_hook_blocks_broken_roadmap(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "ROADMAP.md"
            path.write_text(OK.replace("  Готово когда: пустой отчёт → 200.\n", ""), encoding="utf-8")
            result = self.run_hook(path)
        self.assertEqual(result.returncode, 2)
        self.assertIn("B-2: нет «Готово когда»", result.stderr)

    def test_hook_reports_only_new_errors(self):
        # Старое нарушение из HEAD хук не показывает — его чинит не текущая сессия
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "ROADMAP.md"
            path.write_text(OK.replace("  Готово когда: пустой отчёт → 200.\n", ""), encoding="utf-8")
            git = ["git", "-C", d, "-c", "user.name=t", "-c", "user.email=t@t"]
            subprocess.run(git + ["init", "-q"], check=True)
            subprocess.run(git + ["add", "."], check=True)
            subprocess.run(git + ["commit", "-qm", "init"], check=True)
            self.assertEqual(self.run_hook(path).returncode, 0)
            path.write_text(path.read_text(encoding="utf-8") + "\n- **B-3** Новый — —\n  Готово когда: 1 шт.\n",
                            encoding="utf-8")
            result = self.run_hook(path)
        self.assertEqual(result.returncode, 2)
        self.assertIn("B-3: нет статуса", result.stderr)
        self.assertNotIn("B-2", result.stderr)

    def test_hook_reads_ledger_next_to_roadmap(self):
        # docs/roadmap/DONE.md ищется относительно самого ROADMAP.md
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "ROADMAP.md"
            path.write_text(OK.replace("Готово когда: пустой отчёт → 200.",
                                       "Готово когда: пустой отчёт → 200.\n  Зависит от: A-9"), encoding="utf-8")
            ledger = Path(d) / "docs/roadmap/DONE.md"
            ledger.parent.mkdir(parents=True)
            ledger.write_text(LEDGER, encoding="utf-8")
            # Тезис A-9 ссылается на done/A-9/STATUS.md — хук проверяет и ссылки
            (ledger.parent / "done/A-9").mkdir(parents=True)
            (ledger.parent / "done/A-9/STATUS.md").write_text("x", encoding="utf-8")
            self.assertEqual(self.run_hook(path).returncode, 0)
            ledger.write_text("# Сделано\n", encoding="utf-8")
            self.assertEqual(self.run_hook(path).returncode, 2)

    def test_hook_проверяет_пару_по_правке_архива(self):
        # Правят DONE.md — линт смотрит на пару «роадмап + архив», иначе снятые
        # пункты и занятые номера не проверяет никто и никогда
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "ROADMAP.md").write_text(
                OK.replace("Готово когда: пустой отчёт → 200.",
                           "Готово когда: пустой отчёт → 200.\n  Зависит от: A-8"),
                encoding="utf-8")
            ledger = root / "docs/roadmap/DONE.md"
            ledger.parent.mkdir(parents=True)
            ledger.write_text("# Сделано\n\n## Снято\n\n- **A-8** Рендерер — 11.08 · причина.\n",
                              encoding="utf-8")
            result = self.run_hook(ledger)
        self.assertEqual(result.returncode, 2)
        self.assertIn("зависит от снятого A-8", result.stderr)

    def test_hook_passes_valid_roadmap(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "ROADMAP.md"
            path.write_text(OK, encoding="utf-8")
            self.assertEqual(self.run_hook(path).returncode, 0)


if __name__ == "__main__":
    unittest.main()
