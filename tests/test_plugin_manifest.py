"""Два плагина из одного репозитория: `mast` (английский) и `mast-ru`.

Язык — это выбор плагина при установке, а не настройка внутри одного: так у
пользователя три скилла и одна команда, а не шесть и две.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGINS = {"en": ROOT / "plugins" / "en", "ru": ROOT / "plugins" / "ru"}
NAMES = {"en": "mast", "ru": "mast-ru"}


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


def test_у_каждого_плагина_свой_mcp_и_ничего_лишнего():
    """В подкаталоге плагина — только обёртка: манифест, хуки, скиллы, команда, MCP.
    Код и тексты общие и лежат в корне, иначе они разъедутся между языками."""
    for lang, root in PLUGINS.items():
        files = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
        assert ".mcp.json" in files
        assert "hooks/hooks.json" in files
        assert "commands/init-project.md" in files
        assert not [f for f in files if f.endswith(".py")], f"{lang}: код должен быть общим"
        assert not [f for f in files if f.startswith("locales/")], f"{lang}: тексты должны быть общими"
