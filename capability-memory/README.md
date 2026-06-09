# capability-memory

Operating rules, versioned in this repository. Every Markdown file here (except
this README) is concatenated by `bridge/capability_context.py` and prepended to
the system prompt of every task.

A rule is generic operating knowledge — how the agent should work — with no
project-, client-, or instance-specific detail. Editing a rule changes how every
future task behaves, and the change is reviewable as a diff.

Each file:

```markdown
---
name: <kebab-case-slug>
description: <one-line summary>
---

<the rule, with a short why and how-to-apply>
```
