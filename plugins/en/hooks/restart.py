# Сгенерировано tools/sync_plugins.py из hooks/restart.py — правь там, здесь затрётся
"""Подсказка перезапуска диспетчеру после `mast merge` (A-24): контекст выше порога —
«перезапусти: `/clear`» в `additionalContext`, не блокирует. Перезапуск ничего не теряет —
роль и `mast status` вернёт справка на старте (`dispatcher.py`), — а контекст перечитывается
каждым ходом, и автосжатие перескажет разговор посреди работы.

Зовёт медленный путь PostToolUse в `roadmap_watch.py`. Отдельным модулем, а не в
`dispatcher.py`: тот запускается на каждый Edit/Write и компилируется целиком, этот код
удорожил бы каждую правку на 0,3–0,6 мс, а нужен только после вливания.
"""
import json
import os
import re
from pathlib import Path

from dispatcher import is_dispatcher

# Порог, тыс. токенов. Замер `tools/dispatcher_context.py` по диспетчерам mast и reinhold:
# автосжатие на 667 тыс. минус наибольший прирост контекста между вливаниями, 162 тыс., —
# подсказка приходит раньше, чем автосжатие успеет до следующего вливания
RESTART_DEFAULT = 500
RESTART = re.compile(r"(?:порог перезапуска|restart threshold)\s*:\s*(\d+)", re.I)
MAST_MERGE = re.compile(r"(?<![\w-])mast\s+merge\s+[A-Z]-\d+")
# Хвост транскрипта, где ищется последний ответ модели: сам файл у диспетчера — десятки МБ
TAIL = 1 << 20
HINT = {
    "ru": "MAST: вливание прошло, а контекст этой сессии — {n} тыс. токенов при пороге {t} тыс. "
          "Каждый ход перечитывает его целиком, а автосжатие перескажет разговор посреди работы. "
          "Передай человеку: перезапусти: `/clear` — справка на старте вернёт роль и `mast status`, "
          "пункты и вопросы лежат в `ROADMAP.md`. Порог — строка `Порог перезапуска: <тыс. токенов>` "
          "в `.claude/mast.md`.",
    "en": "MAST: the merge is done, and this session's context is {n}k tokens against a {t}k "
          "threshold. Every turn rereads it whole, and auto-compaction will retell the conversation "
          "mid-work. Tell the human: restart with `/clear` — the start-up brief brings back the role "
          "and `mast status`, items and questions live in `ROADMAP.md`. The threshold is the line "
          "`Restart threshold: <k tokens>` in `.claude/mast.md`.",
}


def usage_context(usage):
    """Контекст хода по `usage` ответа модели. С советником `usage` — сумма итераций, две из них
    основной модели: контекст вышел бы вдвое больше. Берётся последняя итерация основной модели."""
    usage = ([i for i in usage.get("iterations") or [] if i.get("type") == "message"] or [usage])[-1]
    return sum(usage.get(k, 0) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))


def last_context(transcript):
    """Контекст последнего записанного ответа модели или None. Площадка дописывает транскрипт
    с отставанием на ход-другой — ошибка в тысячи токенов при пороге в сотни тысяч."""
    try:
        with open(transcript, "rb") as f:
            f.seek(max(0, f.seek(0, 2) - TAIL))
            lines = f.read().splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        if b'"usage"' not in line:
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue  # обрезанная первая строка хвоста или недописанная последняя
        usage = r.get("type") == "assistant" and not r.get("isSidechain") and r["message"].get("usage")
        if usage:
            return usage_context(usage)
    return None


def hint(payload, lang):
    """Текст подсказки или None. PostToolUse приходит только на Bash с кодом 0 — отказ идёт
    в PostToolUseFailure, — поэтому `mast merge` здесь уже влил пункт."""
    if not MAST_MERGE.search(payload["tool_input"].get("command", "")) or not is_dispatcher(payload):
        return None
    n = last_context(payload["transcript_path"])
    settings = Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload["cwd"]) / ".claude" / "mast.md"
    m = settings.is_file() and RESTART.search(settings.read_text(encoding="utf-8"))
    limit = int(m.group(1)) if m else RESTART_DEFAULT
    if n is None or n <= limit * 1000:
        return None
    return HINT[lang].format(n=n // 1000, t=limit)
