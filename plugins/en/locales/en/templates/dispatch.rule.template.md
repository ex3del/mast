---
paths:
  - "<sensitive folder>/**"
---

# Models and sensitive zones

Zones that always run on `opus`, one line per zone — the path and what an error there costs:

- `<path/**>` — opus only: <why getting this wrong is expensive>

**While this file doesn't exist, everything runs on `opus`.** It exists precisely to allow
`sonnet` where that is safe: the error is discoverable by checking against something that
already exists, it reverts with a single `git revert`, and it hits exactly one item. Those
three conditions live in the roadmap-items skill.

The advisor: `opus` gets `fable`, `sonnet` gets `opus`. Don't give `fable` as advisor to a
session running `sonnet`: subagents inherit the session's advisor, Fable multiplies across
them and ends up costing more than `opus` would have.

The paths in `paths:` are those same sensitive zones: the rule then arrives in the context by
itself once an agent reaches them. The dispatcher reads this file by name, before starting a
session.

Silence threshold: 30 min

`mast status` flags an item session with no new commit for longer than this. The flag blocks
nothing: a false alarm costs more than slow detection. Without this file the threshold is the same.

Restart threshold: 500k tokens

After `mast merge` a dispatcher whose context exceeds the threshold gets a hint: restart with
`/clear`. 500k is measured on a 1M window: auto-compaction there hits at 667k, and between
merges the context grew by up to 162k. For a model with a smaller window, set the threshold
below its auto-compaction. Without this file the threshold is the same.
