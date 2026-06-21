"""Seed default recurring schedules into the Argus DB.

Safe to run multiple times — uses INSERT OR IGNORE with deterministic IDs.

    python -m scheduler.seed_schedules
"""
from __future__ import annotations

import logging
import sqlite3
import time

from bridge.db import connect, init_db
from scheduler.cron import next_after

log = logging.getLogger("argus.seed_schedules")

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


def _schema_has_col(conn: sqlite3.Connection, table: str, col: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row[1] == col for row in rows)


def seed() -> None:
    try:
        init_db()
    except sqlite3.OperationalError as exc:
        # The connected DB may have a different schema version (e.g. the
        # production Argus DB whose schedules table predates next_run_at).
        # Log a warning and continue; the INSERT below handles incompatibility.
        log.warning("init_db() skipped incompatible migration: %s", exc)

    now = int(time.time())
    conn = connect()
    try:
        if not _schema_has_col(conn, "schedules", "next_run_at"):
            log.warning(
                "schedules table has no next_run_at column — "
                "skipping seed (use the production schedule manager instead)"
            )
            return

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
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    seed()
