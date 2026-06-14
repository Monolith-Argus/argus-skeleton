"""Seed default recurring schedules into the Argus DB.

Safe to run multiple times — uses INSERT OR IGNORE with deterministic IDs.

    python -m scheduler.seed_schedules
"""
from __future__ import annotations

import time

from bridge.db import connect, init_db
from scheduler.cron import next_after

_SCHEDULES = [
    {
        "id": "monitor-argus-skeleton-stars",
        "name": "argus-skeleton star/engagement monitor",
        "cron": "0 */6 * * *",
        "prompt": (
            "Run python3 -m scheduler.monitor_repo_stars to check "
            "Monolith-Argus/argus-skeleton for star and engagement surges. "
            "The script self-posts alerts to Slack on surge; just execute it "
            "and report the exit status."
        ),
        "repo": "Monolith-Argus/argus-skeleton",
        "sink": None,
        "enabled": 1,
    },
]


def seed() -> None:
    init_db()
    now = int(time.time())
    conn = connect()
    try:
        for s in _SCHEDULES:
            next_run = next_after(s["cron"], now)
            conn.execute(
                "INSERT OR IGNORE INTO schedules "
                "(id, name, cron, prompt, repo, sink, enabled, next_run_at, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    s["id"],
                    s["name"],
                    s["cron"],
                    s["prompt"],
                    s["repo"],
                    s.get("sink"),
                    s["enabled"],
                    next_run,
                    now,
                ),
            )
        conn.commit()
        for s in _SCHEDULES:
            print(f"seeded: {s['name']}")
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
