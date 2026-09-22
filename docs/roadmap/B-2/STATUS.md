# B-2 Приём вкладов: CONTRIBUTING, CI, защита `main`, шаблоны

**Мои пути:** .github/**, CONTRIBUTING.md, CONTRIBUTING.ru.md, tools/check_version_bump.py, README.md, README.ru.md, TECH_DEBT.md
**Не трогаю:** hooks/, locales/, plugins/ — метод не меняется, бамп версии не нужен
**Готово когда:** CI на `main` зелёный на всех тестах; тестовый PR, меняющий `locales/` без бампа версии, получает красный CI — 1 из 1; `main` требует зелёный CI для PR; ветки удаляются после мерджа; community health на GitHub ≥ 85%.

`STATUS.md` заведён по признаку «работа переживёт `/compact`»: сессия длинная.

## Задачи

- [ ] CI: pytest, синхронность копий в `plugins/`, бамп версии относительно базы PR
- [ ] `CONTRIBUTING.md` (en) и `CONTRIBUTING.ru.md`
- [ ] шаблоны: issue «баг», issue «идея», PR
- [ ] защита `main`: CI обязателен для PR, владелец пушит напрямую
- [ ] удаление ветки после мерджа
- [ ] проверка: тестовый PR без бампа — CI красный

## Журнал

- 22.09 — базовый замер: CI нет, `main` не защищён, шаблонов и `CONTRIBUTING` нет, удаление веток после мерджа выключено, community health 42% (`gh api repos/ex3del/mast/community/profile --jq .health_percentage`).

## Проблемы

## Принятые решения

- Бамп версии в CI проверяется сравнением версий базы и головы PR, а не временем коммитов, как в `tests/test_version_bump.py`: коммит контрибьютора бывает старше последнего бампа в `main`, и проверка по времени пропустит PR без бампа.
