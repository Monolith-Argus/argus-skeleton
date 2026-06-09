"""Cron entry point for recurring jobs.

Invoked from cron (e.g. once a minute). Finds schedules whose ``next_run_at`` has
passed, runs each as an autonomous task in a container, routes the result to the
schedule's sink, and advances ``next_run_at`` to the next cron occurrence.

    * * * * * cd /opt/argus && python -m scheduler.run_scheduled_job
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import time

from bridge import db, router, secrets
from . import sinks
from .cron import next_after

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("argus.scheduler")

DOCKER_IMAGE = os.environ.get("DOCKER_IMAGE", "argus-agent:latest")
TASK_MEM = os.environ.get("TASK_MEM", "500m")
AGENT_HOME_DIR = os.environ.get("ARGUS_AGENT_HOME_DIR", "/var/lib/argus/agent-home")
WORKSPACE_ROOT = os.environ.get("ARGUS_WORKSPACE_ROOT", "/var/lib/argus/workspaces")


def _workspace_for(repo: str) -> str:
    safe = repo.replace("/", "__") if repo else "default"
    path = os.path.join(WORKSPACE_ROOT, safe)
    os.makedirs(path, exist_ok=True)
    return path


def _run_container(*, task_id: str, repo: str, decision: dict) -> tuple[int, str]:
    os.makedirs(AGENT_HOME_DIR, exist_ok=True)
    cmd = [
        "docker", "run", "--rm",
        "--name", f"argus-{task_id}",
        "--memory", TASK_MEM,
        "-v", f"{_workspace_for(repo)}:/workspace",
        "-v", f"{AGENT_HOME_DIR}:/tmp/argus-home",
        "-e", "HOME=/tmp/argus-home",
        "-e", "ARGUS_AUTONOMOUS=1",
        "-e", f"REPO={repo}",
        "-e", f"ARGUS_MODEL={router.model_id(decision['model'])}",
        "-e", f"ARGUS_THINKING={decision['thinking_budget']}",
        "-e", f"ARGUS_MAX_ITERATIONS={decision['max_iterations']}",
        "-e", f"ARGUS_TASK_ID={task_id}",
    ]
    for key in ("CLAUDE_CODE_OAUTH_TOKEN", "GITHUB_TOKEN", "GITHUB_USER", "GITHUB_EMAIL"):
        val = os.environ.get(key)
        if val:
            cmd += ["-e", f"{key}={val}"]
    cmd += [DOCKER_IMAGE, decision["prompt"]]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    result = ""
    for line in proc.stdout.splitlines():
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue
        if evt.get("type") == "result":
            result = evt.get("result", "") or result
    return proc.returncode, result


def run_due(now_ts: int | None = None) -> int:
    secrets.initialize_redaction()
    now_ts = now_ts or int(time.time())
    due = db.due_schedules(now_ts)
    for sched in due:
        decision = router.route(sched["prompt"], repo=sched["repo"])
        task_id = time.strftime("%Y%m%d-%H%M%S") + f"-{os.urandom(3).hex()}"
        log.info("firing schedule %s (%s)", sched["id"], sched["name"])
        rc, result = _run_container(
            task_id=task_id, repo=sched["repo"] or "", decision=decision
        )
        sinks.dispatch(sched["sink"], sched["name"], secrets.redact(result))
        db.set_schedule_next_run(sched["id"], next_after(sched["cron"], now_ts))
    return len(due)


if __name__ == "__main__":
    n = run_due()
    log.info("ran %d due schedule(s)", n)
