---
description: Scaffold the MAST method in a new project, or migrate an existing project's docs to it under human review — CLAUDE.md, ROADMAP.md, docs/roadmap/, .claude/rules/.
---

The scaffold texts this command will copy (`CLAUDE.md`, `ROADMAP.md`, the example rule)
are taken from the plugin's English locale — `${CLAUDE_PLUGIN_ROOT}/../../locales/en/`.

You are bringing the current project up to the MAST method's scaffold. Five scaffold
artifacts: `CLAUDE.md`, `ROADMAP.md`, the `docs/roadmap/` directory, the file
`.claude/rules/example.md` (an example rule with `paths:`) and the line
`.claude/worktrees/` in `.gitignore`. A project with history also has its own `TODO.md`,
`CHANGELOG.md`, rules without `paths:` and whatever else the method can carry over into
its own format — that is the audit, the three steps below. Separate from those five is a
sixth, optional artifact: the Context7 rule `.claude/rules/context7.md` (the plugin ships
the MCP server itself along with it, see README); it is offered by its own separate
question at step 2, not within the common five.

The templates to copy live in the plugin: `${CLAUDE_PLUGIN_ROOT}/../../locales/en/templates/`
— `CLAUDE.template.md`, `ROADMAP.template.md`, `rule.template.md`, `context7.rule.template.md`.

## The `--check` argument

`$ARGUMENTS` contains `--check` — the command runs to the end of step 2 (the survey and the
proposals), shows every finding and every diff, but **asks no questions and doesn't move on
to step 3**: not a single file is created or edited. This is a forced dry run — the guarantee
"`--check` changes 0 files" doesn't depend on there being someone to answer questions (in a
non-interactive run there is nobody to answer anyway, but `--check` makes that explicit
rather than a side effect).

## Audit guardrails

There are five, and they hold for the whole scenario below, not only for findings in a foreign format:

1. **A "Done when" with a number is never invented.** Carrying over someone else's wording
   ("add PDF export") doesn't turn into a measurement of your own. The wording is carried
   over as is, the criterion is marked as not set and is left for the human to fill in.
   Invented numbers break the method on day one.
2. **The git tree must be clean before editing or replacing a file that already exists.**
   Then the result of such an edit is visible through `git diff`, and the rollback is one
   command; that is more reliable than any backup copy, and that is exactly why the
   guardrail exists — if there is something to overwrite, there is something to roll back.
   The rule looks at the specific file, not at the category of the proposal: the file didn't
   exist and is created from scratch (be it one of the five base artifacts, or `ROADMAP.md`
   built from `TODO.md`, or `docs/roadmap/DONE.md` built from `CHANGELOG.md`) — there is
   nothing to overwrite, a clean tree doesn't block it, the rollback for such a file is
   simply `rm`, not `git diff`; the tree is dirty at that point — warn about it, but don't
   stop. The file already exists and is being changed in place (a long `CLAUDE.md`, a rule
   without `paths:`, appending a line to an existing `.gitignore`, an already existing
   `ROADMAP.md`) — a dirty tree blocks exactly that edit, ask for a commit first.
3. **No file is overwritten silently.** There is a file — a "was → would become" diff and a
   separate question about it. A human's refusal is a legitimate outcome, not an error to be worked around.
4. **The Claude Code version is checked in the survey.** The dispatcher and parallel sessions
   (`SendMessage`, `ListAgents`) require 2.1.234 or higher, and the declared dependency on
   `superpowers` requires 2.1.242, so the plugin's minimum is 2.1.242.
   A lower version — the method is scaffolded anyway, but the report says plainly which part
   won't work. The version couldn't be checked (for example, permission to run
   `claude --version` was declined) — write "version not checked" into the survey plainly,
   don't treat it as "below the minimum" and don't keep quiet about it — the scenario continues as usual.
5. **Only what was found goes into `CLAUDE.md`.** The stack, the commands, the test framework,
   the conventions and the root folders are taken from the project's files; whatever isn't in
   the files stays a `<...>` placeholder for the human. A guess about the test command costs
   more than an empty slot: acceptance is run against it later.

## Step 1. Survey

Collect and briefly show the human:

- **Stack and dependencies** — from the manifests in the project root (`package.json`,
  `pyproject.toml`, `requirements.txt`, `go.mod`, `Cargo.toml`, `Gemfile`, ...), whichever are there.
- **Tests** — the command that runs them, if it's visible in a manifest, a `Makefile` or a CI
  config (`npm test`, `pytest`, `go test ./...`, ...). Not visible — say so, don't invent a command.
- **Remote and default branch** — `git remote -v` and `git branch --show-current`. There are no
  branches in the repository yet (a fresh `git init`) — note that, don't invent a branch.
- **Claude Code version** — `claude --version`. Compare with the minimum 2.1.242 by
  major.minor.patch (guardrail 4). Below the minimum — record it in the survey; couldn't check
  — record that explicitly too ("version not checked"), don't equate it with "below the minimum".
  Neither of the two is a reason to stop by itself, and no file is written at this step yet.
- **Cleanliness of the git tree** — `git status --porcelain`. Record the result in the survey and
  remember it for step 3 (guardrail 2): there it blocks only edits to files that already exist,
  and creating any new file from scratch is not stopped by a dirty tree.
- **Data for `CLAUDE.md`** — what will go into the template at step 3 in place of the placeholders.
  Read in parallel, each one only if such a file exists, and don't fill anything in by guesswork
  (guardrail 5):
  - **stack** — the root manifest (`package.json`, `pyproject.toml`, `requirements.txt`,
    `Cargo.toml`, `go.mod`, `*.csproj`, `pom.xml`, `build.gradle`): the language, the runtime
    version, frameworks, key libraries, the database and brokers, if they are named there;
  - **commands** — install, run, build, test, lint: the manifest's `scripts`, `Makefile`,
    `justfile`, `tox.ini`, the CI config. A command that exists nowhere won't be in the file;
  - **tests** — directories (`tests/`, `test/`, `__tests__/`, `spec/`, `e2e/`) and configs
    (`jest.config.*`, `vitest.config.*`, `pytest.ini`, `playwright.config.*`,
    `cypress.config.*`): which framework and where they live;
  - **infrastructure** — `Dockerfile`, `docker-compose.yml`, `.github/workflows/`,
    `.gitlab-ci.yml`, `Jenkinsfile`, `*.tf`, `k8s/`, `helm/`: one line on what's there;
  - **conventions** — `.editorconfig`, `.eslintrc*`/`eslint.config.*`, `.prettierrc*`,
    `tsconfig.json` (whether `strict` is on), `[tool.black]`/`[tool.ruff]` in `pyproject.toml`,
    `.flake8`;
  - **root folders**, other than the service ones (`node_modules`, `.git`, `dist`, `build`,
    `.next`, `__pycache__`, `.venv`, `target`, `vendor`) — one line per folder, what it holds;
  - **`README.md` and `CONTRIBUTING.md`** — the project description in one or two lines and the
    development conventions, if they are there.
- **What of the scaffold already exists** — check each of the five artifacts separately: the file
  `CLAUDE.md`, the file `ROADMAP.md`, the directory `docs/roadmap/`, the file
  `.claude/rules/example.md`, and whether `.gitignore` (if it exists) has the line `.claude/worktrees/`.
- **The Context7 rule** — whether `.claude/rules/context7.md` already exists (the sixth artifact,
  separate from the five above, see step 2).
- **What else the project has besides the scaffold** — what the method can migrate:
  - `TODO.md` or a homemade roadmap (any file with a task list outside our format) — whether
    there is one, how many items, in what shape.
  - `CHANGELOG.md` — whether there is one, whether it holds closed work.
  - `docs/` — what's inside, if the directory already exists.
  - `.claude/rules/*.md`, other than `example.md` and `context7.md` (it has its own line above) —
    which ones there are, for each separately: does the file start with `paths:` frontmatter or not.
  - `.claude/worktrees/` — whether the directory exists (traces of unfinished worktrees), even if
    there is no line for it in `.gitignore` yet.
  - A docs server of its own — if the project has its own `.mcp.json` (that is a project file,
    not a plugin file), whether it holds a server whose name or `url` looks like documentation
    lookup (contains `context7`, for example) — useful at step 2 for the question about the
    Context7 rule. The check looks only at that file: a server the user connected globally or
    only in the current session won't be seen by this heuristic — which is why the question
    about the rule at step 2 is asked in any case, not only when the file is empty or missing,
    and the human decides.
  - Open issues — if there is a GitHub remote and `gh` is available, `gh issue list`; no access
    or no remote — don't invent, just don't show this line.

For every finding — one line: what the file is, what role it plays, how far it diverges from the
scaffold's reference shape. Step 1 writes and edits none of this — it only reads.

## Step 2. Proposals and questions

Split what you are going to propose into two kinds.

**First check that the templates are readable** — `${CLAUDE_PLUGIN_ROOT}/../../locales/en/templates/*.template.md`.
Unreadable (it happens — the session's access is limited to the project's working directory, and
the plugin's directory isn't inside it) — this affects not only the `ROADMAP.md` diff when
migrating `TODO.md`, but all five base artifacts at once (and the Context7 rule too — it is the
same kind of template): don't make up any of them from memory, neither `CLAUDE.md`, nor
`ROADMAP.md`, nor `rule.template.md` for `.claude/rules/example.md`, nor
`context7.rule.template.md` — the format isn't reproduced exactly from the method's core text in
the context, and the lint at step 3 won't pass such a file. Say plainly that the templates are
unavailable, and give a ready next step: relaunch with `--add-dir <plugin root>` — that is
exactly the value of `${CLAUDE_PLUGIN_ROOT}` which you already see substituted in this very
command text (for a real user it is usually `~/.claude/plugins/...` — the typical case, not a
rare one). Proposals that need no template (a rule without `paths:`, `CHANGELOG.md` →
`DONE.md`, the `.gitignore` line) are not affected by this — show them as usual.

**Missing scaffold artifacts** — those of the five that don't exist at all. Their diff is
degenerate: the file didn't exist — a copy of the template appears. Show the list concretely:

1. `CLAUDE.md` — the template `${CLAUDE_PLUGIN_ROOT}/../../locales/en/templates/CLAUDE.template.md`
   with the survey's data filled in: stack, commands, tests, conventions, root folders, the
   description from `README.md`. The diff here isn't degenerate — show the resulting text in
   full. The command doesn't invent the "Project invariants" and "Code" sections: they come from the template as is.
2. `ROADMAP.md` — a copy of `ROADMAP.template.md`, **if** no `TODO.md` or homemade roadmap is
   being migrated into the project (then `ROADMAP.md` is not in this list but in its own
   question below — its content isn't the template's, it is assembled from the finding).
3. `docs/roadmap/` — an empty directory (git doesn't store it, it appears with the first item).
4. `.claude/rules/example.md` — a copy of `rule.template.md`.
5. The line `.claude/worktrees/` in `.gitignore`: no file — create it with that line; the file
   exists but the line doesn't — append it at the end; the line is already there — don't touch
   it at all, and then this point isn't in the list.

A `<...>` placeholder for which the survey found no data stays a placeholder — the human fills
it in for their own project. Only what was read from the project's files is filled in
(guardrail 5); invented details — "TaskFlow", "PDF export", a test command "by analogy" — are
not carried into the template. In `ROADMAP.md` and in the rules, placeholders are not filled in
at all: there is no data there that could be read — only human decisions.

There is nothing to overwrite here (all five are either a copy or an appended line), so ask one
common question for all of it at once and wait for an explicit confirmation before writing a
single file. A refusal or no answer — create nothing from this list.

**The Context7 rule — the sixth artifact, separate from the five above.** `.claude/rules/context7.md`
is not part of the common question: the plugin ships it together with the Context7 MCP server
(see README), but the server and the rule are not one and the same decision, so the rule has its
own question. The file doesn't exist yet — propose a copy of `context7.rule.template.md`, the
diff is degenerate, as for the other five. Step 1 found a docs server of the project's own in
`.mcp.json` — don't push yours: tell the human such a server is already configured, and offer to
skip (the rule names the tool by role rather than by name, and will work with any server,
including the one already configured — so agreement is a legitimate answer too, just not the
only expected one). The file `.claude/rules/context7.md` already exists — it counts as in place,
like the other five: it is not compared against the template, and there is no separate question
about it here (if it has no `paths:` — that is caught by the general table row "a rule in
`.claude/rules/` without `paths:`" below, as for any other rule).

**Findings that conflict or are due to be carried over** — each gets its own "was → would become"
diff and its own separate question; the answers to them are independent:

| What was found | What we propose |
|---|---|
| `TODO.md` or a homemade roadmap | the items in our format: section letter, number, status, `My paths`, `Done when` — the diff shows the proposed `ROADMAP.md` text. A criterion with no number in the original — carried over as text and marked as not set (guardrail 1), not invented |
| `CLAUDE.md` longer than 200 lines | what to move out to `docs/` (architecture, reference), what to `.claude/rules/*.md` with `paths:`, what to leave as is — a separate diff per piece |
| a rule in `.claude/rules/` without `paths:` | add `paths:` frontmatter and the likely paths — a diff of the rule itself |
| `CHANGELOG.md` with closed work | theses in `docs/roadmap/DONE.md`, two lines per item — a diff of the lines being added |
| `.claude/worktrees/` exists, no line in `.gitignore` | the line `.claude/worktrees/` at the end of `.gitignore` |

The format of the criterion line when carrying items over matters to the lint, not only to the
human: the `Done when:` line must contain exactly `not set` and nothing else. The carried-over
wording ("add PDF export", "piled up 10000 tasks") goes into the item's title or a separate line
below it, not inside the criterion line — otherwise its digits (if there are any there, but they
describe the problem rather than a measurement) will be taken by `roadmap_lint.py` for a
criterion that is set, and guardrail 1 stops being visible to the lint at step 3.

If there is one finding but several decisions inside it (three pieces to move out of a long
`CLAUDE.md`, for example) — then there are several questions too, and the human may accept some
and reject others. No candidate file for any row of the table, all five artifacts already in
place and `.claude/rules/context7.md` already there as well — report that the scaffold already
matches the reference, and stop the scenario without questions.

Nothing is written to any file that already exists without a question about that very file
(guardrail 3): a human's refusal or no answer — the file stays as it is, and that is a
legitimate outcome, not an error to be worked around next time.

`$ARGUMENTS` contains `--check` — the scenario stops here: no questions are asked, step 3
doesn't begin, the report ends with the list of proposals shown.

## Step 3. Applying and lint

Use the fact about the tree's cleanliness recorded in the survey at step 1 — don't recheck it
here: as soon as this very step creates the missing artifacts, `git status --porcelain` stops
being empty because of them, and a repeated check would wrongly block the diffs for the
findings, although they are not the cause.

Apply only what was accepted, and for each point look not at the category (a missing artifact or
a finding) but at the file itself (guardrail 2):

- **the file didn't exist and you create it from scratch** — the five base artifacts,
  `.claude/rules/context7.md` (if it was accepted and no docs server of the project's own was
  found, or the human agreed anyway), `ROADMAP.md` assembled from `TODO.md` if `ROADMAP.md`
  didn't exist yet, `docs/roadmap/DONE.md` from `CHANGELOG.md`. You don't check the tree from
  step 1 — there is nothing to overwrite, the rollback for such a file is `rm`. It was dirty —
  create them anyway, but warn the human in one line: these files will land on top of
  uncommitted changes;
- **the file already existed and you change it in place** — a long `CLAUDE.md`, a rule without
  `paths:`, appending a line to an existing `.gitignore`, an already existing `ROADMAP.md`.
  Apply only if the tree at step 1 was clean. It was dirty — don't apply this edit at all, tell
  the human to commit first and come back to this step; that doesn't roll back or touch the
  files created from scratch in the point above. The tree was clean — apply exactly as shown at
  step 2, don't make up anything on top (guardrail 1 holds here too: if the criterion arrived
  without a number, it stays without a number after applying);
- rejected or unanswered — don't touch them, even if the answer for a neighboring file in the
  same run was "yes".

The project now has a `ROADMAP.md` (created or edited) — run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/hooks/roadmap_lint.py ROADMAP.md
```

**Exit code zero** — say that the scaffold matches the reference, and what to do next:

- open `CLAUDE.md` and `ROADMAP.md`, replace the remaining placeholders with the project's data;
- fill in the criteria marked as not set (guardrail 1), if any are left;
- open the next real roadmap item with the skill `mast:managing-roadmap-items`;
- commit the result — `git diff` shows in full what the audit did.

**A non-zero code** — don't confuse the different cases:

- **A criterion deliberately left unset (guardrail 1).** The lint flags it as
  `"Done when" has no number` — that is the expected invitation for the human to fill it in, not
  a breakage of the applying.
- **A violation in a part of the file the human didn't accept at step 2.** It belongs to an
  untouched piece — show it as is, don't fix it silently: an edit without a question is
  forbidden by the same guardrail 3 as at step 2.
- **`ROADMAP.md` was created from `ROADMAP.template.md`.** That shouldn't happen: the English
  template is required to pass the lint (`tests/test_templates.py` checks exactly that). Show
  the violations and say plainly that the plugin's template is broken — that is a bug in the
  plugin, not in the project.
- Nothing of the above fits — this is a new violation from an applied edit, fix it: it means the
  diff at step 2 was inaccurate.
