# Changelog

*Read this in Russian: [CHANGELOG.ru.md](CHANGELOG.ru.md)*

## 4.0.0 — upcoming

Everything below ships as 4.0.0. Build 3.3.2 already reached you as a marketplace auto-update,
without a changelog: it brought the "waiting on human" slot, a task instead of a plan, and the
rule on self-contained messages. Builds 3.3.3–3.3.7 were never published. The reasoning is in
two research notes (in Russian): [dispatcher load](docs/research/2026-09-23-dispatcher-load.md)
and [deterministic contracts](docs/research/2026-09-23-deterministic-contracts.md).

### Dispatcher

- The dispatcher sets the task and no longer writes the plan: the item's session creates its plan and `STATUS.md`; the dispatcher provides the item's line with a description, paths, and the "Done when" criterion.
- Context from the conversation with you — why the item exists, what was rejected, what the constraints are — goes into the item's line: the line survives a session restart, the start prompt doesn't.
- The session start prompt is a short template: item number, skill, path neighbors.
- The dispatcher asks you in a plain message, not a modal: the plugin's hook denies it `AskUserQuestion`, which held up merges and session messages until you answered.
- The hook recognizes the dispatcher by the session name `<project>-dispatch`; the fallback is the environment variable `MAST_ROLE=dispatcher`.
- While the answer is pending, the item's line carries `waiting on human: <question>` and the item keeps working; `grep 'waiting on human' ROADMAP.md` lists everything waiting on you.
- The hook denies the dispatcher Edit/Write in the main copy outside `ROADMAP.md`, `docs/roadmap/`, and `TECH_DEBT.md`: a small fix goes to a subagent in its own worktree, and the dispatcher merges its branch.
- The dispatcher is always an interactive terminal session: the platform won't let a background one (`claude --bg`) edit the main copy, not even `ROADMAP.md`.
- Item sessions coordinate with each other directly; the dispatcher gets findings and "done".
- A message to you stands on its own: it makes sense without knowing the item, with an example, options, and a recommendation; an item number only comes with a note on what the item is.
- The dispatcher doesn't forward a session's question or finding as is — it rewrites it by that rule.
- Ask about the current state ("what do you need from me") with `/btw`: the answer comes from the dispatcher's context and stays out of its history.

### Starting an item

- By default an item runs on `opus` with advisor `fable`; `--model sonnet` (with advisor `opus`) is the exception for an item that passed the downgrade.
- `mast start X-N` starts an item in one command from the main copy: the item's line becomes "in progress", a commit `[X-N] taken into work · <model>`, a push if the default branch has an upstream (`--no-push` skips it), and a background session; the last line of the output is `claude attach <id>`.
- The item's worktree is created from the local `main`, so it has the item's line even without a push; then the session's prompt says "don't push, rebase onto the local main".
- Before the start it refuses and changes nothing: the item isn't ready to take; its "My paths" overlap an item in progress — the human's approval is `--force "reason"`, and the reason goes into the commit; `--model sonnet` without `.claude/rules/dispatch.md` or on an opus zone (the zones from that file, plus `CLAUDE.md` and `.claude/**`); advisor `fable` for `sonnet`; a prompt tail longer than 300 characters; a live session holds the item's name or its branch already exists.
- The command builds the prompt: number, skill, path neighbors with their session names. The dispatcher adds only the tail: what moved in `main`, windows on shared resources.

### Merging

- `mast merge X-N` merges an item in one command from the main copy; it's available in Claude Code's Bash tool, since the plugin puts it on `PATH`.
- A fast-forward of the branch, then one commit: the thesis in `DONE.md`, the item's line removed from `ROADMAP.md`, debt entries from the branch's last commit added to `TECH_DEBT.md`.
- It refuses before merging and changes nothing if the branch isn't a fast-forward, has commits without the item's prefix, edits `ROADMAP.md`, `DONE.md`, or `TECH_DEBT.md`, or its last commit lacks the verbatim criterion, "before → after" measurements, or the thesis.
- If part of the item's work was already in main — a second attempt or an edit in the main copy — `mast merge` merges anyway and lists those commits in the `DONE.md` thesis and the closing commit.
- If the default branch has an upstream, it pushes and deletes the merged branch on the remote; `--no-push` skips that.
- The branch's last commit carries a "Brief:" block for you — what was done, what changed for the user, what to check by eye, at most 800 characters; without it, or longer — a refusal. `mast merge` prints the brief, the list of files from `git diff --stat` and the command to ask the session, puts them in the closing commit, and the dispatcher forwards them to you right after the merge.
- The merged item's session lives for another hour — the Claude Code cache's lifetime: a question through `claude attach <id>` during that hour is read from the cache. The next `mast merge` or `mast start` removes it with its worktree and branch once an hour has passed since the session's last message — previously `mast merge` removed them at once. A branch that moved ahead after the merge is not deleted.
- After the hour you ask the session with the command from the closing commit or `mast status` — `claude --resume <id> --fork-session`: it brings back the item's whole history, after the cleanup too. The first such question writes the session's whole context to the cache again. The transcript is kept as long as the Claude Code setting `cleanupPeriodDays` says — 30 days by default.
- It merges only the named item; for sessions whose branches the merge moved, it prints a ready "rebase" message, plus which items were waiting on this one and which are now ready to take.
- Before merging it calls a reviewer without the item's history: a separate `claude -p` with no plugins, tools, `STATUS.md` log or intermediate commits sees the diff, the item's whole line — the task, the human's decisions, "Done when" — and the "ready" message. `ok` — it merges; `refused` — it changes nothing and prints the reasons for the item's session; no verdict — it doesn't merge. Edits to `.claude/`, `CLAUDE.md` and skills get a stricter review.
- The reviewer gets the project rules — the ones a session editing the diff's files would get: the project `CLAUDE.md`, `.claude/rules/` with no `paths:` or with matching ones, the global `~/.claude/CLAUDE.md`. A broken rule — a refusal; what you decided in the item's line the reviewer doesn't ask again; a measurement claimed in "ready" with no test in the diff checking it — not `ok`.
- A number from "Done when" that no test can check — time, a share on real data, a live check of the installed build — the reviewer accepts without asking you if the diff holds the measuring script or live test that produced it and the script measures what is claimed. The script measures something else — a refusal; no script — a question to you, as before. The item session skill says to put such a script in the branch outside `docs/roadmap/`: the reviewer doesn't see that folder.
- Files marked `linguist-generated` in `.gitattributes` (lock files, build output) are not sent to the reviewer: there is nothing to check in them, and they eat a lot of tokens.
- The reviewer is unsure — the script gives the item `waiting on human: <the reviewer's question>` in a separate commit. You answered "merge" — the dispatcher replaces the slot with `human decided: <answer>`, and `mast merge` merges without a new review while the diff is the same; the question and the answer stay in the closing commit.

### Session check

- `mast status` checks everything in one command, from the main copy or from an item's worktree; it changes nothing. It cross-checks in-progress items, worktrees, and this project's sessions from `claude agents`, and names the mismatches: an abandoned item (no live session — with a `claude respawn <id>` command), an orphaned worktree, a stray session named after an item. Other projects' sessions on the machine stay out of the check.
- For every live item session — a ready `claude attach <id>` command.
- A session that finished its turn and waits for a prompt no longer counts as abandoned: an abandoned one is a session whose process has ended. One that died on an API disconnect, whose state Claude Code still shows as `blocked`, is abandoned too, not "in progress".
- A closed item whose session isn't removed yet — a line "X-N closed, the session is open until HH:MM" with `claude attach <id>`, after the hour — the command to ask it and `claude rm <id>`. Its worktree isn't an orphan, a session named after a closed item isn't a stray; `mast status` still removes nothing.
- An item session with no commit for longer than a threshold gets flagged, but nothing is blocked. The threshold is the line `Silence threshold: 30 min` in `.claude/rules/dispatch.md`, 30 minutes without it; it counts from the item's last commit or the session's restart, whichever is later.
- The same output lists the items waiting on your answer and the number of files in `docs/roadmap/inbox/`.

### Brief after `/compact`

- After `/compact` an item session in `.claude/worktrees/X-N` gets its item's line from the main copy's `ROADMAP.md` in context — the header, "My paths" and "Done when" verbatim — and the path to `STATUS.md`. Before, after the context was compacted, the model recalled the item and its criterion on its own.
- The `<project>-dispatch` dispatcher gets its role with pointers to the skills and the output of `mast status` after `/compact`.
- The brief comes on any session start and is at most 1500 characters; a session with no role and outside an item's worktree doesn't get it.

### Roadmap lint

- It catches edits to `ROADMAP.md` and `DONE.md` made from the shell — `sed`, `perl`, a Python script — not just through Edit/Write; the complaint arrives after the command, once per edit.
- It refuses `git commit` when the commit introduces a new format violation into the roadmap.
- New slot at the end of an item's line — `· waiting on human: <question>`: a slot without a question is an error, and `roadmap_lint.py --waiting ROADMAP.md` lists such items.
- No more false "item number taken, already in DONE.md" complaint when closing an item: `mast merge` writes the archive and the roadmap in one commit.

### Session guards

- A hook denies edits to `ROADMAP.md`, `docs/roadmap/DONE.md`, and `TECH_DEBT.md` in an item's worktree: only the main copy edits them, and an edit on the branch used to surface as a rebase conflict or a `mast merge` refusal. The reason says where to write instead: the line, debt, a finding — to the dispatcher; the thesis and debt for the archive — in the last commit.
- A `git commit` from a worktree that carries these files is refused, with the command to restore them.
- In a project with `ROADMAP.md` superpowers plans and specs don't go to `docs/superpowers/`: the hook denies the write and names the item's path — `docs/roadmap/<X-N>/STATUS.md`, with the spec next to it.
- A hook denies `git merge` of an item branch (`worktree-X-N`) and points to `mast merge X-N`; the dispatcher's subagent branches (`worktree-agent-*`) still merge with `git merge --ff-only`.
- The guards apply to every session, not only the dispatcher. On the history of two projects — 28,539 edits and commands — there were 0 false denials.

### For contributors

- Method texts live only in `plugins/<lang>/locales/<lang>/`; the root `locales/` is gone, so there's no second copy.
- Hook code is edited in the root `hooks/`; the copies in the plugins are marked «Сгенерировано… правь там» ("generated… edit there"), and pre-commit and CI catch both drift and a missing mark.
- Copies, not symlinks: git on Windows checks a symlink out as a plain text file by default, and the hook crashes — details in `CONTRIBUTING`.
- `tools/serve_marketplace.py` tests a plugin install through the cache, the way it comes from GitHub, without pushing — the recipe is in `CLAUDE.md`.

### Cost

The hooks fire in every project where the plugin is enabled; each one starts `python3`. Medians on the developer's machine:

- an agent's shell command takes 14 ms longer (has the roadmap changed?), a git command 28 ms (plus the pre-commit check); 17 ms on average across all commands;
- a commit from a worktree takes 8 ms more (does it carry roadmap files?);
- Edit/Write takes 19 ms longer (the dispatcher role hook and the session guards).

The review in `mast merge` is one `opus` call per merge: 6–23 thousand tokens, median 13 thousand, and about 45 s when measured, 94 thousand tokens and 3 min live on a large branch (about 1000 diff lines); the token count is in the output and in the closing commit.

### Known limitations

- The lint hooks haven't been tried live on Windows without Git Bash (PowerShell), only in tests.
- The dispatcher role after `/rename` hasn't been tried live (it survives `/clear` and `/compact`); if the hook loses it, use `MAST_ROLE=dispatcher`.
- `git commit` is refused over a new violation in the working-copy roadmap, even if the roadmap isn't being committed.
- The guard against `git merge` of an item branch reads the command text: a merge done another way (`git pull`, a script) gets past it.
- Dropping an item is still manual, and the lint complains about the in-between state between the `ROADMAP.md` and `DONE.md` edits.
- `mast start` compares paths by pattern, not by file: two different masks in the same path segment (`*.py` and `test_*`) don't count as an overlap.
- The plugin can't be distributed through organization settings on claude.ai: the platform rejects a plugin with a top-level `bin/` directory. Install it from the GitHub marketplace.
