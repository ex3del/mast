# Contributing to MAST

*По-русски: [CONTRIBUTING.ru.md](CONTRIBUTING.ru.md)*

Thanks for helping. Bugs and ideas go to [issues](https://github.com/ex3del/mast/issues),
code goes through a pull request into `main`. Writing in Russian is fine too.

## Setup

```bash
git clone https://github.com/<you>/mast && cd mast
git config core.hooksPath .githooks     # the pre-commit that guards the version bump
pytest                                  # the whole suite must be green
```

The live tests `tests/test_*_live.py` are skipped without `MAST_LIVE=1`: they call the real
`claude` and cost tokens.

To try your changes in Claude Code without publishing: `claude --plugin-dir plugins/en`
(or `plugins/ru`).

## Rules that aren't obvious

- **Texts live in their plugin — `plugins/<lang>/locales/<lang>/`; hook code at the root,
  in `hooks/`.** The marketplace installs only the plugin's own directory, so each plugin
  carries a copy of the shared `hooks/`. Edit hook code only in the root `hooks/`:
  `plugins/<lang>/hooks/*.py` are generated copies whose first line (after the shebang)
  reads «Сгенерировано… правь там» ("generated… edit there"). Refresh them with
  `python3 tools/sync_plugins.py`; `--check` in the pre-commit and CI rejects both a copy
  that falls behind and a copy without the marker.
- **Copies, not symlinks.** Each plugin is installed from its own directory, and both need
  the code. Git on Windows (`core.symlinks=false` by default) checks a symlink out as a plain
  text file — the hook dies with `SyntaxError` and the core never loads (0 of 2 in the A-18
  probe). Don't replace the copies with symlinks.
- **Change both languages together.** A text edit in `plugins/en/locales/en/` needs the same
  edit in `plugins/ru/locales/ru/`; the guards compare the file set and the heading tree. If
  you can't write one of the languages, say so in the PR — we'll finish the translation.
- **A change to the method bumps the version** in both `plugins/*/.claude-plugin/plugin.json`
  (they must stay equal). Without a bump Claude Code never delivers the update to anyone.
  Changes to `README`, `docs/`, or `tests/` alone need no bump.
- **The core has a ceiling** — `plugins/<lang>/locales/<lang>/core.md` stays under 8200
  characters; the English one is already close. Anything heavier belongs in a skill.
- **Don't edit `ROADMAP.md`, `docs/roadmap/DONE.md`, or `TECH_DEBT.md`.** In MAST only the
  main copy edits them — here that's the maintainer, at merge time. Put a finding or a
  proposal in an issue instead.
- **Fix with a test.** A bug fix comes with a test that fails before it and passes after.

## Pull requests

One PR — one change. Describe what changed and how you checked it; CI runs the tests, checks
the plugin copies and the version bump on every PR.
