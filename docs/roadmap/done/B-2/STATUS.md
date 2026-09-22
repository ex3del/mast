# B-2 Приём вкладов: CONTRIBUTING, CI, защита `main`, шаблоны

**Мои пути:** .github/**, CONTRIBUTING.md, CONTRIBUTING.ru.md, tools/check_version_bump.py, README.md, README.ru.md, TECH_DEBT.md
**Не трогаю:** hooks/, locales/, plugins/ — метод не меняется, бамп версии не нужен
**Готово когда:** CI на `main` зелёный на всех тестах; тестовый PR, меняющий `locales/` без бампа версии, получает красный CI — 1 из 1; `main` требует зелёный CI для PR; ветки удаляются после мерджа; community health на GitHub ≥ 85%.

`STATUS.md` заведён по признаку «работа переживёт `/compact`»: сессия длинная.

## Задачи

- [x] CI: pytest, синхронность копий в `plugins/`, бамп версии относительно базы PR
- [x] `CONTRIBUTING.md` (en) и `CONTRIBUTING.ru.md`
- [x] шаблоны: issue «баг», issue «идея», PR
- [x] защита `main`: CI обязателен для PR, владелец пушит напрямую
- [x] удаление ветки после мерджа
- [x] проверка: тестовый PR без бампа — CI красный
- [x] кодекс поведения `.github/CODE_OF_CONDUCT.md` — health не добирал до 85%

## Журнал

- 22.09 — базовый замер: CI нет, `main` не защищён, шаблонов и `CONTRIBUTING` нет, удаление веток после мерджа выключено, community health 42% (`gh api repos/ex3del/mast/community/profile --jq .health_percentage`).
- 22.09 — CI на `main` зелёный: 104 теста. Защита `main`: обязательный check `test`, force-push и удаление запрещены, владелец пушит напрямую. `delete_branch_on_merge` включён.
- 22.09 — проверка: [PR #1](https://github.com/ex3del/mast/pull/1) правит `locales/ru/core.md` без бампа → шаг «Plugin version grew if the method changed» красный, `mergeStateStatus: BLOCKED` — 1 из 1. PR закрыт без мерджа, ветка удалена.
- 22.09 — health после CONTRIBUTING и шаблонов 71%: YAML-формы issue профиль сообщества не засчитывает (`issue_template: null`). С `.github/CODE_OF_CONDUCT.md` — 85%.

## Проблемы

- Профиль сообщества GitHub не видит issue forms (`.github/ISSUE_TEMPLATE/*.yml`) — 85% добрано кодексом поведения, а не шаблонами.

## Принятые решения

- Бамп версии в CI проверяется сравнением версий базы и головы PR, а не временем коммитов, как в `tests/test_version_bump.py`: коммит контрибьютора бывает старше последнего бампа в `main`, и проверка по времени пропустит PR без бампа.
