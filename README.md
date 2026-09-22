# MAST

*Read this in Russian: [README.ru.md](README.ru.md)*

**MAST — Method for Agents, Sessions and Tasks.** A way to run a project with several
Claude Code agents so they don't get in each other's way, and what they build doesn't
drift apart.

## Where it came from

It started with ultracode mode: it launches dozens of agents at once, and there's no
keeping track of who's doing what or what's already done. The goal was the same reach,
but under control. The pieces turned up in other projects:

- **[beads](https://github.com/steveyegge/beads)** — tasks live in a tracker agents
  understand: what's free, what's taken, what's waiting on what;
- **[Agent Teams](https://code.claude.com/docs/en/agent-teams.md)** — a dispatcher role,
  and agents that message each other, not just the human;
- **[claude-squad](https://github.com/smtg-ai/claude-squad)** — every task gets its own
  working copy, so agents don't trample each other's files;
- **[superpowers](https://github.com/obra/superpowers)** — discipline around the code:
  plan first, then tests and implementation, then review.

One thing none of them had — **a single source of truth**. When agents write the code,
everything drifts: docs fall behind the code, decisions get forgotten, and the next
session undoes what was agreed yesterday. MAST organizes the work around documents that
grow as the work goes and can be trusted: the roadmap, the archive of what's done,
per-folder rules, debts with the condition for fixing them.

Later, some rules came from **[Ouroboros](https://github.com/razzant/ouroboros)** — a
system that rewrites its own rules: a recurring mistake gets caught by a check, not by
one more paragraph of instructions, and every fact has exactly one owner.

## What's inside

A Claude Code plugin that brings a particular way of working into your project: roadmap
items with measurable acceptance criteria, a worktree per item, a dispatcher for parallel
work, path-scoped rules, an archive of closed work. It never touches your global
`~/.claude/CLAUDE.md`, and it doesn't write to your project without asking first. Claude
Code itself records the plugin being enabled in your `settings.json` — the same
bookkeeping entry any plugin gets — but the method and its hooks never write there
themselves.

## Requirements

Claude Code **2.1.242 or newer**. Two things set that floor: `SendMessage` and
`ListAgents`, which the dispatcher and the parallel-session rules rely on,
reached all platforms in 2.1.234; and a dependency entry that names a
marketplace — which is how this plugin declares `superpowers` — is resolved
correctly from 2.1.242 on. `/mast:init-project` checks the running version
during its survey step and tells you if a part of the method won't work.

The plugin **depends on `superpowers@claude-plugins-official`** and Claude
Code installs it along with MAST: the item-session skill hands planning over
to `superpowers:writing-plans`. Without that plugin the method still works —
the skill says to write the plan's tasks yourself — but the handover is the
path it was built for.

## Setup

```bash
claude plugin marketplace add ex3del/mast
claude plugin install mast@ex3del --scope user
```

**The language is the plugin you install.** `mast` carries the English texts,
`mast-ru` the Russian ones — install one of the two, not both, or two copies of
the core land in every session. They share one code base and one repository;
only the texts differ. To switch languages later, uninstall one and install the
other:

```bash
claude plugin install mast-ru@ex3del --scope user
```

Then turn auto-update on — this step is easy to skip and shouldn't be,
because auto-update is **off by default** for third-party marketplaces. Either through the `/plugin`
menu inside a session (find the `ex3del` marketplace → enable auto-update), or
by adding this to `~/.claude/settings.json` yourself:

```json
{ "extraKnownMarketplaces": { "ex3del": { "source": { "source": "github", "repo": "ex3del/mast" }, "autoUpdate": true } } }
```

Without this step new releases won't reach you — Claude Code only checks
auto-update-enabled marketplaces in the background, roughly once per session
start with a random delay of up to ten minutes; a fresh version is picked up
on the next start or via `/reload-plugins`.

### Install variant: the core in every project

```bash
claude plugin install mast@ex3del --scope user --config always_core=true
```

How this differs from the install above: by default the core reaches **only**
projects where the method is already set up (`ROADMAP.md` or `.claude/rules/`
present), and everywhere else a single line arrives instead — "the method isn't
set up here, run `/mast:init-project`". With `always_core=true` the core reaches
**every** project; in unscaffolded ones that same line stays on top as a hint.
Nothing else changes: same skills, same command, same lint — the only difference
is whether the rules show up where there's no scaffold.

Install it this way if the method is how you work in general, not only in
prepared repositories. The price is roughly 8k characters of context per session.

- `--config` is stored **only during an actual install**. Already installed —
  `install` reports "already installed" and stores nothing: run
  `claude plugin uninstall mast@ex3del` first, then the command above.
- The value lands in `~/.claude/settings.json` — you can also write it by hand:
  ```json
  { "pluginConfigs": { "mast@ex3del": { "options": { "always_core": true } } } }
  ```
- It takes effect from the next session; in the current one run `/reload-plugins`.

## What `/mast:init-project` does

One command, one scenario, for both a brand-new project and one with history:
it surveys the repository (stack, tests, existing `CLAUDE.md`/`ROADMAP.md`/
`TODO.md`/`CHANGELOG.md`, rules under `.claude/rules/`, git remote and
default branch, open issues), then goes file by file. A file that doesn't
exist yet is scaffolded from the plugin's templates (`CLAUDE.md`,
`ROADMAP.md`, an example `.claude/rules/*.md` with `paths:`, a
`.claude/worktrees/` line in `.gitignore`). A file that already exists gets a
diff — "was → would become" — and a direct question; nothing is overwritten
silently, and a "no" is a legitimate answer, not an error. Run
`/mast:init-project --check` to see the same survey and the same diffs
without touching anything — a forced dry run, useful to see what the command
would propose to a project you're not ready to hand it yet.

Guardrails baked into this scenario: a "Done when" criterion is never
invented — a vague acceptance line is carried over as-is and flagged as
"unmeasured, needs your number"; a file already on disk is only rewritten
against a clean git tree, so the diff and the rollback are `git diff`/`git
checkout` away; nothing is created or changed without a question first.

## Working: starting the dispatcher

The method's main command. Once the scaffold is in place, start a dispatcher
session in the project's **main copy** — it drives the whole chain from there:

```bash
cd ~/code/<project>
claude --name <project>-dispatch --model opus --advisor fable \
  "You are this project's roadmap dispatcher: run it per skill mast:managing-roadmap-items. Start by checking for abandoned items, then show what's ready to take."
```

- **`--name <project>-dispatch`** — item sessions find the dispatcher by this name in
  `ListAgents` and send it findings and "done". The project is in the name because
  `ListAgents` lists sessions from every project on the machine.
- **`--model opus --advisor fable`** — the dispatcher decides what to take, who runs it,
  and when to merge; don't save on it. If you have `opus[1m]`, use it: a dispatcher
  accumulates context for hours.
- **What it does:** opens items in `ROADMAP.md`, starts a session per item in its own
  worktree, triages findings, merges ready branches one at a time, moves closed items to
  `DONE.md`. Only the dispatcher edits `ROADMAP.md`, `DONE.md`, and `TECH_DEBT.md`.
- **You don't start item sessions by hand** — the dispatcher launches them in the
  background: `claude --bg --worktree A-1 --name A-1 --advisor fable "…"`, and for items
  that passed the downgrade — `--model sonnet --advisor opus`. List them with
  `claude agents`, step into one with `claude attach <id>`.
- **No dispatcher** is fine while there's a single item: drive it yourself in the main
  copy; findings land as files in `docs/roadmap/inbox/` and wait for a dispatcher.

## The core: what it is and how it arrives

- **The core** — `locales/<lang>/core.md`: the rules the method breaks without. Where
  to write a decision, plan before code, marking ownership with the session's name,
  which model an item runs on, turning a task into a checkable goal, concurrent
  sessions in one working copy.
- **It arrives through a `SessionStart` hook.** At session start Claude Code runs
  `hooks/core.py` and puts its output into the context. No file in your project, no
  import — just the hook's output.
- **Capped at 8200 characters**, against the platform's 10000-per-insertion limit.
  Anything heavier lives in **skills**: they load only when their description matches
  the task, and cost nothing in the sessions that don't need them.
- **The condition:** `ROADMAP.md` or `.claude/rules/` present — the whole core; neither
  one — a single line, "the method isn't set up here, run `/mast:init-project`". That
  way the plugin weighs nothing in other people's repositories.
- **The `always_core` option** lifts that condition: the core arrives in unscaffolded
  projects too, underneath the same hint line. How to turn it on — see "Setup".
- **Language is which plugin you install** (`mast` or `mast-ru`), not a setting inside one.

## Context7 bundled

The plugin ships the [Context7](https://context7.com) MCP server (remote,
`https://mcp.context7.com/mcp`) so up-to-date library docs are one lookup
away. No key is required — the free tier is enough for normal use — so the
"two commands and you're set" promise holds even here. If you hit its rate
limit, add your own key in the plugin's configuration under "Context7 API
key"; the field is optional and stored as sensitive.

The bundle also includes a rule, offered by `/mast:init-project` as its own
scaffold artifact (`.claude/rules/context7.md`): check a documentation-lookup
tool before relying on memory for library/framework/SDK/CLI questions. It
names the tool by role, not by exact server name, so it works whether you use
the bundled Context7 or one of your own — and if you already have your own
docs server configured, the command says so and offers to skip.

## Honest limitations, today

- `hooks/roadmap_lint.py` understands **only** these status words and
  acceptance-criterion headings (`запланирован`/`planned`, `в работе`/
  `in progress`, `готов`/`done`, `снят`/`dropped`, «Готово когда»/`Done when`).
  Invent your own synonym and the line stops being recognized.
- In some restricted session setups `/mast:init-project` may not be able to
  read its own template files under the plugin's install directory; if it
  reports templates as unavailable, relaunch the session with
  `--add-dir <path to the mast plugin>`.
