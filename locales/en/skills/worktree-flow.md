## Working through a worktree

**Every roadmap item is done in its own worktree and merged into `main` once it's ready.** The exception is a small item, while no one else is working in the main copy: mark it `main copy` instead of a worktree.

1. Start: `claude --bg --worktree A-1 --name A-1` plus `--model` and `--advisor` per the rule in "Roadmap dispatcher" — a background session, its working copy in `.claude/worktrees/A-1/`, branch `worktree-A-1`, base `origin/main`. The command prints an id: attach with `claude attach <id>`, list with `claude agents`. Without `--bg` the session opens in the current terminal. The item's line in `ROADMAP.md` must be pushed before the start, or the worktree won't see it.
2. Inside the worktree, edits to the main copy are blocked by the engine (Edit/Write, bash with cwd in the main copy, `git -C` into it). This is a safeguard, not a bug: two roadmap items don't corrupt each other's index or see each other's half-finished files.
3. Commits carry the item's prefix: `[A-1] description`. **The item's session never pushes to `main`** — neither `git push` nor `git push origin <branch>:main`: only the main copy merges (step 4). Before finishing, the background session commits and pushes on its own — only its own branch `worktree-A-1`, after a rebase, via `git push --force-with-lease`.
4. The item is ready (the "Done when" criterion is met, the whole test suite is green) → the item's session runs `git fetch origin && git rebase origin/main` on its own and tells the main copy. **The main copy** merges — it can't be done from the worktree, `main` is occupied by it:
   ```bash
   git merge --ff-only worktree-A-1
   git log --format=%h -1 ORIG_HEAD; git log --format=%h -1 HEAD   # the item's range
   # a thesis in docs/roadmap/DONE.md, the line removed from ROADMAP.md → commit "[A-1] closed" → git push
   ```
   The range `<base>..<tip>` goes into the thesis: `— 17.09 · a1b2c3d..e4f5a6b`, so `git diff a1b2c3d..e4f5a6b` is everything the item did. Hashes are never written before the merge: rebase changes them.
5. After merging — `claude rm <id>` (removes the background session and the worktree) or `git worktree remove .claude/worktrees/A-1`, then `git branch -d worktree-A-1`.

- `.claude/worktrees/` is in the project's `.gitignore`.
- Need gitignored files (`.env` and the like) in every worktree — list them in `.worktreeinclude` at the project root.
- A small edit outside the roadmap doesn't need a worktree, do it in the main copy.
- Unpushed commits should land in a new worktree — `"worktree": {"baseRef": "head"}` in settings; the default base is always a fresh `origin/main`.

## Roadmap dispatcher

When items run in parallel, one main-copy session becomes the **dispatcher**, `--name <project>-dispatch` (the name includes the project: `ListAgents` shows sessions for every project on the machine).

- Only the main copy — the dispatcher or a human — edits `ROADMAP.md`, `docs/roadmap/DONE.md`, and `TECH_DEBT.md`. Item sessions send the dispatcher findings and "done" via `SendMessage`; no dispatcher — the finding goes as a file in `docs/roadmap/inbox/`. Only the main copy assigns an item's number.
- The dispatcher triages findings, assigns numbers and dependencies, starts sessions on items ready to take (model and advisor per the rule below), merges branches one at a time, moves closed items into `DONE.md`, clears blockers, and writes back to waiting sessions. Order — skill `mast:managing-roadmap-items`.
- It asks the human only when the decision changes the meaning or is irreversible: the "Done when" criterion, dropping or merging items with different goals, two items conflicting over the same paths, deleting an unmerged branch, an urgent finding. It decides everything else on its own, the reason goes in the commit message.
- The dispatcher's state is `ROADMAP.md`, `claude agents`, `git worktree list` — not its context: a restart loses nothing.
- **No dispatcher — a human does its steps in the main copy** following the "Roadmap dispatcher" section of skill `mast:managing-roadmap-items`, starting with checking for abandoned items. Findings pile up in `docs/roadmap/inbox/` meanwhile — that's the queue until one shows up.
- An item's model defaults to `opus` with the `fable` advisor. Downgrading to `sonnet` with the `opus` advisor — only if the error is discoverable by checking against something existing, reversible with a single `git revert`, and hits exactly one item. Zones that are always `opus` are declared by the project in `.claude/rules/dispatch.md`; no file — everything goes on `opus`, a file exists (even with no zones) — `sonnet` is allowed under these three conditions.
