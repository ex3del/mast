## Project structure

Documents are opened **as needed**, not all at once. Every truth has one owner — this table;
once a fact moves, every reference to it is fixed in the same commit. A system that says two
different things about itself cannot see its own contradiction.

| Document | When it appears | What's inside |
|---|---|---|
| `CLAUDE.md` | right away | stack, commands, project invariants. Target — under 200 lines |
| `ROADMAP.md` | right away | sections lettered (A, B, C…), items numbered within a section: `A-1`, `B-3`. A flat list. Holds only what's open: `planned`, `🔨 in progress`. Closed and dropped items move to `docs/roadmap/DONE.md` — `done` and `dropped` don't linger in the file (tolerated on old items until archived). A new item's number is the next free one across both files (check with grep), assigned by the main copy; a number from the archive is taken forever, closed items are never reopened. An in-progress item carries its worktree's name, dependencies go in a `Depends on: A-3` field. Only the main copy edits it (see skill `mast:worktree-flow`) |
| `docs/roadmap/DONE.md` | at the first closed or dropped item | closed items, 2 lines each: what changed with a number, date, commit range, links to `done/<item>/STATUS.md` and an ADR if they exist. Dropped items go in a "Dropped" subsection, one line each with the reason. The first layer for "has this been done already?" and "has this been tried and rejected?" |
| `TECH_DEBT.md` | at the first debt | what's off, what it risks, **the condition that triggers a fix** — this trigger condition ("bill > $5") is what separates debt from a roadmap item with its "Done when". A link to the item is required: where the debt was found, and on closing, which item closed it; a closed debt collapses to one line, the prose goes away. A class of error being fixed for the second time is debt too: what the class is, what it risks, the trigger "it happens once more", and which guard closes it |
| `docs/roadmap/<A-1>/STATUS.md` | only given one of these signs: it needs a plan with several tasks; the work will survive a restart or `/compact`; a neighboring item is running on nearby paths. Otherwise — a line in `ROADMAP.md` and commits | driven by skill `mast:managing-roadmap-items`; the item itself is done in its own worktree (see skill `mast:worktree-flow`). On closing it moves to `docs/roadmap/done/<A-1>/` along with the criterion and measurements |
| `docs/roadmap/inbox/` | at the first finding from a worktree, when there's no dispatcher | the finding as a file before triage, no number yet; the dispatcher sorts it out |
| `.claude/rules/*.md` | once an agreement about a specific folder appears | see "Where to write things" in the method core |

Reference material — architecture, DB schemas, workflow cards — goes in `docs/`, **not in `CLAUDE.md`**. `CLAUDE.md` loads in full every session, `docs/` is read by link only when needed.
