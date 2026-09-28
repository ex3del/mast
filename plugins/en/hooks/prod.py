# Сгенерировано tools/sync_plugins.py из hooks/prod.py — правь там, здесь затрётся
"""Прод-команды у диспетчера (A-26): основному потоку `*-dispatch` — отказ. Выкладку после
вливания делает сессия пункта — `mast merge` печатает ей поручение, — а состояние прода читает
субагент: у него во входе хука `agent_id`, и `roadmap_watch.py` сюда его не пускает.

Зовёт PreToolUse в `roadmap_watch.py`, куда вызов попадает фильтром `if` на слова `FILTER`
(`hooks.json`): хук на каждую команду оболочки стоил бы всем пользователям плагина ~12 мс.
Шаблон `Прод:` с другого слова (`python scripts/…`) хук поэтому видит, только если команда
запущена через эти слова.

Прод — базовый список внешних инструментов (`base`) и шаблоны строк `Прод:`/`Prod:` из
`.claude/mast.md` (`declared`). Разбор по сегментам с маской кавычек, тела `bash <<`,
`bash -c` и файл из `bash <файл>` — перенос из `measure.py` ресёрча 2026-09-25-prod-ops:
подстрока `ssh|docker` дала бы 17% ложных отказов.
"""
import os
import re
from pathlib import Path

# Слова фильтра `if` в `hooks.json`: `Bash(<слово> *)`, у `clearml*` — без пробела
# (сторож в tests/test_hooks_wiring.py)
FILTER = ("ssh", "scp", "rsync", "aws", "mc", "rclone", "lakectl", "clearml*", "kubectl", "dvc",
          "docker", "curl", "bash", "sh")
SETTING = re.compile(r"^(?:Прод|Prod)\s*:(.*)$", re.M)
QUOTE = re.compile(r"'[^']*'|\"(?:\\.|[^\"\\])*\"")
# `&` — фон и оператор вызова PowerShell, но не `2>&1` и `&>`
SEP = re.compile(r"\n|;|&&|\|\||\||(?<![<>])&(?!>)|\$\(|`|\(|\)|\{|\}|\b(?:then|do|else|elif)\b")
HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_]\w*)\1")
ENV = re.compile(r"[A-Za-z_]\w*=")
PS_ENV = re.compile(r"\$env:(\w+)(?:=(.*))?$", re.I)
WRAP = {"time", "timeout", "env", "nohup", "sudo", "command", "exec", "xargs", "nice", "watch", "!",
        "if", "while", "until"}
SHELLS = {"bash", "sh", "zsh", "source", "."}
SSH_ARG = set("bcDEeFIiJLlmOopQRSWw")
MC = set("cp ls mirror rm mv cat stat du find tree head".split())
# Сколько читать из `bash <файл>` и насколько глубоко раскрывать вложенные оболочки
SCRIPT_LIMIT = 1 << 16
DEPTH = 3

REFUSAL = {
    "ru": "MAST: диспетчер не ходит на прод — `{c}` среди прод-команд проекта (базовый список "
          "плагина или строка `Прод:` в `.claude/mast.md`). Выкладку после вливания делает сессия "
          "пункта: `mast merge` печатает для неё поручение — перешли его через SendMessage. "
          "Состояние прода — субагентом `Agent`: его команды хук пропускает, а в твой контекст "
          "вернётся выжимка, а не весь вывод.",
    "en": "MAST: the dispatcher doesn't go to prod — `{c}` is among the project's prod commands "
          "(the plugin's base list or the `Prod:` line in `.claude/mast.md`). The item session "
          "deploys after the merge: `mast merge` prints an assignment for it — forward it via "
          "SendMessage. Prod state — via an `Agent` subagent: the hook lets its commands through, "
          "and your context gets a summary instead of the whole output.",
}


def patterns(project):
    """Шаблоны строк `Прод:`/`Prod:` из `.claude/mast.md` списками слов. Строк может быть
    несколько, запятая — только разделитель, обратные кавычки вокруг шаблона не значимы."""
    try:
        text = (Path(project) / ".claude" / "mast.md").read_text(encoding="utf-8")
    except OSError:
        return []
    return [p.split() for line in SETTING.findall(text) for p in line.replace("`", "").split(",") if p.split()]


def segments(text):
    """(слово команды, аргументы, окружение, текст) по сегментам. Кавычки маскируются только
    для поиска разделителей: аргументы — исходный текст без кавычек, иначе адрес в
    `curl "https://…"` не сверить с шаблоном."""
    masked = QUOTE.sub(lambda m: m[0][0] + "\0" * (len(m[0]) - 2) + m[0][-1], text)
    cuts = [0, *(i for m in SEP.finditer(masked) for i in m.span()), len(text)]
    for a, b in zip(cuts[::2], cuts[1::2]):
        toks = [re.sub(r"['\"]", "", text[a + t.start():a + t.end()]) for t in re.finditer(r"\S+", masked[a:b])]
        env = {}
        while toks and (ENV.match(toks[0]) or toks[0] in WRAP or toks[0].isdigit()):
            key, eq, value = toks.pop(0).partition("=")
            if eq:
                env[key] = value
        if toks:
            yield toks[0], toks[1:], env, text[a:b].strip()


def split_heredocs(command):
    """Текст без тел heredoc и тела: (слово-потребитель, файл из `> f`/`tee f`, тело)."""
    lines, out, docs, i = command.split("\n"), [], [], 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        i += 1
        for m in HEREDOC.finditer(line):
            body = []
            while i < len(lines) and lines[i].strip() != m[2]:
                body.append(lines[i])
                i += 1
            i += 1
            head = SEP.split(QUOTE.sub("''", line[:m.start()]))[-1]
            words = [w for w in head.split() if not ENV.match(w)]
            f = re.search(r"(?:>>?|\btee\s+(?:-a\s+)?)\s*[\"']?([^\s\"'<>;|&]+)", head)
            docs.append((words[0] if words else "", f[1] if f else "", "\n".join(body)))
    return "\n".join(out), docs


def ssh_host(args):
    """В аргументах `ssh` есть хост; `ssh -G` читает только локальный конфиг."""
    i = 0
    while i < len(args):
        a = args[i]
        if not a.startswith("-") or len(a) == 1:
            return True
        if "G" in a[1:] and not a.startswith("-o"):
            return False
        i += 2 if len(a) == 2 and a[1] in SSH_ARG else 1
    return False


def remote_docker(args, env):
    """`docker` на чужой демон: `--context`/`-c`/`--host`/`-H` или `DOCKER_CONTEXT`/`DOCKER_HOST`.
    `docker context …` и `compose … config` читают только локальный конфиг, `default` — локальный демон."""
    if args[:1] == ["context"] or args[:1] == ["compose"] and "config" in args:
        return False
    ctx = env.get("DOCKER_CONTEXT") or env.get("DOCKER_HOST")
    for i, a in enumerate(args):
        if not a.startswith("-"):
            break
        if a in ("--context", "-c", "--host", "-H") and i + 1 < len(args):
            ctx = args[i + 1]
        elif a.startswith(("--context=", "--host=")):
            ctx = a.split("=", 1)[1]
    return ctx not in (None, "", "default")


def base(word, args, env):
    """Внешний инструмент из базового списка — прод и без строки `Прод:`."""
    if word == "docker":
        return remote_docker(args, env)
    if env.get("DOCKER_CONTEXT") not in (None, "", "default") or env.get("DOCKER_HOST"):
        return True  # раннер проекта, внутри которого `docker exec` на прод
    if word == "ssh":
        return ssh_host(args)
    if word in ("scp", "rsync"):
        return any(re.match(r"[\w.@-]{2,}:", a) for a in args)
    if word == "aws":
        return "s3" in args or "s3api" in args
    if word == "mc":
        return bool(args) and args[0] in MC
    if word == "dvc":
        return args[:1] in (["push"], ["pull"], ["fetch"])
    return word in ("rclone", "lakectl", "kubectl") or word.startswith("clearml")


def declared(word, args, env, pats):
    """Совпал шаблон `Прод:`: первое слово — слово команды или `ИМЯ=значение` окружения,
    остальные — вхождения в слова сегмента без учёта порядка: `clearml-task --project mnist`
    ловит и `clearml-task --name x --project mnist`."""
    words = (word, *args)
    for head, *rest in pats:
        key, eq, value = head.partition("=")
        if (env.get(key) == value if eq else word == head) and all(any(r in w for w in words) for r in rest):
            return True
    return False


def script(args, scripts, cwd):
    """Что исполнит оболочка: строка `-c`, файл, записанный той же командой (`cat > f <<EOF`),
    или файл с диска — первые SCRIPT_LIMIT символов."""
    for i, a in enumerate(args):
        if re.fullmatch(r"-[a-z]*c[a-z]*", a):
            return args[i + 1] if i + 1 < len(args) else None
    path = next((a.lstrip("<") for a in args if not a.startswith(("-", "<<")) and a.lstrip("<")), None)
    if not path:
        return None
    if os.path.basename(path) in scripts:
        return scripts[os.path.basename(path)]
    p = Path(cwd, os.path.expanduser(path))
    if not p.is_file():
        return None
    with open(p, encoding="utf-8", errors="replace") as f:
        return f.read(SCRIPT_LIMIT)


def hit(command, pats, cwd, depth=0):
    """Текст первого прод-сегмента команды или None."""
    main, docs = split_heredocs(command.replace("\\\n", " "))
    scripts = {os.path.basename(f): body for word, f, body in docs if word in ("cat", "tee") and f}
    exported = {}
    for word, args, env, text in segments(main):
        if word == "export":
            exported.update(a.split("=", 1) for a in args if "=" in a)
            continue
        ps = PS_ENV.match(word)
        if ps:  # PowerShell: `$env:DOCKER_CONTEXT = "prod"`
            exported[ps[1].upper()] = ps[2] if ps[2] is not None else ("".join(args[1:2]) if args[:1] == ["="] else "")
            continue
        env = {**exported, **env}
        if base(word, args, env) or declared(word, args, env, pats):
            return text
        body = word in SHELLS and depth < DEPTH and script(args, scripts, cwd)
        inner = body and hit(body, pats, cwd, depth + 1)
        if inner:
            return f"{text} → {inner}"
    for word, _, body in docs:
        inner = word in SHELLS and depth < DEPTH and hit(body, pats, cwd, depth + 1)
        if inner:
            return inner
    return None


def refusal(payload, lang):
    """Причина отказа или None. Роль и `agent_id` уже проверил `roadmap_watch.py`."""
    cwd = Path(payload["cwd"])
    found = hit(payload["tool_input"].get("command", ""),
                patterns(os.environ.get("CLAUDE_PROJECT_DIR") or cwd), cwd)
    if not found:
        return None
    return REFUSAL[lang].format(c=found if len(found) <= 120 else found[:119] + "…")
