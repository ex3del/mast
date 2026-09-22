---
paths:
  - "**/*.{js,jsx,ts,tsx,py,go,rs,java,rb,php,cs,cpp,c,h,swift,kt}"
---

# Library docs — through the tool, not from memory

- For API syntax, configuration, version-migration and install questions
  about libraries, frameworks, SDKs and CLIs — check a documentation-lookup
  tool first, not memory: it can be stale.
- Don't use this for refactoring, debugging your own business logic, or
  general programming questions — no documentation tool needed there.

## The order

1. Look the library up by its name **and your question** — you get its id in the
   catalog (with Context7, which ships with the plugin, that's `resolve-library-id`).
   Take the exact name match, and the version if one was named.
2. Ask for the docs by that id and with the **full question**, not a single word
   (`query-docs`).
3. The answer didn't satisfy — repeat the same query in research mode
   (`researchMode: true`): it costs more, but it reads the repositories' sources
   and a live web search. That retry comes **before** answering from memory, not after.
