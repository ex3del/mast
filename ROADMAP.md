# ROADMAP

Разделы буквами, пункты цифрами внутри раздела. Держит только открытое; закрытое и снятое
уезжают в [docs/roadmap/DONE.md](docs/roadmap/DONE.md).

## A. Плагин

- **A-10** Порт на Codex CLI из этого же репозитория — запланирован · —
  В Codex есть плагины, скиллы `SKILL.md`, хуки `SessionStart`/`PostToolUse` и маркетплейс из GitHub — метод ставится рядом с Claude-плагином, как у superpowers: `.codex-plugin/plugin.json` в `plugins/<язык>/`, `.agents/plugins/marketplace.json` в корне. `/init-project` становится скиллом, Claude-специфичные команды диспетчера переводит словарь `codex-tools.md`; связь сессий с диспетчером — через `docs/roadmap/inbox/`, `codex queue` не документирован. Проверка — живьём на бесплатном аккаунте ChatGPT: A-7 показал, что проверка в обход настоящей установки врёт.
  Мои пути: plugins/*/.codex-plugin/**, .agents/**, hooks/**, locales/*/**, tools/sync_plugins.py, tests/**, README.md, README.ru.md, CONTRIBUTING.md, CONTRIBUTING.ru.md
  Готово когда: в песочнице на Codex CLI ≥ 0.156, плагины `mast` и `mast-ru` поставлены через `codex plugin marketplace add ex3del/mast`: маркер ядра в контексте — 2 из 2; линт после правки `ROADMAP.md` через `apply_patch` вернул ошибку на критерии без числа — 2 из 2; 4 скилла видны в `/skills` — 8 из 8; сторож: каждая Claude-специфичная команда из скиллов (`claude --bg`, `claude agents`, `ListAgents`, `SendMessage`, `--advisor`) есть в `codex-tools.md` — 0 непокрытых; набор тестов Claude-плагинов зелёный.

## B. Продвижение

- **B-1** Демо-GIF в шапке README — запланирован · —
  Плагин без картинки работы не ставят: README объясняет метод словами, но не показывает. Нужна запись одного терминала, где диспетчер ведёт несколько пунктов.
  Мои пути: assets/**, README.md, README.ru.md
  Готово когда: GIF ≤ 30 с и ≤ 5 МБ стоит в шапке обоих README и показывает в одном терминале, как диспетчер запускает ≥ 2 пункта параллельно, вливает ветку и переносит закрытый пункт в `DONE.md`.
