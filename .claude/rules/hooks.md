---
paths:
  - "hooks/dispatcher.py"
  - "hooks/roadmap_watch.py"
  - "hooks/restart.py"
  - "plugins/*/hooks/hooks.json"
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
