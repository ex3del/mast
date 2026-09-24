---
paths:
  - "hooks/review.py"
  - "hooks/mast.py"
  - "plugins/*/locales/*/review.md"
---

# Ревьюер `mast merge`

После правки промпта ревьюера (`review.md`, любой язык), его вызова (`hooks/review.py`) или того,
что ему кладёт во вход `hooks/mast.py` (`memory()`, `verdict()`), — живой замер:
`MAST_LIVE=1 python3 -m pytest tests/test_review_live.py -v -s`. Это 24 вызова настоящего `claude -p`
на `opus`: платно, минут 30. Каждый вердикт должен попасть в допустимые для своей фикстуры; упал хоть
один — правка испортила ревьюера. Обычный `pytest` этот файл пропускает, поэтому без замера порча не видна.
