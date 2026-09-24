---
paths:
  - "hooks/review.py"
  - "plugins/*/locales/*/review.md"
---

# Ревьюер `mast merge`

После правки промпта ревьюера (`review.md`, любой язык) или его вызова (`hooks/review.py`) — живой замер:
`MAST_LIVE=1 python3 -m pytest tests/test_review_live.py -v -s`. Это 9 вызовов настоящего `claude -p`
на `opus`: платно, несколько минут. Все 9 вердиктов должны совпасть с ожидаемыми; упал хоть один —
правка испортила ревьюера. Обычный `pytest` этот файл пропускает, поэтому без замера порча не видна.
