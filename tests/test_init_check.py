import hashlib
from pathlib import Path

FIX = Path(__file__).resolve().parent / "fixtures" / "legacy"


def snapshot(root):
    return {p.relative_to(root): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def test_образец_содержит_все_случаи_ревизии():
    names = {p.name for p in FIX.rglob("*") if p.is_file()}
    assert {"CLAUDE.md", "TODO.md", "CHANGELOG.md"} <= names
    assert len((FIX / "CLAUDE.md").read_text(encoding="utf-8").splitlines()) > 200
    rule = next(FIX.glob(".claude/rules/*.md"))
    assert not rule.read_text(encoding="utf-8").startswith("---")      # правило без paths:


def test_снимок_образца_считается():
    """Тем же снимком проверяется вручную, что --check не изменил ни файла."""
    assert len(snapshot(FIX)) >= 5
