# <Project name>

<One or two lines: what this project is and who it's for.>

## Where to look

| Document | When to read |
|---|---|
| [ROADMAP.md](ROADMAP.md) | what's left to do |

## Stack

- <language, framework, database — what the project runs on>

## Commands

```bash
<test command>
<lint or build command>
```

## Code

- **On an unexpected state, fail loudly or return an explicit `unknown`.** A bare `except`,
  a default in place of an error, `return None` in place of a check — the program keeps
  running on wrong data, and the failure surfaces far from its cause.

## Project invariants

- <a rule that must never break silently>

**Keep this file under 200 lines.** Reference material — architecture, schemas, cards — goes in
`docs/`; agreements about a specific folder go in `.claude/rules/*.md` with `paths:`.
