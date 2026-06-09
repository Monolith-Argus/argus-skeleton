"""Slack Socket Mode listener and per-message task dispatcher.

For each authorized message the bridge classifies and routes it, writes a task
row, spawns a Docker container running the ``claude`` CLI, reads the stream-json
output, and posts the terminal result back to the originating thread.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time

from slack_bolt.app.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from . import db, router, secrets

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("argus.bridge")

ALLOWED_SLACK_USERS = {
    u.strip() for u in os.environ.get("ALLOWED_SLACK_USERS", "").split(",") if u.strip()
}
DEFAULT_REPO = os.environ.get("ARGUS_DEFAULT_REPO", "")
DOCKER_IMAGE = os.environ.get("DOCKER_IMAGE", "argus-agent:latest")
MAX_CONCURRENT = int(os.environ.get("MAX_CONCURRENT_TASKS", "3"))
TASK_MEM = os.environ.get("TASK_MEM", "500m")

WORKSPACE_ROOT = os.environ.get("ARGUS_WORKSPACE_ROOT", "/var/lib/argus/workspaces")
AGENT_HOME_DIR = os.environ.get("ARGUS_AGENT_HOME_DIR", "/var/lib/argus/agent-home")

GITHUB_USER = os.environ.get("GITHUB_USER", "")
GITHUB_EMAIL = os.environ.get("GITHUB_EMAIL", "")

app = AsyncApp(token=os.environ.get("SLACK_BOT_TOKEN"))
_sem = asyncio.Semaphore(MAX_CONCURRENT)


def is_authorized(user_id: str) -> bool:
    return user_id in ALLOWED_SLACK_USERS


def new_task_id() -> str:
    return time.strftime("%Y%m%d-%H%M%S") + f"-{os.urandom(3).hex()}"


def workspace_for(repo: str) -> str:
    safe = repo.replace("/", "__") if repo else "default"
    path = os.path.join(WORKSPACE_ROOT, safe)
    os.makedirs(path, exist_ok=True)
    return path


def build_docker_cmd(*, task_id: str, repo: str, decision: dict, user_id: str) -> list[str]:
    """Assemble the ``docker run`` command for one task."""
    workspace = workspace_for(repo)
    os.makedirs(AGENT_HOME_DIR, exist_ok=True)

    cmd = [
        "docker", "run", "--rm",
        "--name", f"argus-{task_id}",
        "--memory", TASK_MEM,
        "-v", f"{workspace}:/workspace",
        "-v", f"{AGENT_HOME_DIR}:/tmp/argus-home",
        "-e", "HOME=/tmp/argus-home",
        "-e", f"REPO={repo}",
        "-e", f"ARGUS_MODEL={router.model_id(decision['model'])}",
        "-e", f"ARGUS_THINKING={decision['thinking_budget']}",
        "-e", f"ARGUS_MAX_ITERATIONS={decision['max_iterations']}",
        "-e", f"ARGUS_INTENT={decision.get('intent', '')}",
        "-e", f"ARGUS_TASK_ID={task_id}",
        "-e", f"ARGUS_USER_ID={user_id}",
        "-e", f"GITHUB_USER={GITHUB_USER}",
        "-e", f"GITHUB_EMAIL={GITHUB_EMAIL}",
    ]
    for key in ("CLAUDE_CODE_OAUTH_TOKEN", "GITHUB_TOKEN"):
        val = os.environ.get(key)
        if val:
            cmd += ["-e", f"{key}={val}"]
    for env_var, val in secrets.all_platform_tokens().items():
        cmd += ["-e", f"{env_var}={val}"]

    cmd += [DOCKER_IMAGE, decision["prompt"]]
    return cmd


async def _stream_task(cmd: list[str]) -> tuple[int, str, float | None]:
    """Run the container, parse stream-json, return (exit_code, result, cost)."""
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    result_text = ""
    cost: float | None = None
    assert proc.stdout is not None
    async for raw in proc.stdout:
        line = raw.decode(errors="replace").strip()
        if not line:
            continue
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue
        if evt.get("type") == "result":
            result_text = evt.get("result", "") or result_text
            cost = evt.get("total_cost_usd", cost)
    await proc.wait()
    return proc.returncode or 0, result_text, cost


async def run_task(*, prompt: str, user_id: str, channel_id: str, thread_ts: str,
                   post_message) -> None:
    async with _sem:
        decision = router.route(prompt)
        repo = decision.get("repo") or DEFAULT_REPO
        task_id = new_task_id()
        started = int(time.time())

        db.insert_task({
            "id": task_id,
            "type": "interactive",
            "schedule_id": None,
            "user_id": user_id,
            "channel_id": channel_id,
            "thread_ts": thread_ts,
            "prompt": prompt,
            "repo": repo,
            "model": decision["model"],
            "max_iterations": decision["max_iterations"],
            "started_at": started,
        })
        log.info("task %s: model=%s intent=%s repo=%s",
                 task_id, decision["model"], decision.get("intent"), repo)

        cmd = build_docker_cmd(
            task_id=task_id, repo=repo, decision=decision, user_id=user_id
        )
        try:
            exit_code, result, cost = await _stream_task(cmd)
        except Exception as exc:  # surface, don't crash the listener
            log.exception("task %s failed", task_id)
            exit_code, result, cost = 1, f"task error: {exc}", None

        db.finish_task(
            task_id,
            finished_at=int(time.time()),
            exit_code=exit_code,
            cost_usd=cost,
            duration_ms=(int(time.time()) - started) * 1000,
            summary=result[:2000] if result else None,
        )
        await post_message(
            channel=channel_id,
            thread_ts=thread_ts,
            text=secrets.redact(result) or "(no output)",
        )


@app.event("app_mention")
async def on_mention(event, say, client):
    await _handle(event, client)


@app.event("message")
async def on_message(event, client):
    # Only direct messages; channel messages arrive as app_mention.
    if event.get("channel_type") == "im" and not event.get("bot_id"):
        await _handle(event, client)


async def _handle(event: dict, client) -> None:
    user_id = event.get("user", "")
    channel_id = event.get("channel", "")
    thread_ts = event.get("thread_ts") or event.get("ts")
    text = (event.get("text") or "").strip()
    if not text:
        return
    if not is_authorized(user_id):
        await client.chat_postMessage(
            channel=channel_id, thread_ts=thread_ts,
            text="Not authorized.",
        )
        return

    async def post_message(*, channel, thread_ts, text):
        await client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=text)

    asyncio.create_task(run_task(
        prompt=text, user_id=user_id, channel_id=channel_id,
        thread_ts=thread_ts, post_message=post_message,
    ))


async def main() -> None:
    secrets.initialize_redaction()
    db.init_db()
    handler = AsyncSocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    log.info("argus bridge starting (image=%s, concurrency=%d)", DOCKER_IMAGE, MAX_CONCURRENT)
    await handler.start_async()


if __name__ == "__main__":
    asyncio.run(main())
