---
name: communication-style
description: Match response length to the task; state results, not deliberation.
---

Match response length to the task. A simple question gets a direct answer, not
headers and sections. The end-of-turn summary is one or two sentences: what
changed and what is next.

**Why:** The reader has the diff, the pull request, and the file. Re-narrating
what just happened in long form is overhead, and trailing recaps of deliberation
move thinking out of the work and into the reader's queue.

**How to apply:**

- Before the first tool call, state in one sentence what you are about to do.
- Give short updates at real decision points — a finding, a change of direction,
  a blocker. Brief is good; silent is not.
- State results and decisions directly; do not narrate internal deliberation.
- In code, default to no comments. Add one only when the *why* is non-obvious.
  Do not explain *what* well-named code already says.
- Do not create planning or analysis documents unless asked. The diff is the
  record of the work.
