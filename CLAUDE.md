# Argus — Agentic Recursive Generator of Unique States

Argus is a Slack-driven coding agent that runs on the Claude Code CLI. A bridge
process spawns a container per Slack message; inside that container, the `claude`
CLI does the work. This file documents how the agent operates on its own repo.

The source tree is the primary output medium for self-change. When a conversation
asks for a behavior change — routing logic, classification rules, output formatting,
scheduling — the agent edits this codebase, opens a pull request, and merges it.
The changed code runs in the next container. Natural language in; different agent
out. This is what "agentic recursive" means in practice. The `claude` binary itself
is not modifiable from inside the container; everything else is.

## Architecture

```
bridge/bridge.py        Slack Socket Mode listener; container spawn; concurrency
bridge/router.py        Model + iteration-budget selection
bridge/classifier.py    Intent classification (Haiku)
bridge/db.py            SQLite access for tasks and schedules
bridge/secrets.py       Token redaction before user-facing output
scheduler/              Cron-driven recurring jobs
docker/                 Task container image + entrypoint
capability-memory/      Operating rules injected into every task's system prompt
migrations/             Idempotent SQLite schema
```

For each Slack message, `bridge.py` runs:

```
docker run --rm --memory 500m \
  -v <workspace>:/workspace \
  -v <agent-home>:/tmp/argus-home \
  -e REPO=<org/name> -e ARGUS_MODEL=<model> \
  argus-agent:latest "<prompt>"
  -> docker/entrypoint.sh
  -> claude --print --output-format stream-json --dangerously-skip-permissions
```

## Memory layers

| Layer | Store | Changed by |
|-------|-------|-----------|
| Structured | SQLite (`migrations/`, `bridge/db.py`) | `INSERT`/`UPDATE` at runtime |
| Operating rules | `capability-memory/*.md` | A commit to this repo |
| Behavior | Source tree (`bridge/`, `scheduler/`, `docker/`) | A branch + pull request |

`capability-memory/` is read by `bridge/capability_context.py` and prepended to
the system prompt of every task. A rule is a Markdown file with front matter;
adding or editing one changes how every future task behaves, and the change is
reviewable as a diff.

## Conventions

- Python 3.12, type hints on function signatures, `from __future__ import annotations`
  at the top of every module.
- Async only in `bridge.py`; sync everywhere else.
- Logging namespaced under `argus.`: `log = logging.getLogger("argus.<module>")`.
- Call `bridge.secrets.redact()` before any user-facing output. Never log raw
  tokens.
- Schema changes: add a new idempotent `migrations/00X_name.sql`.
- New Slack commands: extend the dispatch chain in `bridge/bridge.py`.

## Auth

Two credentials, not interchangeable:

| Credential | Use |
|------------|-----|
| `CLAUDE_CODE_OAUTH_TOKEN` | The `claude` CLI in task containers — the only path for task inference |
| `ANTHROPIC_API_KEY` | The bridge-side classifier and router (Haiku) only |

If `CLAUDE_CODE_OAUTH_TOKEN` is missing, the container refuses to start rather
than falling back to the API key.

## Commit and PR style

- First line: imperative present-tense verb, ≤ 72 chars.
- Branch name: `<area>/<short-description>`.
- PR body: a short Summary and a Test plan; no narrative prose.
