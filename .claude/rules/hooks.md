---
paths:
  - "hooks/dispatcher.py"
  - "hooks/roadmap_watch.py"
  - "hooks/restart.py"
  - "hooks/mast.py"
  - "hooks/prod.py"
  - "plugins/*/hooks/hooks.json"
  - "plugins/*/locales/*/templates/*.template.md"
---

# Хуки на Edit/Write и git-команды

Новая проверка на Edit/Write или git-команду — в существующий хук (`hooks/dispatcher.py`; для Bash —
медленный путь `hooks/roadmap_watch.py`), а не новым хуком в `hooks.json`: каждый хук — отдельный старт
python3, около 10 мс на каждый вызов инструмента. Накладные меряются парно: старый и новый хук вперемешку,
python3 из PATH. Абсолютное время зависит от машины (на батарее после сна старый хук — 21 мс), сравнивается
разница.

Код, нужный только на медленном пути Bash, — отдельным модулем с ленивым импортом из `roadmap_watch.py`
(как `hooks/restart.py`), а не в `dispatcher.py`: тот запускается на каждый Edit/Write и компилируется
целиком, 3,8 КБ лишнего кода в нём стоили Edit/Write +0,3–0,6 мс (A-24).

Настройка проекта для скриптов плагина — строка `Ключ: значение` в `.claude/mast.md` (шаблон
`mast.template.md`, ключ на обоих языках), не в `.claude/rules/`: файл в `rules/` агент получает
в контекст, а `dispatch.md` своим наличием разрешает `sonnet` (A-25).

Новое слово в фильтре `if` на Bash (`prod.FILTER`, `hooks.json`) — ещё один процесс python3 на каждую
команду, которую площадка не может разобрать (7,7% команд): их она отдаёт всем обработчикам разом.
Мерить `python3 tools/hook_overhead.py <база> 60 --mix ~/.claude/projects` до и после (A-26).
