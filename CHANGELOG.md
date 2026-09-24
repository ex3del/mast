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

### Merging

- `mast merge X-N` merges an item in one command from the main copy; it's available in Claude Code's Bash tool, since the plugin puts it on `PATH`.
- A fast-forward of the branch, then one commit: the thesis in `DONE.md`, the item's line removed from `ROADMAP.md`, debt entries from the branch's last commit added to `TECH_DEBT.md`.
- It refuses before merging and changes nothing if the branch isn't a fast-forward, has commits without the item's prefix, edits `ROADMAP.md`, `DONE.md`, or `TECH_DEBT.md`, or its last commit lacks the verbatim criterion, "before → after" measurements, or the thesis.
- If the default branch has an upstream, it pushes and deletes the merged branch on the remote; `--no-push` skips that.
- It removes the item's session, worktree, and branch.
- It merges only the named item; for sessions whose branches the merge moved, it prints a ready "rebase" message, plus which items were waiting on this one and which are now ready to take.

### Session check

- `mast status` checks everything in one command, from the main copy or from an item's worktree; it changes nothing. It cross-checks in-progress items, worktrees, and this project's sessions from `claude agents`, and names the mismatches: an abandoned item (no live session — with a `claude respawn <id>` command), an orphaned worktree, a stray session named after an item. Other projects' sessions on the machine stay out of the check.
- For every live item session — a ready `claude attach <id>` command.
- A session that finished its turn and waits for a prompt no longer counts as abandoned: an abandoned one is a session whose process has ended.
- An item session with no commit for longer than a threshold gets flagged, but nothing is blocked. The threshold is the line `Silence threshold: 30 min` in `.claude/rules/dispatch.md`, 30 minutes without it; it counts from the item's last commit or the session's restart, whichever is later.
- The same output lists the items waiting on your answer and the number of files in `docs/roadmap/inbox/`.

### Roadmap lint

- It catches edits to `ROADMAP.md` and `DONE.md` made from the shell — `sed`, `perl`, a Python script — not just through Edit/Write; the complaint arrives after the command, once per edit.
- It refuses `git commit` when the commit introduces a new format violation into the roadmap.
- New slot at the end of an item's line — `· waiting on human: <question>`: a slot without a question is an error, and `roadmap_lint.py --waiting ROADMAP.md` lists such items.
- No more false "item number taken, already in DONE.md" complaint when closing an item: `mast merge` writes the archive and the roadmap in one commit.

### For contributors

- Method texts live only in `plugins/<lang>/locales/<lang>/`; the root `locales/` is gone, so there's no second copy.
- Hook code is edited in the root `hooks/`; the copies in the plugins are marked «Сгенерировано… правь там» ("generated… edit there"), and pre-commit and CI catch both drift and a missing mark.
- Copies, not symlinks: git on Windows checks a symlink out as a plain text file by default, and the hook crashes — details in `CONTRIBUTING`.
- `tools/serve_marketplace.py` tests a plugin install through the cache, the way it comes from GitHub, without pushing — the recipe is in `CLAUDE.md`.

### Cost

The hooks fire in every project where the plugin is enabled; each one starts `python3`. Medians on the developer's machine:

- an agent's shell command takes 14 ms longer (has the roadmap changed?), a git command 28 ms (plus the pre-commit check); 17 ms on average across all commands;
- Edit/Write takes 18.5 ms longer (the dispatcher role hook).

### Known limitations

- The lint hooks haven't been tried live on Windows without Git Bash (PowerShell), only in tests.
- The dispatcher role after `/clear` and `/rename` hasn't been tried live; if the hook loses it, use `MAST_ROLE=dispatcher`.
- `git commit` is refused over a new violation in the working-copy roadmap, even if the roadmap isn't being committed.
- Dropping an item is still manual, and the lint complains about the in-between state between the `ROADMAP.md` and `DONE.md` edits.
- The plugin can't be distributed through organization settings on claude.ai: the platform rejects a plugin with a top-level `bin/` directory. Install it from the GitHub marketplace.
