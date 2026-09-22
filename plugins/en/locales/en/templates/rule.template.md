---
paths:
  - "<folder>/**"
---

# <rule topic>

- <one rule: what always happens here and why>

<!-- A protected path is the same kind of rule, only it forbids:

       paths: ["migrations/**"]
       "Migrations are applied in production. Never edit existing files — add new
        ones. Need to change an applied migration — ask a human."

     Access itself is not restricted, and cannot be: the agent reads anything it
     likes. The rule simply lands in its context at the moment it reaches for
     those files. The immunity boundary is text, not a mechanism. -->
