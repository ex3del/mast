---
paths:
  - "hooks/review.py"
  - "hooks/mast.py"
  - "plugins/*/locales/*/review.md"
---

# Ревьюер `mast merge`

После правки промпта ревьюера (`review.md`, любой язык), его вызова (`hooks/review.py`) или того,
что ему кладёт во вход `hooks/mast.py` (`memory()`, `verdict()`), — `python3 tools/sync_plugins.py`
(замер берёт `mast` из `plugins/ru/hooks`, без sync проверяется старый код) и живой замер:
`MAST_LIVE=1 python3 -m pytest tests/test_review_live.py -v -s`. Это 33 вызова настоящего `claude -p`
на `opus`: платно, около 25 минут. Каждый вердикт должен попасть в допустимые для своей фикстуры; упал
хоть один — правка испортила ревьюера. Обычный `pytest` этот файл пропускает, поэтому без замера порча не видна.

Часть фикстур (базовый замер новых) — `-o disable_test_id_escaping_and_forfeit_all_rights_to_community_support=true
-k <слово из имени фикстуры>`: имена кириллицей, без флага pytest экранирует их в `\uXXXX`, и `-k` не находит ничего.
