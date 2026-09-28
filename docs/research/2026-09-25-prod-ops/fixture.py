#!/usr/bin/env python3
"""Фикстура хука прод-команд (A-26): Bash-вызовы диспетчера `83cd81f4` с меткой прод/не прод.

Метку ставит `measure.py` этого ресёрча, тем же профилем reinhold и окном. Файл остаётся у того,
кто его выгрузил (`tests/fixtures/.gitignore`): хосты, адреса и контейнеры чужого проекта в
публичный репозиторий не кладутся, тест без файла пропускается. Текст всё равно чистится:
секреты и адреса почты — заглушками, тела heredoc, которые не исполняет оболочка (SQL, Python,
текст для `ssh … <<`), — одной строкой. После чистки метка каждого вызова пересчитывается и
обязана совпасть с исходной — иначе чистка поменяла замер.

    python3 fixture.py [--projects ~/.claude/projects] [--out tests/fixtures/dispatch-83cd81f4.jsonl]

Строка вывода: {"prod": bool, "command": str, "files": {имя: текст}} — `files` это скрипты,
записанные раньше в той же сессии, на которые команда ссылается (`bash x.sh`).
"""
import argparse
import collections
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import measure  # noqa: E402

SESSION = '83cd81f4'
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
SECRETS = [
    ('tg_token', re.compile(r'(?<!\d)\d{6,12}:[A-Za-z0-9_-]{30,}'), '<TG_TOKEN>'),
    ('dsn_password', re.compile(r'(\w+://[^:/\s@]+:)[^@\s/]+@'), r'\1<PASSWORD>@'),
    ('assigned', re.compile(r'(?i)((?:password|passwd|secret|token|api_?key)\w*\s*[=:]\s*["\']?)[A-Za-z0-9_\-./+=]{6,}'),
     r'\1<SECRET>'),
    ('bearer', re.compile(r'(?i)(bearer\s+)[A-Za-z0-9._\-]{8,}'), r'\1<TOKEN>'),
    ('chat_id', re.compile(r'(?i)(chat_id["\']?\s*[=:]\s*["\']?)-?\d{5,}'), r'\1<CHAT_ID>'),
    ('email', re.compile(r'\b[\w.+-]+@(?!github\.com\b)[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}\b'), '<EMAIL>'),
    ('long_random', re.compile(r'\b(?=[A-Za-z_-]*\d)(?=[\d_-]*[A-Za-z])[A-Za-z0-9_-]{32,}\b'), '<RANDOM>'),
]
KEEP = {'file', 'shell'}  # тела, которые исполнит оболочка: их разбирает и замер, и хук


def drop_bodies(cmd):
    """Тела heredoc, не исполняемые оболочкой, — одной строкой; разметка вида — как в `measure.split_heredocs`."""
    lines, out, i = cmd.split('\n'), [], 0
    kinds = iter(kind for kind, _, _ in measure.split_heredocs(cmd)[1])
    while i < len(lines):
        ln = lines[i]
        out.append(ln)
        i += 1
        for m in measure.HEREDOC.finditer(ln):
            kind = next(kinds)
            start = i
            while i < len(lines) and lines[i].strip() != m.group(2):
                i += 1
            out += lines[start:i] if kind in KEEP or kind == 'drop' else ['…']
            if i < len(lines):
                out.append(lines[i])
            i += 1
    return '\n'.join(out)


def clean(text, hits):
    text = drop_bodies(text)
    for name, rx, repl in SECRETS:
        text, n = rx.subn(repl, text)
        hits[name] += n
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--projects', default=os.path.expanduser('~/.claude/projects'))
    ap.add_argument('--out', default=os.path.join(ROOT, 'tests', 'fixtures', f'dispatch-{SESSION}.jsonl'))
    a = ap.parse_args()
    p = measure.PROFILES['reinhold']
    paths = glob.glob(os.path.join(a.projects, p['glob'], f'{SESSION}*.jsonl'))
    if len(paths) != 1:
        sys.exit(f'транскрипт {SESSION}: найдено {len(paths)}, нужен один')
    det, until = measure.Detector(p, []), '2026-09-25T00:00:00Z'
    scripts, rows, hits, changed = {}, [], collections.Counter(), []
    for c in measure.load(paths[0])['calls']:
        if c['name'] == 'Write':
            scripts[os.path.basename(c['input'].get('file_path', ''))] = c['input'].get('content', '')
        if c['name'] != 'Bash' or not p['since'] <= c['ts'] < until:
            continue
        cmd = c['input'].get('command', '')
        main_text = measure.split_heredocs(cmd)[0]
        before = dict(scripts)
        tg = measure.analyze(cmd, c['ts'], det, scripts)[0]
        prod = bool(tg - {'mac-локально', 'docker context use'})
        files = {n: b for n, b in before.items() if n and re.search(
            r'(?:\b(?:bash|sh|zsh|source|\.)\s+\S*|<\s*\S*|\./)' + re.escape(n) + r'\b', main_text)}
        row = dict(prod=prod, command=clean(cmd, hits), files={n: clean(b, hits) for n, b in files.items()})
        again = measure.analyze(row['command'], c['ts'], det, dict(row['files']))[0]
        if bool(again - {'mac-локально', 'docker context use'}) != prod:
            changed.append(len(rows))
        rows.append(row)
    if changed:
        sys.exit(f'чистка поменяла метку у вызовов {changed[:20]} — фикстура не записана')
    with open(a.out, 'w', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')
    n = sum(r['prod'] for r in rows)
    print(f'{a.out}: Bash {len(rows)}, прод {n}, не прод {len(rows) - n}, через файл '
          f'{sum(bool(r["files"]) for r in rows)}; заменено: {dict(hits)}')


if __name__ == '__main__':
    main()
