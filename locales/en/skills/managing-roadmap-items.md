# Roadmap items

**Core idea:** a decision not backed by a test, a number, or a CI check gets reverted by whoever didn't read the discussion. The skill keeps evidence at three points: the done criterion, the finding, the decision made.

This is a checklist, not a script for a reply: execute it, don't recount the reasoning.

## Who you are — what to read

| You are | Read in this skill |
|---|---|
| an item's session — in worktree `X-N` or marked `main copy` | the whole "Item session" section at the start; before closing, reread its "3. Closing" section |
| the main copy — the dispatcher `<project>-dispatch` or the human running the roadmap | the "Roadmap dispatcher" section, and the parts of "Item session" it refers to |

This part is shared by both: invariants, the line format, the archive, decisions.

## Invariants

- Only **the main copy** edits `ROADMAP.md`, `docs/roadmap/DONE.md`, and `TECH_DEBT.md`. Everything meant for them travels from an item's branch as a message to the dispatcher.
- **The main copy assigns the item's number** — the next free one across `ROADMAP.md` and `DONE.md`. A number from the archive is taken forever.
- **An item's session in a worktree never pushes to `main`** — only its own branch.
- **"Done when" holds a checkable number** — time, volume, count, size, a memory ceiling. ❌ "the PDF renders correctly" ✅ "500 rows < 3s, file < 2 MB".
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

# Item session

Read it in full at the start, reread section 3 before closing: the checklist is long, you won't get through it from memory. Invariants and the line format are in the "Roadmap items" section above.

## 1. Start

**Take the baseline measurement now, not at closing.** Run the scenario from "Done when" against the current code and record "before" together with the measuring command: in `Journal`, or in the body of the item's first commit if there's no `STATUS.md`. If the feature doesn't exist yet, say so: the command and "no, n/a". Without a "before", the decision stays just words.

**`STATUS.md` is opened only if at least one of these signs holds:**

1. a plan with several tasks is needed — call `writing-plans`;
2. the work will outlive a restart or `/compact` — you'll come back later, or the session has already been restarted;
3. a neighboring item is running on nearby paths — you need `Don't touch` and a log of agreements with the neighbor.

None of these — a line in the roadmap plus commits: decisions and small findings go into commit messages. A sign shows up along the way — open the file right then.

### If `STATUS.md` is opened

There's one path — `docs/roadmap/<item>/STATUS.md`. Create it with our header. If the `superpowers` plugin is installed, call `superpowers:writing-plans` saying "the file already exists at this path, add to it, don't change the path" (its default `docs/superpowers/plans/` isn't used). Without that plugin, write the tasks yourself, one checkable goal per task, and skip the `writing-plans` header line in the sample below. Then carry the rest forward.

```markdown
# B-4 Export reports to PDF
<writing-plans header: For agentic workers, Goal, Architecture, Tech Stack, Spec>

**My paths:** reports/**, api/routes/export.py         ← ours, copied from the roadmap line
**Don't touch:** everything else                        ← ours
**Done when:** 500 rows < 3s, file < 2 MB                ← ours, copied from the roadmap line

## Global Constraints / File Structure / Task 1..N       ← writing-plans

## Journal                                               ← ours
- 08.09 — storage layer, migration 052 (commit "[B-4] storage layer")
## Issues                                                ← ours
## Decisions made                                        ← ours
- reportlab over weasyprint — image <measurement> MB vs <measurement> MB
```

Don't duplicate `writing-plans`'s sections with your own: it has a proven task format, but the plan is static. Our sections are living: **`Journal` is written at the end of every step** — it's what restores context after `/compact` and a break. The journal holds commit topics, not hashes: rebase before merging changes hashes.

## 2. A finding outside the item

**The bar.** A new item — only if the fix goes beyond `My paths` or doesn't fit in the current session: it needs its own criterion with a number and its own measurement. Otherwise fix it where you are — a line in `Issues`, the chosen value (a timeout, a threshold) in `Decisions made`, and without a `STATUS.md` both go into the commit message. **If writing up the item costs more than fixing it — it isn't an item.**

Past the bar — all four steps, none skipped:

1. **An artifact, not words.** A test reproducing the problem, marked "expected to fail" (`xfail(strict=True)` in pytest or the equivalent): a plain failing test would block your merge. An architectural finding isn't caught by a test — then a measurement with a number: the scenario, the command, the result. Put the test where the tests for its area live — that's a legitimate exception to `My paths`. A separate commit `[B-4] finding: <description>`, containing only the test (and the inbox file, if there's no dispatcher) — the dispatcher will bring it into `main` via `cherry-pick`.
2. **Where else the same cause hides.** Check it, don't just note it: a token isn't revoked on a password change — check logout, deactivation, an email change, revoking access. The list of what was checked goes into the record.
3. **Urgency, with facts.** Logs, production, traces of exploitation, the number affected — one line with a figure, or "doesn't reproduce in prod".
4. **Get it to the main copy.** Don't assign a number, don't touch `ROADMAP.md` on your own branch. The record: the gist, the path to the test, the finding's branch and commit topic, places checked, urgency, the suggested section, `Depends on`, and "Done when" with a number.

| Situation | What to do |
|---|---|
| `<project>-dispatch` shows up in `ListAgents` | `SendMessage` it the record. The reply is the item's number, don't write the number anywhere before that. No reply by closing time — write it as a file in `docs/roadmap/inbox/` in a separate commit |
| no dispatcher, not urgent | a file `docs/roadmap/inbox/<DD.MM>-<word>.md` in the finding's commit — it arrives with the merge. Don't make up session names |
| urgent: production, active exploitation | tell the human right now, in a separate message, don't wait for a merge |

**Apply a mitigation on your own paths, don't just propose it** — a cheap temporary softening (a shorter TTL, a disabled flag) marked "temporary": a mitigation that's proposed but not applied protects nothing. A mitigation on someone else's paths goes into the record. Don't drop your own task.

## 3. Closing

Closed means everything below is done, **in this order**: the measurement is taken on the code that will actually be merged, i.e. after the rebase.

- [ ] **Decisions are sorted** by the "Decisions" table in the "Roadmap items" section above. "Decisions made" is filled in, each with a reason and its own number; without a `STATUS.md` they're already in the commits. Decisions that clear the ADR bar go into all three places; none did — skip this step.
- [ ] **Loose ends are resolved:** small stuff on your own paths — finish it; past the bar — file it as a finding per section 2; left crooked on purpose — a record for `TECH_DEBT.md` in the message to the dispatcher. Neither one nor the other — not closed.
- [ ] **A rule for the agent is proposed.** The item taught you something that will come up again — propose one edit to `.claude/rules/<subsystem>.md` with `paths:` (no such file — create it). No rule is needed — say so explicitly; silence doesn't count as an answer: rules either grow with the code or fall behind it forever.
- [ ] **The changelog and user docs are updated**, or split off into a separate item through the dispatcher. A feature the user never learned about isn't done.
- [ ] **Archive:** `git mv docs/roadmap/B-4 docs/roadmap/done/B-4` on your branch. There was no folder — skip this.
- [ ] **Fresh `main`:** `git fetch origin && git rebase origin/main` (here and below, `main` is your repository's default branch; yours may be named differently, e.g. `master`), the **whole project test suite** is green, not just the item's tests, `git status` is clean. After the rebase, push your branch with `git push --force-with-lease origin worktree-B-4` — this isn't a question for the human, there are no foreign commits on it.
- [ ] **"After" measurement** — on the code after the rebase, with the same command as "before": before → after. "Before" wasn't taken — measure it on the commit right before the item's first one.
- [ ] **The last commit carries everything for the archive** — messages are lost when the dispatcher restarts, commits aren't. In its body:
  - the "Done when" block **verbatim** from `ROADMAP.md` in `origin/main` (it may have changed while you worked) with before → after measurements and the command. With a `STATUS.md` — also into its header. Copy it, don't paraphrase it: the roadmap line will be deleted;
  - a draft thesis for `DONE.md` — two lines: what changed and the main number, links to `STATUS.md` and an ADR if there is one. Without the range — only the main copy knows it;
  - entries for `TECH_DEBT.md`, if any remain.

  Nothing left to commit — `git commit --allow-empty`.
- [ ] **A message to the dispatcher** (no dispatcher — to the human): "B-4 is ready, branch `worktree-B-4` on a fresh main, measurements: before → after", and the same text as in the last commit. Don't touch the branch after that. A "not fast-forward" reply — repeat the rebase, the tests, and the message.

## Common mistakes

| Mistake | What it leads to |
|---|---|
| A finding recorded in words, without a test or a measurement | it can't be confirmed a month later |
| The symptom was checked, not the cause | the same hole shows up nearby |
| Small stuff on your own paths was opened as an item | the roadmap grows faster than it closes |
| A mitigation was proposed but not applied | a feeling of protection with no protection |
| The criterion was paraphrased instead of carried over verbatim | measurements drift from what was agreed |
| Only the item's tests ran before merging | the shared run is broken, a chain of fixes trails the item |

# Roadmap dispatcher

You are the main-copy session `<project>-dispatch`. The only one who edits `ROADMAP.md`, `DONE.md`, and `TECH_DEBT.md`, and merges items' branches. Invariants, the line format, and the archive are in the "Roadmap items" section above, an item session's path is in the "Item session" section above, here is everything the main copy does.

**State isn't in your context.** After a restart, rebuild it from `ROADMAP.md`, `claude agents`, `git worktree list`, `ls docs/roadmap/inbox/`. Don't take the marks in `ROADMAP.md` on faith — the first thing is checking for abandoned items.

## Abandoned items

After every restart, and before starting any new session, cross-check three sources:

```bash
claude agents --json --all | jq -r '.[] | select(.state=="working" or .state=="blocked" or .status!=null) | .name'  # alive; no jq — the same by eye in `claude agents --all`
grep -n 'in progress' ROADMAP.md   # who's listed as in progress
git worktree list                  # what's on disk
```

| Mismatch | What it means |
|---|---|
| an item is "in progress", its session isn't among the alive ones | abandoned: the session crashed or finished without closing the item (its `state` is `done`, `failed`, or `stopped`) |
| a worktree exists, no item is "in progress" for it | orphaned: the item was closed or dropped and the worktree stayed |
| a live session named after an item that isn't "in progress" | stray: it will hold the name, and a new session for that item gets a suffix |

Don't delete anything yourself: a worktree may hold uncommitted changes. Send the human one message listing the mismatches, with an option for each: resume (`claude attach <id>` or `claude respawn <id>`), close, drop.

## When to ask the human

| Ask | Decide yourself |
|---|---|
| change an item's "Done when" | a duplicate → add to the existing item |
| drop an item, merge items with different goals | a section, a number, `Depends on` for a new finding |
| two in-progress items touch the same paths — which to stop | split a finding into items, if all of them share one goal |
| delete a branch with unmerged commits, force-push | the order of starting and merging |
| an urgent finding (production, active exploitation) — right away, in a separate message | send a finding back to its sender for a test or a number |
| a mitigation users will notice | `Depends on` for new items and for items waiting on them |
| an abandoned item, an orphaned worktree, a stray session — resume, close, or drop | |
| | send an item back for more work if there are no measurements in the journal or the commits |

A question to the human is one message: facts with numbers (no numbers — ask the item's session for them first), 2–3 options, your recommendation. While you wait for a reply, don't touch the line, the item keeps going. Decided it yourself — the reason goes in the commit message.

## Triaging findings

Sources: `SendMessage` from sessions, and files in `docs/roadmap/inbox/` — they arrive with merges, check the folder after each one.

1. **Does it need an item at all?** The bar is the "2. A finding outside the item" section of "Item session" above: either the finding is outside the sender's `My paths`, or it doesn't fit in their session. Small stuff on their own paths with no number-backed criterion of its own — send it back: let them fix it where they are and write it into `Issues` or the commit message. A roadmap that grows faster than it closes is useless.
2. **Is there a test?** For an architectural finding — a measurement with a number and a command. Neither one — send it back.
3. **A duplicate?** `grep -in '<keywords>' ROADMAP.md docs/roadmap/DONE.md` → add to the item found and check that its "Done when" already covers the finding with a number. Found in `DONE.md` — check which section. Among the closed items it means the same problem came back: a new item linking to the old one, the old one isn't reopened. In the "Dropped" subsection it means this was already tried and rejected — that's a question for the human (see the table "When you ask the human"), not a new item of your own.
4. **A new item:** the section by topic; the number is the next free one **across both files** (`grep -n '^- \*\*B-' ROADMAP.md docs/roadmap/DONE.md`), a number from the archive is taken forever; `Depends on`; "Done when" with a number — no number, ask the sender for one. A large finding — several items, each with its own criterion.
5. **The test goes into `main` together with the line.** Otherwise the item lands in `--ready` before its test reaches `origin/main`.
   - The finding arrived via `SendMessage` — its commit holds only the test, take it:
     ```bash
     git cherry-pick -n $(git log worktree-B-4 --format=%h --grep='finding: <topic>' -1)
     ```
     The sender's branch will drop the transplanted commit on its own during rebase.
   - The finding sits in `inbox/` — it arrived with the branch merge along with its own test, no `cherry-pick` needed. Remove the inbox file with `git rm` in the commit that opens the item.
6. **Check and commit:** `python3 ${CLAUDE_PLUGIN_ROOT}/hooks/roadmap_lint.py ROADMAP.md` → commit → `git push`. The reply to the sender is the item's number.

Commit messages: `[B-2] opened: …`, `[A-2] finding added: …`, `[B-2] taken into work · <model>`, `[B-2] closed`, `[A-3] criterion changed by human decision: …`.

## Which model an item gets

By default the item is driven by a stronger model. Downgrading to a more economical one — only when the answer is "yes" to all three questions:

1. **Discoverability.** A wrong result is caught by checking against something that already exists: a test, a linter, CI, a measurement, code, a spec, an ADR.
2. **Reversibility.** It reverts with a single `git revert`, without data loss and without action outside the repository.
3. **Blast radius.** Only this item suffers, not every future session, user, or piece of data.

Missing even one — the stronger model. **When in doubt — the stronger model:** redoing one item costs more than the price gap between models.

The rule rests on the properties of the error, not on the names of areas, so it works in any project. Documentation splits along the same first question: "add a section about existing code", "fix a stale fragment", "tests for a criterion where the number is already written" — the more economical model; "describe the architecture, behavior, invariants, an API contract" — the stronger model, because there's nothing to check it against: the text itself becomes the source of truth.

**Always the stronger model, in any project:** files that agents read as rules — `CLAUDE.md`, `.claude/rules/`, skills, prompts. An error in them silently changes the behavior of every future session — the largest blast radius in this scheme.

**An item's session has an advisor** — a model one tier above the executor: the `--advisor <model>` flag at startup, or `advisorModel` in Claude Code settings. The executor calls it itself — before committing to an approach, and before declaring the item done. Downgrading the item's model doesn't downgrade the advisor: that's the point, the stronger model catches what the cheaper one missed. Which two models exactly — the project declares in `.claude/rules/dispatch.md` next to its zones; no such file — both come from Claude Code settings.

**The project declares sensitive zones**, not this skill: `<project>/.claude/rules/dispatch.md`, one line per zone — `auth/** · billing/** · db/migrations/** — stronger model only`. No file — everything goes on the stronger model: a project opts into the more economical one deliberately, it isn't the default. The file exists, even with no zones — the more economical model is allowed under the three questions.

## Starting an item

1. **What can be taken:** `python3 ${CLAUDE_PLUGIN_ROOT}/hooks/roadmap_lint.py --ready ROADMAP.md`. Don't run two items in parallel whose `My paths` overlap.
2. **The line** — per the format in the "Roadmap items" section above: session `B-2`, `My paths`. `STATUS.md` — only if there's a sign from the "1. Start" section of "Item session"; the signs "needs a plan" and "a neighbor on nearby paths" are already visible at start time. Commit `[B-2] taken into work · <model>` and `git push` — the model goes in the message, so it's visible at closing time who did the work. All of this **before the session starts**: from inside the worktree, edits to the main copy are blocked, and the worktree is created from `origin/main` — without a push it won't see its own line.
3. **Start:**
   ```bash
   claude --bg --worktree B-2 --name B-2 "Drive item B-2 per skill mast:managing-roadmap-items: a line in ROADMAP.md and docs/roadmap/B-2/STATUS.md if it's opened. First step — the baseline measurement"
   ```
   An item that went through the downgrade — same flags, but with `--model <economical model>`.
   The command prints an id. The name might already be taken by an old live session — the engine then hands out `B-2-<word>`. That's a symptom of an abandoned item: deal with the old session (see "Abandoned items"), don't just record the suffix.
4. **After the start:** send the human the id and `claude attach <id>`.

## Merging

An item's session writes "ready, branch on a fresh main". Queue rules:
- **Ready branches before your own commits.** Any commit of yours on `main` breaks fast-forward for a branch that already rebased.
- **One branch at a time.** Every merge shifts `main`, and the next branch needs its own rebase.
- **Measurements first.** `git log --format=%B origin/main..worktree-B-2` (and `STATUS.md`, if there is one): "before" from the date taken, and "after" with the measuring command. Numbers with no command — send the item back for more work. Numbers matching the skill's example is a reason to check the command, not a verdict.

Order:

1. **Merge:** `git merge --ff-only worktree-B-4`. Not fast-forward — the item's session repeats the rebase.
2. **The range — right after the merge, and check it's clean:**
   ```bash
   git log --format=%h -1 ORIG_HEAD; git log --format=%h -1 HEAD
   git log --format=%s ORIG_HEAD..HEAD | grep -vc '^\[B-4\]'   # 0 — only the item's commits are in range
   ```
   Not 0 — foreign commits got into the branch, and `git diff` over the range will show more than this item. Don't write the range in that case, use `git log --grep='\[B-4\]'` in the thesis instead.
   
   When an item merges in multiple passes (the branch was merged twice, or part of it was done on the main copy), the thesis lists several ranges separated by commas; each is checked for cleanliness in isolation. If any one is dirty — use `git log --grep` for all of them instead.
3. **The thesis in `DONE.md` first, then remove the line from `ROADMAP.md`.** In the reverse order, the hook would briefly see items with `Depends on: B-4` pointing at nothing. The thesis is a draft from the session, taken from the body of the branch's last commit plus the range — no need to retell the item. The section is its own letter (a heading like in the roadmap, none exists — create one), the date is the day of the merge, links to `STATUS.md` and an ADR — if they exist:
   ```markdown
   - **B-4** Export reports to PDF — 17.09 · `a1b2c3d..e4f5a6b` · [STATUS](done/B-4/STATUS.md) · [ADR](../adr/B-4-reportlab.md)
     A 500-row report renders in 8.2s → 2.4s, peak memory 210 MB.
   ```
   Entries for `TECH_DEBT.md` come from the same place — the same commit `[B-4] closed`, then `git push`: otherwise waiting sessions will rebase without this item. A debt entry missing "what it risks" or "the condition that triggers a fix" — send it back to the session, don't guess.
4. **Clear blockers:** `grep -niE 'Depends on:.*\bB-4\b' ROADMAP.md` — tell live sessions of those items "B-4 is in origin/main, rebase", and the ones that became ready go into the launch queue.
5. **Clean up:** `claude rm <id>` (the session and the worktree) or `git worktree remove .claude/worktrees/B-4`, then `git branch -d worktree-B-4` and `git push origin --delete worktree-B-4` — the item's session pushed its own branch, and on `origin` it would otherwise stay forever.

**A dropped item goes to the same place.** Its line is removed from `ROADMAP.md`, and `DONE.md` gets a "Dropped" subsection with one line in it: number, title, date, the reason, and where the work moved if another item took it over. The `docs/roadmap/<X-N>/` folder, if one was opened, moves along with it into `done/<X-N>/` — otherwise the link in the "Dropped" line is broken; there was no folder, so there is no link. That way the archive answers not only "has this been done already?" but also "has this been tried and rejected?" — otherwise what was rejected lives only in an ADR, if one was written, and six months later the same item is opened again.

After merging:
- `ls docs/roadmap/inbox/` — the branch may have brought findings;
- `python3 ${CLAUDE_PLUGIN_ROOT}/hooks/roadmap_lint.py ROADMAP.md` — also flags theses with broken links to `done/`;
- `python3 ${CLAUDE_PLUGIN_ROOT}/hooks/roadmap_lint.py --ready ROADMAP.md` — what's now ready to start.

## Common mistakes

| Mistake | What it leads to |
|---|---|
| Started a session before pushing the line | a worktree from `origin/main` doesn't see its own line, the session takes the item again |
| Merged two branches in a row without rebasing the second one | not fast-forward, or changes silently mixed together |
| Asked the human about a duplicate or a number | the human gets pinged over mechanics, an important question drowns |
| Opened an item for small stuff the sender could've fixed on their own | the roadmap grows faster than it closes |
| Handed the economical model work where text becomes the source of truth | there's nothing to check the error against, it propagates through links |
| Left a closed item in `ROADMAP.md` | the working file bloats, `--ready` drowns in what's already done |
| Changed "Done when" on your own | acceptance runs against a criterion the human never agreed to |
| Kept the queue in your head instead of in `ROADMAP.md` | the queue is lost on restart |
