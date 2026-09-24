# Сгенерировано tools/sync_plugins.py из hooks/review.py — правь там, здесь затрётся
"""Ревью ветки с чистым контекстом: отдельный `claude -p` видит только дифф и «Готово когда».

`--safe-mode` выключает CLAUDE.md, плагины, хуки и MCP, но не вход по подписке
(`--bare` читает только ANTHROPIC_API_KEY); `--tools ""` — ревьюер не ходит по
репозиторию, и история пункта до него не доходит. Промпт — `locales/<язык>/review.md`
плагина, ответ — JSON по схеме. Нет ответа по схеме — `NoVerdict`: без вердикта не вливают.
"""
import json
import subprocess
from pathlib import Path

VERDICTS = ("ok", "refuse", "unsure")
SCHEMA = {"type": "object", "additionalProperties": False,
          "properties": {"verdict": {"enum": list(VERDICTS)},
                         "reasons": {"type": "array", "items": {"type": "string"}},
                         "question": {"type": "string"}},
          "required": ["verdict", "reasons", "question"]}
MODEL = "opus"
TIMEOUT = 600
USAGE = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")


class NoVerdict(Exception):
    pass


def ask(lang, diff, crit, strict):
    """(вердикт, причины, вопрос человеку, токены) по диффу и критерию.
    strict — файлы диффа, которые агенты читают как правила: для них планка строже."""
    prompt = (Path(__file__).resolve().parent.parent / "locales" / lang / "review.md").read_text(encoding="utf-8")
    task = (f"<criterion>\n{crit}\n</criterion>\n<strict_files>\n{chr(10).join(strict)}\n</strict_files>\n"
            f"<diff>\n{diff}\n</diff>\n")
    cmd = ["claude", "-p", "--safe-mode", "--tools", "", "--no-session-persistence", "--model", MODEL,
           "--output-format", "json", "--json-schema", json.dumps(SCHEMA), "--system-prompt", prompt]
    try:
        r = subprocess.run(cmd, input=task, capture_output=True, text=True, encoding="utf-8", timeout=TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise NoVerdict(str(e))
    try:
        out = json.loads(r.stdout)
        v = out["structured_output"]
        verdict, reasons, question = v["verdict"], [str(x) for x in v["reasons"]], str(v["question"])
    except (ValueError, KeyError, TypeError):
        raise NoVerdict((r.stderr or r.stdout).strip()[:500] or f"claude -p: {r.returncode}")
    if out.get("is_error") or verdict not in VERDICTS:
        raise NoVerdict(str(out.get("result") or verdict)[:500])
    tokens = sum((out.get("usage") or {}).get(k) or 0 for k in USAGE)
    return verdict, reasons, question.strip(), tokens
