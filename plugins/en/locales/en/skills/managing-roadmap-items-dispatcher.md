# Roadmap dispatcher

You are the main-copy session `<project>-dispatch`. The only one who edits `ROADMAP.md`, `DONE.md`, and `TECH_DEBT.md`, and merges items' branches. Invariants, the line format, and the archive are in `managing-roadmap-items.md`, read before this file; an item session's path is in `managing-roadmap-items-item.md` next to it — open it via the links from here. Here is everything the main copy does.

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

A question to the human is one message **as text, not `AskUserQuestion`**: a modal question holds both merges and incoming messages from sessions until the human answers. In a `*-dispatch` session the plugin's hook denies `AskUserQuestion`, and also Edit/Write in the main copy outside `ROADMAP.md`, `docs/roadmap/**` and `TECH_DEBT.md`: a small fix outside the roadmap — via an `Agent` subagent with `isolation: "worktree"`, you merge its branch yourself. In the message — facts with numbers (no numbers — ask the item's session for them first), 2–3 options, your recommendation. A question or a finding from an item's session isn't forwarded as is — you rewrite it by the invariant on messages to the human in `managing-roadmap-items.md` next to this file. A question about an item also goes into its line as the last slot — `· waiting on human: <question>`; that's the only edit to the line while you wait, and the item keeps going meanwhile. "What do you need from me" — `python3 ${CLAUDE_PLUGIN_ROOT}/hooks/roadmap_lint.py --waiting ROADMAP.md`. Got the answer — remove the slot. Decided it yourself — the reason goes in the commit message.

## Triaging findings

Sources: `SendMessage` from sessions, and files in `docs/roadmap/inbox/` — they arrive with merges, check the folder after each one.

1. **Does it need an item at all?** The bar is the "2. A finding outside the item" section of `managing-roadmap-items-item.md` next to this file: either the finding is outside the sender's `My paths`, or it doesn't fit in their session. Small stuff on their own paths with no number-backed criterion of its own — send it back: let them fix it where they are and write it into `Issues` or the commit message. A roadmap that grows faster than it closes is useless.
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

By default the item is driven by `opus` with `fable` as its advisor. Downgrading to `sonnet` with `opus` as advisor — only when the answer is "yes" to all three questions:

1. **Discoverability.** A wrong result is caught by checking against something that already exists: a test, a linter, CI, a measurement, code, a spec, an ADR.
2. **Reversibility.** It reverts with a single `git revert`, without data loss and without action outside the repository.
3. **Blast radius.** Only this item suffers, not every future session, user, or piece of data.

Missing even one — `opus`. **When in doubt — `opus`:** redoing one item costs more than the price gap between models.

The rule rests on the properties of the error, not on the names of areas, so it works in any project. Documentation splits along the same first question: "add a section about existing code", "fix a stale fragment", "tests for a criterion where the number is already written" — `sonnet`; "describe the architecture, behavior, invariants, an API contract" — `opus`, because there's nothing to check it against: the text itself becomes the source of truth.

**Always `opus`, in any project:** files that agents read as rules — `CLAUDE.md`, `.claude/rules/`, skills, prompts. An error in them silently changes the behavior of every future session — the largest blast radius in this scheme.

**The advisor is set at startup** — the `--advisor <model>` flag, or `advisorModel` in Claude Code settings. The executor calls it itself: before committing to an approach, and before declaring the item done.

**The project declares sensitive zones**, not this skill: `<project>/.claude/rules/dispatch.md`, one line per zone — `auth/** · billing/** · db/migrations/** — opus only`. No file — everything goes on `opus`: a project opts into `sonnet` deliberately, it isn't the default. The file exists, even with no zones — `sonnet` is allowed under the three questions.

Don't give `fable` as advisor to a session running `sonnet`: subagents inherit the session's advisor, Fable multiplies across them and ends up costing more than `opus` would have.

## Starting an item

1. **What can be taken:** `python3 ${CLAUDE_PLUGIN_ROOT}/hooks/roadmap_lint.py --ready ROADMAP.md`. Don't run two items in parallel whose `My paths` overlap.
2. **The line** — per the format in `managing-roadmap-items.md`: session `B-2`, `My paths`. The description carries the context of your conversation with the human: why the item exists, which options were rejected and why, what constraints they set. The start prompt is gone once sent, while the session rereads the line even after a restart. Don't write the plan or pick the implementation: the item's session does that after studying the code. Commit `[B-2] taken into work · <model>` and `git push` — the model goes in the message, so it's visible at closing time who did the work. All of this **before the session starts**: from inside the worktree, edits to the main copy are blocked, and the worktree is created from `origin/main` — without a push it won't see its own line.
3. **Start:**
   ```bash
   claude --bg --worktree B-2 --name B-2 --advisor fable "Drive item B-2 per skill mast:managing-roadmap-items: its line in ROADMAP.md. First step — the baseline measurement. No neighbors on nearby paths in progress"
   ```
   After the template — coordination facts only: neighbors on nearby paths in progress and their session names (the session negotiates with them directly), windows on shared resources, what moved in `main`. An item that went through the downgrade — same flags, but with `--model sonnet --advisor opus`.
   The command prints an id. `--advisor fable` gives the session a stronger advisor at the key points; if consent to bill Fable hasn't been given yet, the background session simply starts without an advisor. The name might already be taken by an old live session — the engine then hands out `B-2-<word>`. That's a symptom of an abandoned item: deal with the old session (see "Abandoned items"), don't just record the suffix.
4. **After the start:** send the human the id and `claude attach <id>`.

## Merging

The item's session says "ready" — you merge from the main copy with one command:

```bash
mast merge B-4            # push not allowed — add --no-push
```

The script checks the form, not the truth: fast-forward, only `[B-4]` in the range, the branch left `ROADMAP.md`, `DONE.md` and `TECH_DEBT.md` alone, the last commit has "Done when" verbatim, "before → after" and a thesis. A refusal changes nothing: the reason goes to the item's session, "part of the work is already in main" — merge by hand with the human. Passed — a commit `[B-4] closed` with the thesis, the line and the debt, push, cleanup of the session, worktree and branch. Ready branches this merge moved are merged next after a rebase and the tests from the `Tests:` line in `.claude/rules/dispatch.md`; if that fails, the output has a text for their session. The rest of the output — whom to tell "rebase", what is ready to take, `inbox/`.

## Dropping an item

**A dropped item goes to the archive too** — by hand, `mast merge` doesn't drop. Its line is removed from `ROADMAP.md`, and `DONE.md` gets a "Dropped" subsection with one line in it: number, title, date, the reason, and where the work moved if another item took it over. The `docs/roadmap/<X-N>/` folder, if one was opened, moves along with it into `done/<X-N>/` — otherwise the link in the "Dropped" line is broken; there was no folder, so there is no link. That way the archive answers not only "has this been done already?" but also "has this been tried and rejected?" — otherwise what was rejected lives only in an ADR, if one was written, and six months later the same item is opened again.

## Common mistakes

| Mistake | What it leads to |
|---|---|
| Started a session before pushing the line | a worktree from `origin/main` doesn't see its own line, the session takes the item again |
| Merged a branch by hand, `git merge` instead of `mast merge` | thesis, line and debt become three edits, the lint complains about the in-between state, cleanup gets forgotten |
| Asked the human about a duplicate or a number | the human gets pinged over mechanics, an important question drowns |
| Opened an item for small stuff the sender could've fixed on their own | the roadmap grows faster than it closes |
| Handed `sonnet` work where text becomes the source of truth | there's nothing to check the error against, it propagates through links |
| Gave a session running `sonnet` the `fable` advisor | subagents inherit the advisor, so it costs more than `opus` would have |
| Left a closed item in `ROADMAP.md` | the working file bloats, `--ready` drowns in what's already done |
| Changed "Done when" on your own | acceptance runs against a criterion the human never agreed to |
| Kept the queue in your head instead of in `ROADMAP.md` | the queue is lost on restart |
