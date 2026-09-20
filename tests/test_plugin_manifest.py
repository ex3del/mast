import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(name):
    return json.loads((ROOT / ".claude-plugin" / name).read_text(encoding="utf-8"))


def test_манифест_плагина_объявляет_имя_версию_и_язык():
    m = load("plugin.json")
    assert m["name"] == "mast"
    assert m["version"].count(".") == 2          # семвер
    lang = m["userConfig"]["language"]
    assert lang["type"] == "string"
    assert lang["options"] == ["ru", "en"]
    assert lang["default"] == "ru"
    assert lang["title"]
    assert lang["description"]


def test_маркетплейс_ссылается_на_этот_же_репозиторий():
    m = load("marketplace.json")
    assert m["name"] == "ex3del"
    assert m["owner"]["name"]
    entry = next(p for p in m["plugins"] if p["name"] == "mast")
    assert entry["source"] == "./"
    assert entry["description"] and entry["license"]
