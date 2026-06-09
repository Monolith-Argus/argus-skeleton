# argus

A Slack-driven coding agent. A bridge process listens on Slack, classifies each
message, selects a model, and runs the [Claude Code](https://github.com/anthropics/claude-code)
CLI inside a per-message Docker container. The agent's own source tree is one of
its memory layers: it edits `bridge/`, `scheduler/`, `capability-memory/`, and
`docker/` through pull requests, the same way it edits any other repository. Task
metadata and schedules live in SQLite alongside that.

## Components

| Path | Purpose |
|------|---------|
| `bridge/bridge.py` | Slack Socket Mode listener; per-message container spawn; concurrency limit |
| `bridge/router.py` | Model + iteration-budget selection per message |
| `bridge/classifier.py` | Intent classification (Haiku) used by the router |
| `bridge/db.py` | SQLite access for tasks and schedules |
| `bridge/secrets.py` | Redaction of tokens before any user-facing output |
| `scheduler/run_scheduled_job.py` | Cron entry point for recurring jobs |
| `scheduler/sinks.py` | Output sinks (Slack, file) for scheduled job results |
| `docker/Dockerfile` | Task container image |
| `docker/entrypoint.sh` | Container entry: auth, repo clone, `claude` invocation |
| `capability-memory/` | Markdown operating rules injected into every task's system prompt |
| `migrations/` | Idempotent SQLite schema |

## Memory layers

Three stores, read at different points:

- **SQLite** (`migrations/`, `bridge/db.py`) — structured task and schedule
  records. Conventional database.
- **Capability memory** (`capability-memory/*.md`) — operating rules versioned in
  this repository and injected into the system prompt of every task. Changing a
  rule is a commit.
- **Source tree** — the agent modifies its own `bridge/`, `scheduler/`, and
  `docker/` code via branches and pull requests. Behavior persists by being
  committed, not by being held in a database.

## Runtime

For each Slack message the bridge:

1. Checks the sender against `ALLOWED_SLACK_USERS`.
2. Classifies the message (`bridge/classifier.py`) and routes it to a model and
   iteration budget (`bridge/router.py`).
3. Writes a `tasks` row and spawns a container:

   ```
   docker run --rm \
     --memory 500m \
     -v <workspace>:/workspace \
     -v <agent-home>:/tmp/argus-home \
     -e REPO=<org/name> \
     -e ARGUS_MODEL=<model> \
     argus-agent:latest "<prompt>"
   ```

4. `docker/entrypoint.sh` configures git auth, clones the target repo into
   `/workspace`, injects `capability-memory/` into the system prompt, and execs
   `claude --print --output-format stream-json`.
5. The bridge reads the stream, posts the result to the originating thread, and
   updates the `tasks` row with cost and exit code.

`/workspace` and the agent home directory persist across containers; everything
else is fresh per task.

## Configuration

Copy `.env.example` to `.env` and set:

| Variable | Purpose |
|----------|---------|
| `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN` | Slack Socket Mode credentials |
| `ALLOWED_SLACK_USERS` | Comma-separated Slack user IDs permitted to invoke the agent |
| `CLAUDE_CODE_OAUTH_TOKEN` | Auth for the `claude` CLI in task containers |
| `ANTHROPIC_API_KEY` | Used only by the classifier/router (Haiku) on the bridge |
| `GITHUB_TOKEN`, `GITHUB_USER`, `GITHUB_EMAIL` | Git auth and commit identity in containers |
| `ARGUS_DEFAULT_REPO` | Repo cloned when a message names no other |
| `DB_PATH` | SQLite path (default `./argus.db`) |
| `DOCKER_IMAGE` | Task image tag (default `argus-agent:latest`) |
| `MAX_CONCURRENT_TASKS` | Container concurrency limit |

The two credentials are not interchangeable: `CLAUDE_CODE_OAUTH_TOKEN` is the only
auth path for task inference; `ANTHROPIC_API_KEY` is read only by the bridge-side
classifier and router.

## Build and run

```
# Build the task image
docker build -t argus-agent:latest -f docker/Dockerfile .

# Apply schema and start the bridge
pip install -r requirements.txt
python -m bridge.db            # initialise SQLite
python -m bridge.bridge        # start the Slack listener
```

Schedules are stored in the `schedules` table and fired by
`scheduler/run_scheduled_job.py` from cron.

## License

Apache 2.0. See `LICENSE`.
