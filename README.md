<p align="center">
  <img src="assets/logo.svg" width="128" alt="MAST">
</p>

<h1 align="center">MAST</h1>

<p align="center">
  <img src="https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fex3del%2Fmast%2Fmain%2Fplugins%2Fen%2F.claude-plugin%2Fplugin.json&query=%24.version&label=version&color=0E2238" alt="version">
  <img src="https://img.shields.io/badge/Claude%20Code-%E2%89%A5%202.1.242-D97757" alt="Claude Code ≥ 2.1.242">
  <a href="LICENSE"><img src="https://img.shields.io/github/license/ex3del/mast?color=4F7CAC" alt="MIT"></a>
</p>

<p align="center"><i>Read this in Russian: <a href="README.ru.md">README.ru.md</a></i></p>

**MAST — Method for Agents, Sessions and Tasks.** A way to run a project with several
Claude Code agents so they don't get in each other's way, and what they build doesn't
drift apart.

The goal is development that runs as autonomously as possible. Several tasks move in
parallel while you work from **a single terminal**: you talk to one dispatcher session,
and it hands work out to agents, collects the results, talks to other sessions, turns to
a stronger model for advice, and comes to you only when a decision is yours to make.

## Where it came from

It started with the problems of ultracode mode: it launches dozens of agents at once, and there's no
keeping track of who's doing what or what's already done. The goal was the same reach,
but under control. The pieces turned up in other projects:

- **[beads](https://github.com/steveyegge/beads)** — tasks live in a tracker agents
  understand: what's free, what's taken, what's waiting on what. *But* it's a separate
  database (Dolt) with its own CLI, in embedded mode only one process writes to it, and
  tasks move out of the text next to the code — for a small project that's more
  machinery than benefit;
- **[Agent Teams](https://code.claude.com/docs/en/agent-teams.md)** — a dispatcher role,
  and agents that message each other, not just the human. *But* it's experimental and
  built as "a lead hands out work to subordinates": the lead can't change, one team per
  session, and teammates don't survive `/resume`;
- **[claude-squad](https://github.com/smtg-ai/claude-squad)** — every task gets its own
  working copy, so agents don't trample each other's files. *But* it's a separate program
  on top of tmux, and Claude Code now does worktrees and background sessions natively —
  an extra layer;
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

## How it works

1. **The rules arrive on their own.** The plugin injects a short core of rules into every
   session — nobody has to remind the agent.
2. **The scaffold.** `/mast:init-project` lays out the project's documents once:
   `CLAUDE.md`, the roadmap, the archive, per-folder rules.
3. **Work comes in items.** A task bigger than one session becomes a roadmap item with a
   measurable "Done when".
4. **The dispatcher.** One session in the main copy runs the roadmap: it decides what to
   take and starts a separate agent for each item.
5. **Each item gets its own copy.** The agent works in its own worktree and branch, so
   parallel items don't get in each other's way.
6. **Agents message each other.** Findings and "done" go to the dispatcher as messages
   instead of getting lost in someone's context.
7. **Merge and archive.** The dispatcher merges ready branches one at a time, and a closed
   item moves to the archive with its "before → after" measurements.
8. **Memory lives in documents.** Decisions, debts, and rules are written down next to the
   code, so the next session reads them instead of guessing.

### Documentation layers

Each document answers its own question, and every fact has one home.

**What we're doing**

- `ROADMAP.md` — the overall plan: open items only, each with a done-criterion that has a
  number, who drives it, and what it depends on.
- `docs/roadmap/<A-1>/STATUS.md` — the detailed plan of one item: tasks, a step-by-step
  journal, issues, decisions made. It survives an agent restart; opened only when the item
  needs it.
- `docs/roadmap/inbox/` — agents' findings nobody has triaged yet.

**What we did and why**

- `docs/roadmap/DONE.md` — the archive of closed work: two lines per item — what changed,
  with a number, when, and in which commits. It answers "has this been done before?", and
  its "Dropped" subsection answers "was this tried and rejected?".
- `docs/adr/` — why it was done this way: for decisions that are costly to reverse. Such a
  decision also lives in a rule for the agent and in a test that fails if it's undone.
- `TECH_DEBT.md` — what was deliberately left crooked, and under what condition we fix it.

**Rules**

- `CLAUDE.md` — the project's passport: stack, commands, invariants. It loads into every
  session, so it stays under 200 lines; reference material lives in `docs/`.
- `.claude/rules/*.md` — agreements about a specific folder: they reach the agent only
  when it touches those files.

A closed item reads top-down exactly as deep as you need: a line in the archive → the
item's journal → why it was decided that way → the code itself in `git diff`.

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

## Setting up a project: what `/mast:init-project` does

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

## What's in the plugin

Everything is edited at the repository root — `hooks/` and `locales/`; inside
`plugins/<lang>/` sit their copies, laid out by `tools/sync_plugins.py`. The links below
point to the sources.

### The core — rules in every session

[`locales/en/core.md`](locales/en/core.md) — the handful of rules the method breaks without:
where to write a decision, plan before code, marking ownership with the session's name, an
item's model and advisor, concurrent sessions in one working copy, turning a task into a
checkable goal. Every rule names the skill that holds the details.

- **How it arrives.** At session start a `SessionStart` hook runs
  [`hooks/core.py`](hooks/core.py), and Claude Code puts its output into the context —
  nothing is copied into your project.
- **When.** `ROADMAP.md` or `.claude/rules/` present — the whole core; neither — a single
  line, "the method isn't set up here". With the `always_core` option — the core
  everywhere (see "Setup").
- **Size.** Capped at 8200 characters against the platform's 10000 limit: anything
  heavier lives in skills.

### Skills — load when their description matches the task

| Skill | Files | What's inside |
|---|---|---|
| `mast:managing-roadmap-items` | [shared](locales/en/skills/managing-roadmap-items.md) · [item session](locales/en/skills/managing-roadmap-items-item.md) · [dispatcher](locales/en/skills/managing-roadmap-items-dispatcher.md) | Shared: invariants, the item line format, the archive of closed work, where decisions go. Item session: the baseline measurement, `STATUS.md`, findings outside the item, the closing checklist. Dispatcher: abandoned items, triaging findings, choosing the model, starting sessions, merging branches. Each role reads only its own file |
| `mast:worktree-flow` | [worktree-flow.md](locales/en/skills/worktree-flow.md) | An item's worktree cycle: starting the background session, `[A-1]` commits, rebase, merging by the main copy, cleanup; the dispatcher's role in brief |
| `mast:project-structure` | [project-structure.md](locales/en/skills/project-structure.md) | The table of project documents: when each one appears and what goes in it |

The `skills/<name>/SKILL.md` files in the plugin hold only the description used to pick
the skill and a line saying "read the file above": the texts live in `locales/` so they
aren't duplicated per language.

### The command

[`/mast:init-project`](plugins/en/commands/init-project.md) — survey the project →
proposals with a question per file → apply and lint. Five guardrails: no invented
criterion, an existing file is changed only on a clean git tree, no silent overwrite, the
Claude Code version is checked, only what was found goes into `CLAUDE.md`. `--check` — the
same without writing anything.

### Scaffold templates — [`locales/en/templates/`](locales/en/templates/)

| Template | What it becomes |
|---|---|
| [`CLAUDE.template.md`](locales/en/templates/CLAUDE.template.md) | the project's `CLAUDE.md`: stack, commands, code (fail loud), invariants |
| [`ROADMAP.template.md`](locales/en/templates/ROADMAP.template.md) | an empty `ROADMAP.md` that passes the lint |
| [`rule.template.md`](locales/en/templates/rule.template.md) | `.claude/rules/example.md` — an example rule with `paths:` |
| [`context7.rule.template.md`](locales/en/templates/context7.rule.template.md) | `.claude/rules/context7.md` — library docs through the tool, not from memory |
| [`dispatch.rule.template.md`](locales/en/templates/dispatch.rule.template.md) | `.claude/rules/dispatch.md` — the zones that always run on `opus` |

### Hooks and plumbing

| File | What it does |
|---|---|
| [`hooks.json`](plugins/en/hooks/hooks.json) | the wiring: `SessionStart` → `core.py` with the plugin's language; an edit to `ROADMAP.md` or `DONE.md` → `roadmap_lint.py` |
| [`hooks/core.py`](hooks/core.py) | injects the core or the one-line hint |
| [`hooks/roadmap_lint.py`](hooks/roadmap_lint.py) | catches format violations in the roadmap and the archive right after an edit; with `--ready` — the items ready to take |
| [`hooks/plugin_names.py`](hooks/plugin_names.py) | the plugin's name per language — for the links the hooks print |
| [`.mcp.json`](plugins/en/.mcp.json) | the Context7 MCP server |
| [`plugin.json`](plugins/en/.claude-plugin/plugin.json) | the manifest: version, the `superpowers` dependency, the `always_core` and `context7_key` options |

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
