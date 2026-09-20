## Where to write things

Three different places, don't mix them up:

| Where | What goes there | When |
|---|---|---|
| `<project>/.claude/rules/<topic>.md` with `paths:` | conventions and rules for a **specific folder or subsystem** | "remember that in `db/` we always…"; a decision was made about a section of the project |
| auto-memory (`/memory`) | my preferences, your corrections, project context that can't be inferred from code | you decide on the fly |
| `CLAUDE.md` — global or project-level | rules needed in **every** session | only on an explicit request such as "add this to CLAUDE.md" |

**`paths:` is the main tool for saving context.** A file in `.claude/rules/` with frontmatter

```yaml
---
paths:
  - "db/**/*.{sql,md}"
---
```

sits quietly and only enters the context when those files are touched. Without `paths:` it loads every time, like CLAUDE.md.

When I say "remember this" and it's about a specific section, folder, or subsystem — **by default write it to `rules/` with `paths:`**, not to CLAUDE.md. One topic, one file, named after the topic: `db.md`, `n8n.md`, `telegram.md`. A rule like "check cacheHitRate after editing prompts" lives next to the prompts, not in the shared context.

## Planning

- Any feature costing more than one session → plan first, code second.
- Before `superpowers:writing-plans` — always the roadmap-item skill: first the item is opened in `ROADMAP.md` and `STATUS.md` is created, only then the plan gets filled with tasks. `brainstorming` calls `writing-plans` directly — this order overrides that.
- Plans and specs for superpowers skills are written **in our own paths**; we don't use their defaults (`docs/superpowers/plans/`, `docs/superpowers/specs/`): an item's plan goes to `docs/roadmap/<A-1>/STATUS.md`, its spec sits next to it in the same folder.
- Commits inside plans use our format `[A-1] description`, not the conventional commits (`feat:`) the skills suggest.
- A small edit within one session needs no plan — just do it.
- **A new roadmap item is an expensive unit.** Open one only if the work goes beyond the current item's `My paths` or doesn't fit in the current session (it needs its own "Done when" with a number). Small stuff gets fixed on the spot and goes as a line under `Issues` in its `STATUS.md`, or into the commit message if it has no `STATUS.md`. If writing up the item costs more than fixing it — it isn't an item.
- End a plan with a list of open questions. Keep it as short as possible, sacrifice grammar for brevity.
- Ask clarifying questions. Suggest best practices, as if the task were being solved by a panel of experts looking at it from different angles.
- Use the project's existing patterns, don't invent new ones without need.

## Who owns a task

A task that a Claude session is driving gets tagged with **that session's name**. Other sessions find it by name in `ListAgents` and reach out via `SendMessage` if they need to coordinate.

- Your own name — the first line of `ListAgents` output.
- **A roadmap item** — in the "where it's driven" slot of its `ROADMAP.md` line: `` `worktree-A-1` · session `A-1` · since 15.09 ``. An item's session starts with `--name <item ID>`, so the name is known in advance: whoever sets up the worktree puts the tag in place, in the main copy, before the session starts.
- **A task outside the roadmap** in the main copy (a name like `fine-tune-llm-c8`) — the session writes its own name next to the task, wherever that task is tracked.
- Finished or dropped a task — the name comes off along with the status change.

## Concurrent sessions in one working copy

Another Claude session, with its own uncommitted files, can be working in parallel in the project's main copy. The pre-commit hooks on `git commit` and `git push` stash uncommitted changes into a patch for the duration of the run and restore them afterward: anything the other session writes during those seconds is silently rolled back.

- **Before `git commit`, `git push`, `git stash`, `git checkout`, `git rebase` in a copy where another session is working — warn it first** (`ListAgents` → `SendMessage`) and wait for a reply: it will commit its files or leave them untouched.
- Another session is busy in the main copy and you have a **small edit outside the roadmap** — do it in a separate worktree and push an explicit branch from there (`git push origin <branch>:main`), so the other session's local commits don't get carried along. A roadmap item is never merged this way — see skill `mast:worktree-flow`.
- Run a git command with hooks as the **only** Bash call in a round: parallel calls share one shell, their `cd`s get mixed up, and the command ends up in the wrong copy.

## More details — in the skills

- project document structure → skill `mast:project-structure`
- the worktree cycle, merging an item's branch, the dispatcher's role → skill `mast:worktree-flow`
- managing items, findings, closing them out → skill `mast:managing-roadmap-items`
