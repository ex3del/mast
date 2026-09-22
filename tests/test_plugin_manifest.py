"""Два плагина из одного репозитория: `mast` (английский) и `mast-ru`.

Язык — это выбор плагина при установке, а не настройка внутри одного: так у
пользователя три скилла и одна команда, а не шесть и две.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGINS = {"en": ROOT / "plugins" / "en", "ru": ROOT / "plugins" / "ru"}
NAMES = {"en": "mast", "ru": "mast-ru"}
sys.path.insert(0, str(ROOT / "hooks"))
from plugin_names import PLUGIN  # noqa: E402

# Путь, который текст плагина обещает пользователю или модели
PLUGIN_ROOT_PATH = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}(/[^\s`)\"']*)")
# Ссылка на скилл (`mast-ru:worktree-flow`) или команду (`/mast:init-project`)
REFERENCE = re.compile(r"(/?)\b(mast(?:-ru)?):([a-z0-9-]+)")
READMES = {"en": "README.md", "ru": "README.ru.md"}


def manifest(lang):
    return json.loads((PLUGINS[lang] / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))


def marketplace():
    return json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))


def test_манифесты_обоих_плагинов_на_месте():
    for lang, name in NAMES.items():
        m = manifest(lang)
        assert m["name"] == name
        assert m["version"].count(".") == 2          # семвер
        assert m["description"] and m["license"]


def test_настройки_языка_больше_нет():
    """Настройка не подставляется в тело скилла и команды — язык выбирается плагином."""
    for lang in PLUGINS:
        assert "language" not in manifest(lang).get("userConfig", {})


def test_версии_двух_плагинов_не_разъехались():
    assert manifest("en")["version"] == manifest("ru")["version"]


def test_зависимость_от_superpowers_объявлена_и_разрешена():
    """Зависимость из чужого маркетплейса без allowlist отвергается при установке."""
    allowed = marketplace()["allowCrossMarketplaceDependenciesOn"]
    for lang in PLUGINS:
        dep = next(d for d in manifest(lang)["dependencies"]
                   if isinstance(d, dict) and d["name"] == "superpowers")
        assert dep["marketplace"] == "claude-plugins-official"
        assert dep["marketplace"] in allowed


def test_маркетплейс_отдаёт_оба_плагина_из_подкаталогов():
    m = marketplace()
    assert m["name"] == "ex3del" and m["owner"]["name"]
    entries = {p["name"]: p for p in m["plugins"]}
    assert set(entries) == set(NAMES.values())
    for lang, name in NAMES.items():
        assert entries[name]["source"] == f"./plugins/{lang}"
        assert entries[name]["description"] and entries[name]["license"]


def test_имена_плагинов_в_коде_хуков_совпадают_с_манифестами():
    """Хуки печатают пользователю ссылки на команду и скилл, а имя плагина в них —
    из `hooks/plugin_names.py`. Разъедется с манифестом — ссылка поведёт в никуда."""
    assert PLUGIN == {lang: manifest(lang)["name"] for lang in PLUGINS}


def test_пути_в_текстах_плагина_ведут_в_существующие_файлы():
    """Тексты скиллов и команд зовут линт и читают шаблоны по `${CLAUDE_PLUGIN_ROOT}`.
    Разводку хуков при переезде в подкаталог поправили, а тексты — нет: команды из
    скиллов полгода указывали в пустоту, и ни один сторож этого не видел."""
    for lang, plugin in PLUGINS.items():
        checked = 0
        for path in [*plugin.rglob("*.md"), *(ROOT / "locales" / lang).rglob("*.md")]:
            for m in PLUGIN_ROOT_PATH.finditer(path.read_text(encoding="utf-8")):
                rel = m.group(1).lstrip("/")
                if not rel:
                    continue
                target = plugin / rel
                hits = (list(target.parent.glob(target.name)) if "*" in target.name
                        else [target] if target.exists() else [])
                assert hits, f"{path.relative_to(ROOT)}: ${{CLAUDE_PLUGIN_ROOT}}/{rel} никуда не ведёт"
                checked += 1
        assert checked, f"{lang}: путей не нашлось — сторож смотрит не туда"


def test_ссылки_на_скиллы_и_команды_ведут_в_своего_плагина():
    """Каждое `mast…:<имя>` в текстах языка — имя плагина этого языка плюс скилл
    или команда, которые у него правда есть. Именно этот класс ошибок трижды
    доехал до пользователя: префикс от старой схемы вёл в никуда."""
    for lang, plugin in PLUGINS.items():
        skills = {p.parent.name for p in plugin.glob("skills/*/SKILL.md")}
        commands = {p.stem for p in plugin.glob("commands/*.md")}
        texts = [*plugin.rglob("*.md"), *(ROOT / "locales" / lang).rglob("*.md"),
                 ROOT / READMES[lang]]
        found = 0
        for path in texts:
            for slash, prefix, name in REFERENCE.findall(path.read_text(encoding="utf-8")):
                where = f"{path.relative_to(ROOT)}: {slash}{prefix}:{name}"
                assert prefix == NAMES[lang], f"{where} — чужой плагин, ждали {NAMES[lang]}"
                assert name in (commands if slash else skills), f"{where} — такого нет у плагина"
                found += 1
        assert found, f"{lang}: ссылок не нашлось — сторож смотрит не туда"


def test_плагин_самодостаточен():
    """Площадка копирует в кэш только содержимое каталога плагина — проверено живьём
    на установке из маркетплейса. Значит код и тексты обязаны лежать внутри него."""
    for lang, root in PLUGINS.items():
        files = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
        for required in (".mcp.json", "hooks/hooks.json", "hooks/core.py",
                         "hooks/roadmap_lint.py", "commands/init-project.md",
                         f"locales/{lang}/core.md"):
            assert required in files, f"{lang}: нет {required}"


def test_копии_в_плагинах_не_отстали_от_источника():
    """Истина одна — корневые `hooks/` и `locales/`; внутри плагина её копии,
    разложенные `tools/sync_plugins.py`. Отстали — релиз уедет с чужим текстом."""
    sys.path.insert(0, str(ROOT / "tools"))
    import sync_plugins  # noqa: PLC0415 — импорт здесь, чтобы тест не требовал tools/ в sys.path

    assert sync_plugins.check() == [], "разложить: python3 tools/sync_plugins.py"
