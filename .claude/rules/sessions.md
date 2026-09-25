---
paths:
  - "hooks/mast.py"
---

# Сессии после вливания: живой тест

После правки в `hooks/mast.py` того, что решает судьбу сессий пунктов, — `alive()`, `agents()`,
`session()`, `last_message()`, `ask_line()`, `closed_line()`, `sweep()`, `cleanup()` — живой тест
на установленном плагине (по CLAUDE.md, «Живая проверка установки»):
`MAST_LIVE=1 MAST_BIN=<bin/mast из кэша плагина> python3 -m pytest tests/test_hot_hour_live.py -v -s`.
Обычный набор ходит в заглушку `claude` и не заметит, что Claude Code поменял вывод `claude agents`
или поведение `claude rm` — так `mast status` уже считал упавшую сессию живой. Тест платный
(фоновая сессия и ревьюер), несколько минут. Правка `mast start`, проверок `mast merge` и текстов
его не требует.
