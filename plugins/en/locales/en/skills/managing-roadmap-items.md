# Roadmap items

**Core idea:** a decision not backed by a test, a number, or a CI check gets reverted by whoever didn't read the discussion. The skill keeps evidence at three points: the done criterion, the finding, the decision made.

This is a checklist, not a script for a reply: execute it, don't recount the reasoning.

## Who you are — what to read

| You are | What to read **next to this file**, right now |
|---|---|
| an item's session — in worktree `X-N` or marked `main copy` | all of `managing-roadmap-items-item.md` at the start; before closing, reread its "3. Closing" section |
| the main copy — the dispatcher `<project>-dispatch` or the human running the roadmap | `managing-roadmap-items-dispatcher.md`, and the parts of `…-item.md` it refers to |

Read the file for your role in full, and don't read the other one: an item's session doesn't merge branches and doesn't edit `ROADMAP.md` — it has no reason to carry the dispatcher's procedures.

This part is shared by both: invariants, the line format, the archive, decisions.

## Invariants

- Only **the main copy** edits `ROADMAP.md`, `docs/roadmap/DONE.md`, and `TECH_DEBT.md`. Everything meant for them travels from an item's branch as a message to the dispatcher.
- **The main copy assigns the item's number** — the next free one across `ROADMAP.md` and `DONE.md`. A number from the archive is taken forever.
- **An item's session in a worktree never pushes to `main`** — only its own branch.
- **"Done when" holds a checkable number** — time, volume, count, size, a memory ceiling. ❌ "the PDF renders correctly" ✅ "500 rows < 3s, file < 2 MB".
- **A message to the human — a question, a report, an escalation — is self-contained:** it's understood without knowing this item or its neighbors. It holds what happened, why it matters to the human, a concrete example, options with their consequences, a recommendation; an item number only with a phrase saying what the item is; a term or a file name only with why it's here. ❌ "waits on B-2" ✅ "waits on B-2, the data export the report is built from". There's no length limit; if the human has to ask back, the message failed.
- **`ROADMAP.md` is edited with Edit or Write, not `sed`:** after an edit, a hook runs `roadmap_lint.py` and reports violations introduced by that edit. It doesn't see an edit made through Bash.
- ⚠️ **Numbers and names in the skill's examples are made up.** Copied a number from an example — there was no measurement.

## The item's line

```markdown
- **B-4** Export reports to PDF — 🔨 in progress · `worktree-B-4` · session `B-4` · since 08.09
  Depends on: B-2
  My paths: reports/**, api/routes/export.py
  Done when: a 500-row report renders in < 3s, peak memory < 300 MB.
```

| Slot | When required | What |
|---|---|---|
| status | always | `planned` / `🔨 in progress`. `done` and `dropped` don't linger in the file: both closing and dropping move the item into `DONE.md` — a dropped one into the "Dropped" subsection, one line with the reason. Until the item is moved, `dropped` carries its reason right in the line — otherwise nobody remembers six months later why it was abandoned. Legal on old items until archived |
| where it's driven | in progress | `worktree-X-N` or `main copy`; not taken — `—` |
| session | in progress | the name from `--name`, used to reach it via `SendMessage`. Whether it's alive — `claude agents` shows it |
| date taken | in progress | an abandoned item shows by its age |
| `waiting on human` | if awaiting an answer | the last slot of the head: `· waiting on human: <question>`. Set and removed by the main copy; the list — `python3 ${CLAUDE_PLUGIN_ROOT}/hooks/roadmap_lint.py --waiting ROADMAP.md`, a slot without a question is a lint error |
| `Depends on` | if waiting | only the form `Depends on: B-2, A-3`: "blocks" or "waiting on" isn't seen by the check |
| `My paths` | in progress | what the item touches. It sets the bar for a new item and blocks running a neighbor in parallel |
| Done when | always | with a number. This line is the source of truth |

**Ready to take** — `planned`, and every dependency is **closed**: either `done`, or in `DONE.md` outside the "Dropped" subsection. A dependency that was dropped is not satisfied — the work was abandoned, so the item waits on a human decision rather than a start: `python3 ${CLAUDE_PLUGIN_ROOT}/hooks/roadmap_lint.py --ready ROADMAP.md`. `Depends on` isn't cleared once the dependency closes.

## Closed: four layers

| Layer | Where | What |
|---|---|---|
| theses | `docs/roadmap/DONE.md` | 2 lines per item, by section: what changed with a number, date, commit range, links down |
| how it was done | `docs/roadmap/done/X-N/STATUS.md` if it was opened; otherwise commit messages | the journal, the criterion with measurements verbatim, decisions |
| why it was done that way | `docs/adr/X-N-<topic>.md` | decisions that cleared the bar below |
| what changed | `git diff <range>` | the code |

Go down exactly as far as needed. Below is always the verbatim source — no paraphrasing layers.

## Decisions

| What was decided | Where |
|---|---|
| a choice whose reversal is plausible and costly: without context someone will want Y back, and that breaks something or costs days | ADR + `rules/` + guard, see below |
| an ordinary decision | "Decisions made" in `STATUS.md` or the commit message |
| left crooked on purpose | `TECH_DEBT.md`: what's off, what it risks, **the condition that triggers a fix**, a link to the item. A choice deferred with a return condition goes here, not into an ADR |

A decision that clears the bar lives in three places at once:

- **`docs/adr/<item>-<topic>.md`** — for the human. Named by item number, so it's unique and parallel sessions don't collide. Old `NNNN-*.md` files aren't renamed.
- **`.claude/rules/<subsystem>.md` with `paths:`** — for the agent. Named after the top folder from `paths:` (`reports/**` → `rules/reports.md`), not after the technology. Opened at the moment of the decision.
- **A guard** — a test or a CI step that fails on regression. `rules/` alone isn't enough: `paths:` doesn't fire on an edit from an unexpected folder.

A class is defined by the invariant, not by the incident. A guard that freezes the accidental shape of a failure — today's provider, config, or step order — is the same patch, only dressed as a structural fix.

## Common mistakes

| Mistake | What it leads to |
|---|---|
| A criterion without a number | acceptance turns into an argument |
| Someone other than the main copy assigned the number | two items share a number, `git log --grep` mixes them |
| A number from `DONE.md` was reused | the history of two items merges forever |
| An item's session edits `ROADMAP.md` on its own branch | a conflict on rebase |
| A dependency written as "blocks" or "waiting on" | the ready queue doesn't see it, the item is taken too early |
| A decision lives only in `STATUS.md` or only in `rules/` | the archive isn't read, `paths:` doesn't fire — the decision gets reverted |
| An ADR for every decision | the important ones drown among the routine ones |
| A commit hash was recorded before the merge | rebase changed it, the link is broken |
| One class of error is fixed a third time with prose — a rule in `rules/`, a line in a prompt, a checklist item | prose doesn't enforce itself; it needs a guard — a test, a hook, or a lint that fails on regression |
