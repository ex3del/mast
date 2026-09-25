#!/usr/bin/env python3
"""Замер прод-операций по транскриптам Claude Code — ресёрч 2026-09-25-prod-ops.

Только чтение, только stdlib. Единица замера — вызов Bash, в котором исполняется хотя бы одна
прод-команда (маркер в позиции команды, не в grep/echo/тексте коммита; скрипт из файла,
записанного раньше в той же сессии, раскрывается).

    python3 measure.py                              # профиль reinhold
    python3 measure.py --profile fine-tune-LLM --hosts gpu-box
    python3 measure.py --samples 5                  # случайные примеры на класс — для ручной сверки
"""
import argparse
import collections
import glob
import json
import os
import random
import re
import statistics
from datetime import datetime, timedelta

PROFILES = {
    'reinhold': dict(
        glob='*-Documents-reinhold*', hosts={'reinhold-vps'}, contexts={'reinhold-vps'},
        # до переезда (D-4, `docker stop agent-hermes` на Mac) боевой стек жил в docker на Mac
        local_prod_until='2026-09-16T07:16:00Z',
        since='2026-09-14T19:24:00Z',  # первый вызов будущего диспетчера: «купил впс»
        urls=r'api\.telegram\.org|GRAFANA_DOMAIN|vps-provider-host|203\.0\.113\.10|domain\.txt|localhost:1(?:3000|5678)',
        local_urls=r'(?:localhost|127\.0\.0\.1):(?:3000|5678)\b',
        resource=r'(?<![/\w.-])agent-[a-z0-9]+(?:-[a-z0-9]+)*',
        # раннеры scripts/*-test-runner.py без HERMES_CONTAINER ходят в тестовый контейнер
        runner=(r'-test-runner\.py', 'agent-hermes-test'),
    ),
    'fine-tune-LLM': dict(
        glob='*-Documents-fine-tune-LLM*', hosts=set(), contexts=set(), local_prod_until=None,
        since='', urls=r'$^', local_urls=r'$^', resource=r'(?<![\w-])s3://[\w.-]+|lakefs://[\w.-]+', runner=None,
    ),
}
CLASSES = ['выкладка', 'рестарт/управление', 'данные: запись', 'прогон/эксперимент', 'чтение состояния']
MUTATING = set(CLASSES[:3])
LAUNCH = re.compile(r'\bclaude\b(?![^\n]*--help)[^\n|]*--bg')  # запуск сессии пункта
NOT_HOSTS = {'github.com', 'localhost', '127.0.0.1', 'QQ'}

# --- разбор shell ---------------------------------------------------------------------------
HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_]\w*)\1")
QUOTE = re.compile(r"'[^']*'|\"(?:\\.|[^\"\\])*\"")
SEP = re.compile(r"\n|;|&&|\|\||\||\$\(|`|\(|\)|\{|\}|\b(?:then|do|else|elif)\b")
WRAP = {'time', 'timeout', 'env', 'nohup', 'sudo', 'command', 'exec', 'xargs', 'nice', 'watch', '!'}
SSH_ARG = set('bcDEeFIiJLlmOopQRSWw')


def commands(text):
    """(слово команды, аргументы, env сегмента) по сегментам текста с замаскированными кавычками."""
    for seg in SEP.split(QUOTE.sub('QQ', text)):
        toks, env = seg.split(), {}
        while toks and (re.match(r'[A-Za-z_]\w*=', toks[0]) or toks[0] in WRAP or toks[0].isdigit()):
            if '=' in toks[0]:
                k, _, v = toks[0].partition('=')
                env[k] = v
            toks.pop(0)
        if toks:
            yield toks[0], toks[1:], env


def split_heredocs(cmd):
    """Текст без тел heredoc и список (потребитель, файл, тело)."""
    lines, out, docs, i = cmd.split('\n'), [], [], 0
    while i < len(lines):
        ln = lines[i]
        out.append(ln)
        i += 1
        for m in HEREDOC.finditer(ln):
            body = []
            while i < len(lines) and lines[i].strip() != m.group(2):
                body.append(lines[i])
                i += 1
            i += 1
            head = SEP.split(QUOTE.sub('QQ', ln[:m.start()]))[-1]
            words = [w for w in head.split() if not re.match(r'[A-Za-z_]\w*=', w)]
            word = words[0] if words else ''
            f = re.search(r"(?:>>?|\btee\s+(?:-a\s+)?)\s*[\"']?([^\s\"'<>;|&]+)", head)
            if word in ('cat', 'tee') and f:
                kind = 'file'
            elif word in ('bash', 'sh', 'zsh'):
                kind = 'shell'
            elif word in ('ssh', 'docker') or 'psql' in head:
                kind = 'remote'
            elif word in ('python', 'python3', 'node', 'sqlite3'):
                kind = 'other'
            else:
                kind = 'drop'  # сообщение коммита, текст для echo/gh
            docs.append((kind, f.group(1) if f else '', '\n'.join(body)))
    return '\n'.join(out), docs


def ssh_host(args):
    i = 0
    while i < len(args):
        a = args[i]
        if a.startswith('-') and len(a) > 1:
            if 'G' in a[1:] and not a.startswith('-o'):
                return None  # ssh -G — чтение локального конфига
            i += 2 if (len(a) == 2 and a[1] in SSH_ARG) else 1
            continue
        return a.split('@')[-1]
    return None


class Detector:
    def __init__(self, p, extra_hosts):
        self.hosts = set(p['hosts']) | set(extra_hosts)
        self.contexts = p['contexts']
        self.until = p['local_prod_until']
        self.urls = re.compile(p['urls'])
        self.local_urls = re.compile(p['local_urls'])

    def targets(self, text, ts, genv):
        """Цели исполняемого shell-текста: хост, `mac-прод`, `mac-локально`, s3, clearml…"""
        out = set()
        local_prod = bool(self.until) and ts < self.until
        for word, args, env in commands(text):
            if word == 'export':
                genv.update(a.split('=', 1) for a in args if '=' in a)
            elif word == 'ssh':
                h = ssh_host(args)
                if h and (h in self.hosts or (not self.hosts and h not in NOT_HOSTS)):
                    out.add(h)
            elif word in ('scp', 'rsync'):
                out |= {a.split(':')[0].split('@')[-1] for a in args if re.match(r'[\w.@-]+:', a)
                        and a.split(':')[0].split('@')[-1] in (self.hosts or {a.split(':')[0]})}
            elif word == 'docker':
                ctx = env.get('DOCKER_CONTEXT') or genv.get('DOCKER_CONTEXT')
                if args[:2] == ['context', 'use']:
                    out.add('docker context use')
                if args[:1] == ['context'] or (args[:1] == ['compose'] and 'config' in args):
                    continue  # локальный конфиг, стек не трогает
                for j, a in enumerate(args):
                    if not a.startswith('-'):
                        break
                    if a in ('--context', '-c') and j + 1 < len(args):
                        ctx = args[j + 1]
                    elif a.startswith('--context='):
                        ctx = a.split('=', 1)[1]
                out.add(ctx if ctx in self.contexts else ('mac-прод' if local_prod else 'mac-локально'))
            elif (env.get('DOCKER_CONTEXT') or genv.get('DOCKER_CONTEXT')) in self.contexts:
                out.add(env.get('DOCKER_CONTEXT') or genv['DOCKER_CONTEXT'])  # раннер, внутри которого docker exec
            elif word in ('curl', 'wget'):
                out.add('http')  # уточняется по URL ниже
            elif (word == 'aws' and args[:1] in (['s3'], ['s3api'])) or word in ('rclone', 's5cmd') \
                    or (word == 'mc' and args[:1] and args[0] in 'cp ls mirror rm mv cat stat du find tree head'.split()) \
                    or (word == 'dvc' and args[:1] and args[0] in ('push', 'pull', 'fetch')):
                out.add('s3')
            elif word == 'lakectl':
                out.add('lakefs')
            elif word.startswith('clearml'):
                out.add('clearml')
            elif word in ('kubectl', 'helm'):
                out.add('k8s')
        return out

    def url_target(self, text, ts):
        if self.urls.search(text):
            return 'http-прод'
        if self.local_urls.search(text):
            return 'mac-прод' if (self.until and ts < self.until) else None
        return None


def analyze(cmd, ts, det, scripts):
    """(цели, текст для классификации, через файл?) для одного вызова Bash."""
    main, docs = split_heredocs(cmd)
    genv, cls_text = {}, [main]
    tg = det.targets(main, ts, genv)
    for kind, fname, body in docs:
        if kind == 'file':
            scripts[os.path.basename(fname)] = body
        elif kind == 'shell':
            tg |= det.targets(body, ts, genv)
            cls_text.append(body)
        elif kind in ('remote', 'other'):
            cls_text.append(body)
    via_file = False
    for name, body in scripts.items():
        if name and re.search(r'(?:\b(?:bash|sh|zsh|source|\.)\s+\S*|<\s*\S*|\./)' + re.escape(name) + r'\b', main):
            t = det.targets(split_heredocs(body)[0], ts, dict(genv))
            if t - tg - {'mac-локально', 'http'}:
                via_file = True
            tg |= t
            cls_text.append(body)
    text = '\n'.join(cls_text)
    if 'http' in tg:
        tg.discard('http')
        u = det.url_target(text, ts)
        if u:
            tg.add(u)
    return tg, text, via_file


# --- классы действий --------------------------------------------------------------------------
D = r'\bdocker\s+(?:--context[= ]\S+\s+|-c\s+\S+\s+)?'
RULES = [
    ('выкладка', re.compile(
        r'(?:/opt/\S+|git\s+-C\s+/opt/\S+)[^\n]*?\bgit\b[^\n]*?\b(?:pull|reset\s+--hard|checkout|merge|clone)\b'
        r'|git\s+-C\s+/opt/\S+\s+(?:pull|reset|checkout|merge)'
        r'|\bcompose\b[^\n]*?\s(?:build|up)\b|' + D + r'(?:build|load)\b|\bbuildx\s+build'
        r'|\bn8n\s+(?:import|publish|update):|' + D + r'exec[^\n]*\bsed\s+-i'
        r'|\bscp\b[^\n]*\s[\w.@-]+:\S*\s*$|\brsync\b[^\n]*\s[\w.@-]+:\S*\s*$', re.M)),
    ('рестарт/управление', re.compile(
        D + r'(?:restart|stop|start|update|pause|unpause)\b|' + D + r'(?:rm|kill|rmi)\b[^\n]*\bagent-'
        r'|\bcompose\b[^\n]*?\s(?:restart|stop|start|down|rm|kill)\b'
        r'|\bsystemctl\s+(?:restart|stop|start|enable|disable|daemon-reload|reboot)|\breboot\b'
        r'|\b(?:builder|system|image|container|volume)\s+prune|\bufw\s+(?:allow|deny|delete|enable|reload)'
        r'|\bapt(?:-get)?\s+(?:-\S+\s+)*(?:install|upgrade|full-upgrade|remove)'
        r'|\bhermes\s+(?:cron\s+(?:create|add|remove|rm|delete|pause|resume|edit|update)'
        r'|plugins\s+(?:install|enable|disable|remove)|config\s+set)|\bcrontab\s+(?!-l)'
        r'|\bchown\b|(?:>|tee\s+)\s*/(?:opt|etc)/', re.M)),
    ('данные: запись', re.compile(
        r'(?i)(?:psql|\.sql)[\s\S]*\b(?:insert\s+into|update\s+[\w."]+\s+set|delete\s+from'
        r'|alter\s+(?:table|role|schema|default|function|policy)|create\s+(?:table|role|schema|index|unique|function'
        r'|or\s+replace|policy|view|extension|trigger|user)|drop\s+(?:table|role|schema|index|function|policy|view'
        r'|trigger|user|owned)|grant\s|revoke\s|truncate\s)'
        r'|(?:^|[;&|]\s*|\bbash\s+|\bsh\s+)(?:\./)?(?:\S*/)?(?:apply_migration|init-prod-db)\.sh|\bpg_restore\s+-'
        r'|\bcurl\b[^\n]*-X\s*(?:PUT|DELETE|PATCH)|sendMessage|\baws\s+s3\s+(?:cp|sync|mv|rm)|\bmc\s+(?:cp|mirror|rm|mv)|\brclone\s+(?:copy|sync|move|delete|purge)'
        r'|\blakectl\s+(?:commit|merge|branch\s+create|fs\s+(?:upload|rm)|import)|\bdvc\s+push', re.M)),
    ('прогон/эксперимент', re.compile(
        D + r'run\b|' + D + r'exec[^\n]*\b(?:pytest|health-test|hermes\s+chat)|\bcurl\b[^\n]*-X\s*POST|DOCKER_CONTEXT=\S+\s+(?:python3?|bash|sh)\s'
        r'|\bclearml-task\b|\bclearml-agent\s+execute|\btorchrun\b|\baccelerate\s+launch|python\S*\s[^\n]*\btrain')),
]


def resources(text, rx, runner):
    """Контейнеры/бакеты, названные в тексте; раннер без явного контейнера — его контейнер по умолчанию."""
    out = set(rx.findall(text))
    if runner and re.search(runner[0], text) and 'HERMES_CONTAINER=' not in text:
        out.add(runner[1])
    return out


def classify(text):
    for name, rx in RULES:
        if rx.search(text):
            return name
    return CLASSES[-1]


def hotpatch(text):
    """Правка живого контейнера мимо git: docker cp внутрь или sed -i через exec."""
    for m in re.finditer(D + r'cp\s+(\S+)\s+(\S+)', text):
        if ':' in m.group(2) and ':' not in m.group(1):
            return True
    return bool(re.search(D + r'exec[^\n]*\bsed\s+-i', text))


# --- транскрипты ------------------------------------------------------------------------------
def text_of(content):
    if isinstance(content, str):
        return content
    return '\n'.join(c.get('text', '') for c in content or [] if isinstance(c, dict))


def prompt_kind(r, text):
    """Кто разбудил ход: человек, другая сессия, уведомление о фоновой задаче."""
    k = (r.get('origin') or {}).get('kind')
    if k or r.get('isMeta'):
        return {'human': 'человек', 'peer': 'сессия', 'task-notification': 'уведомление'}.get(k)
    return None if text.startswith('<') or not text.strip() else 'человек'


def load(path):
    meta = dict(title='', cwd='', bg=0, calls=[], prompts=[])
    results, trigger = {}, 'старт'
    for line in open(path, encoding='utf-8', errors='replace'):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        t = r.get('type')
        if t == 'custom-title':
            meta['title'] = r.get('customTitle') or meta['title']
        elif t == 'agent-name' and not meta['title']:
            meta['title'] = r.get('agentName') or ''
        if r.get('cwd') and not meta['cwd']:
            meta['cwd'] = r['cwd']
        msg = r.get('message') or {}
        if t == 'user':
            body = msg.get('content')
            if isinstance(body, list) and not any(isinstance(c, dict) and c.get('type') == 'tool_result' for c in body):
                body = text_of(body)
            k = prompt_kind(r, body) if isinstance(body, str) else None
            if k:
                trigger = k
                meta['prompts'].append(dict(ts=r.get('timestamp', ''), kind=k, text=body))
        for c in msg.get('content') or [] if isinstance(msg.get('content'), list) else []:
            if not isinstance(c, dict):
                continue
            if c.get('type') == 'tool_use':
                inp = c.get('input') or {}
                meta['calls'].append(dict(ts=r.get('timestamp', ''), id=c.get('id'), name=c.get('name'), input=inp,
                                          trigger=trigger))
                if c.get('name') == 'Bash' and LAUNCH.search(inp.get('command', '')):
                    meta['bg'] += 1
            elif c.get('type') == 'tool_result':
                results[c.get('tool_use_id')] = (r.get('timestamp', ''), text_of(c.get('content')))
    for c in meta['calls']:
        c['rts'], c['out'] = results.get(c['id'], ('', ''))
    return meta


def role_of(meta):
    t = meta['title']
    if t.endswith('-dispatch'):
        return 'диспетчер'
    if '/.claude/worktrees/' in meta['cwd']:
        return 'пункт'
    if meta['bg'] >= 5:
        return 'диспетчер (без имени)'  # запускает сессии пунктов, имени ещё не было
    if re.search(r'arbiter|fixer', t):
        return 'контур мониторинга'
    return 'прочие'


def iso(s):
    return datetime.fromisoformat(s.replace('Z', '+00:00'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--projects', default=os.path.expanduser('~/.claude/projects'))
    ap.add_argument('--profile', default='reinhold', choices=PROFILES)
    ap.add_argument('--hosts', default='', help='доп. ssh-хосты прода через запятую')
    ap.add_argument('--since', default=None, help='ISO-время; пусто — весь корпус')
    ap.add_argument('--until', default='2026-09-25T00:00:00Z', help='верхняя граница: транскрипты живые, числа не плывут')
    ap.add_argument('--window', type=int, default=10, help='окно пересечения, минут')
    ap.add_argument('--samples', type=int, default=0)
    a = ap.parse_args()
    p = PROFILES[a.profile]
    since = p['since'] if a.since is None else a.since
    until = a.until or '9999'
    det = Detector(p, [h for h in a.hosts.split(',') if h])
    res_rx = re.compile(p['resource'])

    sessions = []
    for f in sorted(glob.glob(os.path.join(a.projects, p['glob'], '*.jsonl'))):
        m = load(f)
        m['id'], m['owner'], m['role'] = os.path.basename(f)[:8], os.path.basename(f)[:8], role_of(m)
        sessions.append(m)
        for s in sorted(glob.glob(os.path.join(f[:-6], 'subagents', '*.jsonl'))):
            sm = load(s)
            sm['id'], sm['owner'], sm['role'] = m['id'] + '/' + os.path.basename(s)[6:14], m['id'], m['role'] + ' · субагент'
            sessions.append(sm)
    print(f'# Профиль {a.profile}: {len(sessions)} транскриптов (с субагентами), окно {since or "начало"} — {until}\n')
    if not sessions:
        print('Транскриптов нет — замерять нечего.')
        return

    calls = []  # все вызовы инструментов в окне, с разметкой
    for s in sessions:
        scripts = {}
        for c in s['calls']:
            if c['name'] == 'Write':
                scripts[os.path.basename(c['input'].get('file_path', ''))] = c['input'].get('content', '')
            c.update(sess=s, prod=False)
            if not since <= c['ts'] < until:
                continue
            calls.append(c)
            if c['name'] != 'Bash':
                continue
            tg, text, via = analyze(c['input'].get('command', ''), c['ts'], det, scripts)
            c['targets'] = tg
            real = tg - {'mac-локально', 'docker context use'}
            if real:
                c.update(prod=True, cls=classify(text), via=via, hot=hotpatch(text),
                         res=resources(text, res_rx, p['runner']) or set(real), text=text)

    roles = sorted({s['role'] for s in sessions})
    bash = collections.Counter(c['sess']['role'] for c in calls if c['name'] == 'Bash')
    prod = [c for c in calls if c['prod']]

    print('## 1. Прод-вызовы по ролям (единица — вызов Bash)\n')
    print('| роль | сессий с прод | прод-вызовов | из всех Bash | ' + ' | '.join(CLASSES) + ' | мимо git | через файл |')
    print('|---' * (6 + len(CLASSES)) + '|')
    for r in roles:
        pc = [c for c in prod if c['sess']['role'] == r]
        if not bash[r]:
            continue
        k = collections.Counter(c['cls'] for c in pc)
        print(f"| {r} | {len({c['sess']['id'] for c in pc})} | {len(pc)} | {100 * len(pc) / bash[r]:.0f}% of {bash[r]} | "
              + ' | '.join(str(k[x]) for x in CLASSES)
              + f" | {sum(c['hot'] for c in pc)} | {sum(c['via'] for c in pc)} |")
    tgt = collections.Counter(t for c in prod for t in c['targets'] - {'mac-локально'})
    print(f"\nЦели (вызов может задеть несколько): {dict(tgt)}")
    loc = sum(1 for c in calls if c.get('targets') and c['targets'] == {'mac-локально'})
    print(f"Локальный docker после переезда (не прод, не считается): {loc} вызовов; "
          f"`docker context use`: {sum('docker context use' in c.get('targets', ()) for c in calls)}")

    print('\n## 2. Серии подряд (прод-вызовы без других инструментов между ними)\n')
    print('| роль | серий | медиана | p90 | максимум | серий ≥ 10 |\n|---|---|---|---|---|---|')
    runs = collections.defaultdict(list)
    for s in sessions:
        n = 0
        for c in [c for c in s['calls'] if since <= c['ts'] < until] + [dict(prod=False)]:
            if c['prod']:
                n += 1
            elif n:
                runs[s['role']].append(n)
                n = 0
    for r in roles:
        v = sorted(runs[r])
        if v:
            print(f"| {r} | {len(v)} | {statistics.median(v):g} | {v[int(0.9 * (len(v) - 1))]} | {v[-1]} | {sum(x >= 10 for x in v)} |")

    print('\n## 3. Время в прод-вызовах (от вызова до результата)\n')
    disp = [s['id'] for s in sessions if s['role'].startswith('диспетчер') and '/' not in s['id']]
    grp = lambda c, g: c['sess']['id'] == g if g in disp else c['sess']['role'] == g  # сессия диспетчера или роль
    for r in roles + disp:
        d = [(iso(c['rts']) - iso(c['ts'])).total_seconds() for c in prod if grp(c, r) and c['rts']]
        if d:
            tot = sum(len(c['out'] or '') for c in calls if grp(c, r))
            pb = sum(len(c['out'] or '') for c in prod if grp(c, r))
            print(f"- {r}: {sum(d) / 3600:.1f} ч, медиана {statistics.median(d):.0f} с, дольше 5 мин — {sum(x > 300 for x in d)}; "
                  f"вывод прод-вызовов в контексте — {pb // 1000} из {tot // 1000} КБ результатов ({100 * pb / max(tot, 1):.0f}%)")

    print(f"\n## 4. Пересечения на одном ресурсе разных сессий в окне {a.window} мин (субагент = его родитель)\n")
    W = timedelta(minutes=a.window)
    seq = sorted(prod, key=lambda c: c['ts'])
    ww, wu, hurt = [], collections.Counter(), []  # изменение × изменение; изменение × чтение/прогон
    down = re.compile(r'is restarting|No such container|is not running|Error response from daemon|Connection refused')
    for i, x in enumerate(seq):
        for y in seq[i + 1:]:
            if iso(y['ts']) - iso(x['ts']) > W:
                break
            if x['sess']['owner'] == y['sess']['owner'] or not x['res'] & y['res']:
                continue
            key = tuple(sorted((x['sess']['role'].split(' ·')[0], y['sess']['role'].split(' ·')[0])))
            if x['cls'] in MUTATING and y['cls'] in MUTATING:
                ww.append((x, y))
            elif x['cls'] in MUTATING or y['cls'] in MUTATING:
                wu[key] += 1
                if x['cls'] in ('выкладка', 'рестарт/управление') and down.search(y['out'] or ''):
                    hurt.append((x, y))
    print(f'Изменение × чтение/прогон другой сессии — пар вызовов по ролям: {dict(wu)}')
    print(f'… из них чтение/прогон упал с «контейнер недоступен» после чужой выкладки/рестарта: {len(hurt)}')
    for x, y in hurt:
        print(f"  - {x['ts'][:16]} {x['sess']['title'] or x['sess']['role']} ({x['cls']}) → {y['ts'][11:16]} "
              f"{y['sess']['title'] or y['sess']['role']}: {down.search(y['out']).group(0)}")
    ep = collections.defaultdict(list)  # эпизод = пара сессий + общий ресурс
    for x, y in ww:
        ep[(x['sess']['owner'], y['sess']['owner'], ','.join(sorted(x['res'] & y['res'])))].append((x, y))
    print(f'Изменение × изменение: пар вызовов {len(ww)}, эпизодов (пара сессий × ресурс) {len(ep)}; по ролям: '
          f"{dict(collections.Counter(tuple(sorted((l[0][0]['sess']['role'].split(' ·')[0], l[0][1]['sess']['role'].split(' ·')[0]))) for l in ep.values()))}\n")
    err = re.compile(r'409|[Cc]onflict|already in use|is restarting|No such container|is not running|Not possible to '
                     r'fast-forward|would be overwritten|diverged|[Ll]ock|unhealthy|Connection refused')
    for (sa, sb, res), lst in sorted(ep.items(), key=lambda e: e[1][0][0]['ts']):
        x, y = lst[0]
        hits = sorted({m.group(0) for c in (x, y) for m in [err.search(c['out'] or '')] if m})
        print(f"- {x['ts'][:16]}–{lst[-1][1]['ts'][11:16]} {x['sess']['id']} ({x['sess']['title'] or x['sess']['role']}, {x['cls']}) × "
              f"{y['sess']['id']} ({y['sess']['title'] or y['sess']['role']}, {y['cls']}) · {res} · пар {len(lst)} · ошибки: {hits or '—'}")

    print('\n## 5. Отставание прода и чужие правки на сервере\n')
    who = collections.defaultdict(collections.Counter)
    shown = []
    for c in prod:
        t, o, r = c['text'], c['out'] or '', c['sess']['role']
        if re.search(r'/opt/\S*[^\n]*\bgit\b[^\n]*\bpull\b|git\s+-C\s+/opt/\S+\s+pull', t):
            who['git pull на сервере'][r] += 1
            if re.search(r'\bgit\s+merge\b', c['input']['command'].split('ssh')[0]):
                who['… в одном вызове с вливанием ветки'][r] += 1
        if re.search(r'Not possible to fast-forward|have diverged|would be overwritten|Please commit your changes', o):
            who['отказ ff на сервере'][r] += 1
            shown.append(('ff', c))
        if 'hermes-image-manifest' in t and 'git log' in t:
            who['проверка «нужна ли пересборка»'][r] += 1
            if re.search(r'^[0-9a-f]{7,}\s', o, re.M):
                who['… образ отстаёт от master'][r] += 1
        if re.search(r'git\b[^\n]*\bstatus', t) and '/opt/' in t and re.search(r'^\s?[MADRU?]{1,2} \S', o, re.M):
            who['грязное дерево /opt на сервере'][r] += 1
            shown.append(('грязно', c))
        if re.search(r'compose\b[^\n]*\sbuild\b|' + D + r'build\b', t):
            who['сборка образа'][r] += 1
        if c['hot']:
            who['правка живого контейнера мимо git'][r] += 1
        if re.search(r'drift \[(?!\] \[\])', o):
            who['doctor: дрейф образа/промптов непуст'][r] += 1
    for k, v in who.items():
        print(f'- {k}: {dict(v)}')
    for k, c in shown:
        lines = [x for x in (c['out'] or '').split('\n') if re.match(r'\s?[MADRU?]{1,2} \S|.*(fast-forward|diverged|overwritten)', x)]
        print(f"  - {k} {c['sess']['id']} {c['ts'][:16]}: {lines[:4]}")

    print('\n## 6. Сверка с «268 вызовов docker/ssh» из ресёрча 23.09 (reinhold-dispatch 17–19.09)\n')
    for s in sessions:
        if s['title'].endswith('-dispatch') and '/' not in s['id']:
            b = [c for c in s['calls'] if c['name'] == 'Bash']
            cm = [c['input'].get('command', '') for c in b]
            sub = sum(bool(re.search(r'docker|ssh', x)) for x in cm)
            first = sum(bool(re.match(r'(?:[A-Z_]+=\S+\s+)*(docker|ssh)\b', x.strip())) for x in cm)
            print(f"- {s['id']}: Bash {len(b)}; подстрока docker|ssh — {sub}; первое слово docker|ssh — {first}; "
                  f"этот замер — {sum(c['prod'] for c in b)}")

    print('\n## 7. Имитация отказа по шаблону (пол 2 / пол 3)\n')
    naive = re.compile(r'\bssh\b|\bdocker\b|' + '|'.join(map(re.escape, det.hosts or {'$^'})))
    for r in roles + disp:
        b = [c for c in calls if grp(c, r) and c['name'] == 'Bash']
        if not b:
            continue
        nv = [c for c in b if naive.search(c['input'].get('command', ''))]
        print(f"- {r}: отказ по разбору команды — {sum(c['prod'] for c in b)} из {len(b)}; "
              f"наивная подстрока — {len(nv)}, из них не прод {sum(not c['prod'] for c in nv)}; "
              f"прод только через файл-скрипт — {sum(c['prod'] and c['via'] for c in b)}")
    items = [s for s in sessions if s['role'] == 'пункт']
    pi = {c['sess']['id'] for c in prod if c['sess']['role'] == 'пункт'}
    mi = collections.defaultdict(set)
    for c in prod:
        if c['sess']['role'] == 'пункт' and c['cls'] in MUTATING:
            mi[c['sess']['id']] |= c['res']
    print(f"- сессий пунктов: {len(items)}, с прод-вызовами {len(pi)}, с изменениями прода {len(mi)}; "
          f"ресурсов на изменяющую сессию: медиана {statistics.median([len(v) for v in mi.values()] or [0]):g}")
    print(f"- чаще всего изменяют: {collections.Counter(x for v in mi.values() for x in v).most_common(8)}")

    print('\n## 8. Что будит диспетчера перед прод-вызовом (последнее входящее перед вызовом)\n')
    for s in sessions:
        if s['role'] in ('диспетчер', 'диспетчер (без имени)'):
            bg = next((c['ts'] for c in s['calls'] if c['name'] == 'Bash'
                       and LAUNCH.search(c['input'].get('command', ''))), None)
            if bg:
                print(f"- {s['id']}: первый запуск сессии пункта {bg[:16]}; прод-вызовов до него "
                      f"{sum(c['ts'] < bg for c in prod if c['sess'] is s)}, после {sum(c['ts'] >= bg for c in prod if c['sess'] is s)}")
    for r in ('диспетчер', 'диспетчер (без имени)'):
        k = collections.Counter((c['trigger'], c['cls'] in MUTATING) for c in prod if c['sess']['role'] == r)
        print(f"- {r}: " + ', '.join(f"{t}: {k[(t, False)] + k[(t, True)]} (изменений {k[(t, True)]})"
                                     for t in ('человек', 'сессия', 'уведомление', 'старт') if k[(t, False)] + k[(t, True)]))

    print('\n## 9. Окна на общий ресурс: переписка и занятость\n')
    WIN = re.compile(r'(?i)окн[оау]? (?:тво|ваш|свобод|занят|освобо)|окн[оау]? на \S*(?:agent|контейнер|test|прод|vps)'
                     r'|контейнер\S* (?:тво|занят|свобод)|(?:свободен|освободил)[^.\n]{0,40}(?:контейнер|test|agent-)'
                     r'|не трога\S* [^.\n]{0,30}(?:agent-|контейнер|test)')
    DRIFT = re.compile(r'(?i)не доех|не доезжа|старше репозитория|отста[её]т от|пересоб|не задеплоен|не выкачан|доставк')
    for r in disp + ['пункт']:
        ss = [s for s in sessions if (s['id'] == r if r in disp else s['role'] == r)]
        inc = [p for s in ss for p in s['prompts'] if p['kind'] == 'сессия' and since <= p['ts'] < until]
        out = [c for s in ss for c in s['calls'] if c['name'] == 'SendMessage' and since <= c['ts'] < until]
        otext = [str(c['input'].get('message', '')) for c in out]
        print(f"- {r}: входящих от сессий {len(inc)}, про окно {sum(bool(WIN.search(p['text'])) for p in inc)}, "
              f"про доставку/пересборку {sum(bool(DRIFT.search(p['text'])) for p in inc)}; "
              f"исходящих {len(out)}, про окно {sum(bool(WIN.search(t)) for t in otext)}, "
              f"про доставку/пересборку {sum(bool(DRIFT.search(t)) for t in otext)}")
    use = collections.defaultdict(lambda: collections.defaultdict(list))  # ресурс → пункт → времена прогонов/изменений
    span = collections.defaultdict(list)                                     # пункт → времена всех вызовов
    for c in calls:
        s = c['sess']
        if s['role'] != 'пункт':
            continue
        span[s['title']].append(c['ts'])
        if c['prod'] and (c['cls'] in MUTATING or c['cls'] == 'прогон/эксперимент'):
            for x in c['res']:
                use[x][s['title']].append(c['ts'])

    def peak(iv):
        ev = sorted([(a, 1) for a, _ in iv] + [(b, -1) for _, b in iv])
        n = m = 0
        for _, d in ev:
            n += d
            m = max(m, n)
        return m

    print('\n| ресурс | пунктов изменяли/гоняли | одновременно «в работе» (замок на пункт) | одновременно в окне использования | '
          'часы в работе | часы окна использования |\n|---|---|---|---|---|---|')
    for x, per in sorted(use.items(), key=lambda e: -len(e[1])):
        if len(per) < 2:
            continue
        work = [(min(span[i]), max(span[i])) for i in per]
        win = [(min(v), max(v)) for v in per.values()]
        hrs = lambda iv: sum((iso(b) - iso(a)).total_seconds() for a, b in iv) / 3600
        print(f'| {x} | {len(per)} | {peak(work)} | {peak(win)} | {hrs(work):.1f} | {hrs(win):.1f} |')

    print('\n## 10. Выкладка диспетчером после вливания: жива ли ещё сессия пункта\n')
    last = collections.defaultdict(str)  # пункт → время последнего вызова любой его сессии
    for s in sessions:
        if s['role'] == 'пункт' and s['calls']:
            last[s['title']] = max(last[s['title']], s['calls'][-1]['ts'])
    for s in sessions:
        if s['role'] not in ('диспетчер', 'диспетчер (без имени)'):
            continue
        merged, k = None, collections.Counter()
        for c in s['calls']:
            cmd = c['input'].get('command', '') if c['name'] == 'Bash' else ''
            m = re.search(r'git merge --ff-only (?:-q )?worktree-([A-Z]+-\d+)', cmd)
            if m:
                merged = (m.group(1), c['ts'])
            if not (c['prod'] and c['cls'] in ('выкладка', 'данные: запись')):
                continue
            k['всего'] += 1
            if merged and iso(c['ts']) - iso(merged[1]) <= timedelta(minutes=60):
                k['в течение часа после вливания'] += 1
                k['… после неё у сессии пункта 0 вызовов' if last[merged[0]] < c['ts'] else '… сессия пункта работала и после'] += 1
        if k:
            print(f"- {s['id']} ({s['role']}): {dict(k)}")

    print('\n## 11. Отказы классификатора auto mode (площадка) по ролям\n')
    deny = collections.defaultdict(collections.Counter)
    for c in calls:
        m = re.search(r'denied by the Claude Code auto mode classifier\. Reason: (\[[^\]]+\]|[^.]+)', c.get('out') or '')
        if m:
            deny[c['sess']['role']][m.group(1)] += 1
    for r, v in deny.items():
        print(f'- {r}: {sum(v.values())} — {dict(v.most_common(6))}')

    if a.samples:
        rnd = random.Random(0)
        print('\n## Примеры для ручной сверки\n')
        for k in CLASSES:
            pool = [c for c in prod if c['cls'] == k]
            for c in rnd.sample(pool, min(a.samples, len(pool))):
                print(f"- [{k}] {c['sess']['id']} {c['ts'][:16]}: {c['input']['command'][:220]!r}")


if __name__ == '__main__':
    main()
