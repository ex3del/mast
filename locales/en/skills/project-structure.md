## Project structure

Documents are opened **as needed**, not all at once:

| Document | When it appears | What's inside |
|---|---|---|
| `CLAUDE.md` | right away | stack, commands, project invariants. Target — under 200 lines |
| `ROADMAP.md` | right away | sections lettered (A, B, C…), items numbered within a section: `A-1`, `B-3`. A flat list. Holds only what's open: `planned`, `🔨 in progress`, `dropped`; closed items move to `docs/roadmap/DONE.md` (old `done` entries are tolerated until archived). A new item's number is the next free one across both files (check with grep), assigned by the main copy; a number from the archive is taken forever, closed items are never reopened. An in-progress item carries its worktree's name, dependencies go in a `Depends on: A-3` field. Only the main copy edits it (see skill `mast:worktree-flow`) |
| `docs/roadmap/DONE.md` | at the first closed item | closed items, 2 lines each: what changed with a number, date, commit range, links to `done/<item>/STATUS.md` and an ADR if they exist. The first layer for "has this been done already?" |
| `TECH_DEBT.md` | at the first debt | what's off, what it risks, **the condition that triggers a fix** — this trigger condition ("bill > $5") is what separates debt from a roadmap item with its "Done when". A link to the item is required: where the debt was found, and on closing, which item closed it; a closed debt collapses to one line, the prose goes away |
| `docs/roadmap/<A-1>/STATUS.md` | only given one of these signs: it needs a plan with several tasks; the work will survive a restart or `/compact`; a neighboring item is running on nearby paths. Otherwise — a line in `ROADMAP.md` and commits | driven by skill `mast:managing-roadmap-items`; the item itself is done in its own worktree (see skill `mast:worktree-flow`). On closing it moves to `docs/roadmap/done/<A-1>/` along with the criterion and measurements |
| `docs/roadmap/inbox/` | at the first finding from a worktree, when there's no dispatcher | the finding as a file before triage, no number yet; the dispatcher sorts it out |
| `.claude/rules/*.md` | once an agreement about a specific folder appears | see "Where to write things" |

Reference material — architecture, DB schemas, workflow cards — goes in `docs/`, **not in `CLAUDE.md`**. `CLAUDE.md` loads in full every session, `docs/` is read by link only when needed.
