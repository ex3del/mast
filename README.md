# MAST

*Read this in Russian: [README.ru.md](README.ru.md)*

MAST — Method for Agents, Sessions and Tasks. A Claude Code plugin that brings a
particular way of working into your project: roadmap items with measurable
acceptance criteria, a worktree per item, a dispatcher for parallel work,
path-scoped rules, an archive of closed work. It never touches your global
`~/.claude/CLAUDE.md`, and it doesn't write to your project without asking
first. Claude Code itself records the plugin being enabled in your
`settings.json` — the same bookkeeping entry any plugin gets — but the
method and its hooks never write there themselves.

## Requirements

Claude Code **2.1.234 or newer** (that's when `SendMessage` and `ListAgents`,
which the dispatcher and parallel-session rules rely on, reached all
platforms). `/mast:init-project` checks the running version during its survey
step and tells you if a part of the method won't work below it.

## Setup in three steps

Three steps — the third one matters, because auto-update is **off by
default** for third-party marketplaces:

```bash
claude plugin marketplace add ex3del/mast
claude plugin install mast@ex3del --scope user
```

Then turn auto-update on, either through the `/plugin` menu inside a session
(find the `ex3del` marketplace → enable auto-update), or by adding this to
`~/.claude/settings.json` yourself:

```json
{ "extraKnownMarketplaces": { "ex3del": { "source": { "source": "github", "repo": "ex3del/mast" }, "autoUpdate": true } } }
```

Without this step new releases won't reach you — Claude Code only checks
auto-update-enabled marketplaces in the background, roughly once per session
start with a random delay of up to ten minutes; a fresh version is picked up
on the next start or via `/reload-plugins`.

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

## Core vs. skills

Two different weights, on purpose. The **core** — `locales/<lang>/core.md` —
is injected into every session automatically by a `SessionStart` hook, capped
at 6000 characters (the platform's own insertion limit is 10000): where to
write a decision, the plan-before-code order, how sessions mark ownership of
work, and how not to step on another session's uncommitted files. It's the
handful of rules the method breaks without. Everything heavier — how to take
a roadmap item into work or close one, how project documents are laid out,
the full worktree/merge/dispatcher cycle — lives in **skills** instead, and
loads only when its description matches what you're doing, so it costs
nothing in sessions that don't need it.

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

## Choosing a language

`userConfig.language` picks `ru` (default) or `en` for the core text, the
skills, and the scaffold templates `/mast:init-project` copies. Set it at
install time:

```bash
claude plugin install mast@ex3del --scope user --config language=en
```

or change it later from the `/plugin` menu inside a session (find `mast` →
its configuration screen) — takes effect on the next session start.

## Honest limitations, today

- `hooks/roadmap_lint.py` currently understands only **Russian** status words
  (`запланирован`, `в работе`, …) and the Russian "Готово когда" heading for
  the acceptance criterion. An English-language `ROADMAP.md` will not pass
  it yet — a bilingual linter is tracked as a separate roadmap item, not done
  here.
- In some restricted session setups `/mast:init-project` may not be able to
  read its own template files under the plugin's install directory; if it
  reports templates as unavailable, relaunch the session with
  `--add-dir <path to the mast plugin>`.
