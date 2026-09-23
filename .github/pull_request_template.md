<!-- Writing in Russian is fine too. / Можно писать по-русски. -->

## What changed

## How I checked it

- [ ] `pytest` is green
- [ ] edited texts in `plugins/<lang>/locales/<lang>/`, hook code in `hooks/`, then ran `python3 tools/sync_plugins.py`
- [ ] changed both languages, or said below which one needs a translation
- [ ] bumped the version in both `plugin.json` files (only if `hooks/` or `plugins/` changed)
- [ ] left `ROADMAP.md`, `DONE.md`, and `TECH_DEBT.md` untouched
