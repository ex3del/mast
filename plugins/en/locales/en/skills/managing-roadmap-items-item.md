# Item session

Read it in full at the start, reread section 3 before closing: the checklist is long, you won't get through it from memory. Invariants and the line format are in `managing-roadmap-items.md` next to this file — it's read before this one.

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

- [ ] **Decisions are sorted** by the "Decisions" table in `managing-roadmap-items.md`. "Decisions made" is filled in, each with a reason and its own number; without a `STATUS.md` they're already in the commits. Decisions that clear the ADR bar go into all three places; none did — skip this step.
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
