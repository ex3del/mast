#!/usr/bin/env python3
"""Локальный git-маркетплейс для живой проверки установки без push.

Маркетплейс-каталог площадка грузит на месте, без кэша, — копирование в кэш, которое
получит пользователь с GitHub, проверяет только git-маркетплейс. `file://` и `git://`
площадка не принимает, dumb HTTP не умеет shallow-клон, поэтому репозиторий отдаётся
по smart HTTP: запрос уходит в `git http-backend` по правилам CGI.

  serve_marketplace.py [--name mast-local] [--port N] — собрать bare-репозиторий из
      текущего дерева (`plugins/` и манифест маркетплейса с новым именем), отдавать
      его на 127.0.0.1 до Ctrl+C и напечатать команды для проверки
  serve_marketplace.py snapshot <каталог> — снять копии общих файлов ~/.claude
  serve_marketplace.py compare <каталог>  — код 1 и дифф, если файлы разошлись со снимком
"""
import argparse
import difflib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = Path(".claude-plugin/marketplace.json")
SKIP = (".DS_Store", "__pycache__", "*.pyc")


def watched():
    """Общие файлы ~/.claude, которые установка `--scope local` менять не должна."""
    home = Path.home() / ".claude"
    return [home / "settings.json", home / "plugins/known_marketplaces.json",
            home / "plugins/installed_plugins.json"]


def build(src, name, dest):
    """Bare-репозиторий `<name>.git` в dest из текущего дерева src, а не из HEAD —
    так проверяется и незакоммиченное."""
    work = dest / "work"
    shutil.copytree(src / "plugins", work / "plugins", ignore=shutil.ignore_patterns(*SKIP))
    manifest = json.loads((src / MANIFEST).read_text(encoding="utf-8"))
    manifest["name"] = name
    (work / MANIFEST).parent.mkdir()
    (work / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8")
    git = ["git", "-C", str(work), "-c", "user.name=mast", "-c", "user.email=mast@localhost"]
    for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "локальный маркетплейс"]):
        subprocess.run(git + args, check=True)
    repo = dest / f"{name}.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(work), str(repo)], check=True)
    shutil.rmtree(work)
    return repo


class GitHandler(BaseHTTPRequestHandler):
    """Передаёт запрос в `git http-backend` по правилам CGI и возвращает его ответ."""

    def do_GET(self):
        path, _, query = self.path.partition("?")
        length = self.headers.get("Content-Length", "0")
        env = dict(os.environ, GIT_PROJECT_ROOT=self.server.git_root, GIT_HTTP_EXPORT_ALL="1",
                   PATH_INFO=path, QUERY_STRING=query, REQUEST_METHOD=self.command,
                   CONTENT_TYPE=self.headers.get("Content-Type", ""), CONTENT_LENGTH=length)
        # Заголовки клиента — как HTTP_*: так доходят Git-Protocol (протокол v2) и Content-Encoding
        env.update(("HTTP_" + k.upper().replace("-", "_"), v) for k, v in self.headers.items())
        out = subprocess.run(["git", "http-backend"], input=self.rfile.read(int(length)),
                             env=env, stdout=subprocess.PIPE).stdout
        head, _, body = out.partition(b"\r\n\r\n")
        headers = dict(line.split(": ", 1) for line in head.decode().split("\r\n"))
        code, _, reason = headers.pop("Status", "200 OK").partition(" ")
        self.send_response(int(code), reason)
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()  # HTTP/1.0: конец тела — закрытие соединения
        self.wfile.write(body)

    do_POST = do_GET


def start(src, name, dest, port):
    """Собрать репозиторий и поднять сервер на 127.0.0.1; port 0 — свободный."""
    build(src, name, dest)
    server = ThreadingHTTPServer(("127.0.0.1", port), GitHandler)
    server.git_root = str(dest)
    return server


def snapshot(dest):
    dest.mkdir(parents=True, exist_ok=True)
    for live in watched():
        if live.is_file():
            shutil.copyfile(live, dest / live.name)
        else:  # файла нет — это тоже состояние
            (dest / live.name).unlink(missing_ok=True)
    print(f"Снимок: {dest}")
    return 0


def compare(dest):
    changed = 0
    for live in watched():
        old, new = ((p.read_bytes() if p.is_file() else None) for p in (dest / live.name, live))
        if old != new:
            changed += 1
            state = " — появился" if old is None else " — пропал" if new is None else ""
            print(f"≠ {live}{state}")
            # Площадка пишет JSON без перевода строки в конце — строки сравниваем без них
            old, new = ((b or b"").decode("utf-8").splitlines() for b in (old, new))
            print(*difflib.unified_diff(old, new, "снимок", "сейчас", lineterm=""), sep="\n")
    print(f"Отличий: {changed}")
    return 1 if changed else 0


def serve(name, port):
    manifest = json.loads((ROOT / MANIFEST).read_text(encoding="utf-8"))
    taken = manifest["name"]
    if name == taken:
        sys.exit(f"Имя {taken} занято маркетплейсом с GitHub: площадка спутает источники. "
                 "Возьми другое, --name mast-local.")
    me = f"python3 {Path(__file__).resolve()}"
    with tempfile.TemporaryDirectory(prefix="mast-marketplace-") as tmp:
        server = start(ROOT, name, Path(tmp), port)
        url = f"http://127.0.0.1:{server.server_address[1]}/{name}.git"
        plugins = [p["name"] for p in manifest["plugins"]]
        print(f"Маркетплейс {name} из {ROOT}: {url} — до Ctrl+C\n",
              "До установки — снимок общих файлов ~/.claude:",
              f"  {me} snapshot <каталог>",
              "Во временном проекте с ROADMAP.md — без него ядро не вкладывается:",
              f"  claude plugin marketplace add {url} --scope local",
              *(f"  claude plugin install {p}@{name} --scope local\n"
                f"  claude plugin disable {p}@{taken} --scope local   # если стоит с GitHub"
                for p in plugins),
              f"Плагин грузится из ~/.claude/plugins/cache/{name}/<плагин>/<версия>"
              " — installPath в installed_plugins.json.",
              "Уборка там же, затем Ctrl+C здесь и сверка со снимком:",
              # --prune: плагин тянет зависимость, её копия --scope local ставится с auto: true
              f"  claude plugin uninstall <плагин>@{name} --scope local --prune -y",
              f"  claude plugin marketplace remove {name}",
              f"  {me} compare <каталог>", sep="\n", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--name", default="mast-local", help="имя маркетплейса")
    parser.add_argument("--port", type=int, default=0, help="порт; по умолчанию свободный")
    sub = parser.add_subparsers(dest="cmd")
    for cmd in ("snapshot", "compare"):
        sub.add_parser(cmd).add_argument("dir", type=Path)
    args = parser.parse_args()
    if args.cmd == "snapshot":
        return snapshot(args.dir)
    if args.cmd == "compare":
        return compare(args.dir)
    return serve(args.name, args.port)


if __name__ == "__main__":
    sys.exit(main())
