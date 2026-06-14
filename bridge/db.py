"""SQLite access for tasks and schedules.

The schema lives in ``migrations/*.sql`` as idempotent statements. ``init_db``
applies every migration in order; each is safe to re-run. Run this module as a
script (``python -m bridge.db``) to initialise the database.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

DB_PATH = os.environ.get("DB_PATH", "./argus.db")
MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Apply every migration. Idempotent."""
    conn = connect()
    try:
        for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
            conn.executescript(sql_file.read_text())
        conn.commit()
    finally:
        conn.close()


def insert_task(task: dict) -> None:
    cols = (
        "id",
        "type",
        "schedule_id",
        "user_id",
        "channel_id",
        "thread_ts",
        "prompt",
        "repo",
        "model",
        "max_iterations",
        "started_at",
    )
    placeholders = ", ".join("?" for _ in cols)
    conn = connect()
    try:
        conn.execute(
            f"INSERT INTO tasks ({', '.join(cols)}) VALUES ({placeholders})",
            tuple(task.get(c) for c in cols),
        )
        conn.commit()
    finally:
        conn.close()


def finish_task(
    task_id: str,
    *,
    finished_at: int,
    exit_code: int,
    cost_usd: float | None = None,
    duration_ms: int | None = None,
    summary: str | None = None,
) -> None:
    conn = connect()
    try:
        conn.execute(
            "UPDATE tasks SET finished_at=?, exit_code=?, cost_usd=?, "
            "duration_ms=?, summary=? WHERE id=?",
            (finished_at, exit_code, cost_usd, duration_ms, summary, task_id),
        )
        conn.commit()
    finally:
        conn.close()


def recent_tasks(limit: int = 20) -> list[sqlite3.Row]:
    conn = connect()
    try:
        return conn.execute(
            "SELECT * FROM tasks ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
    finally:
        conn.close()


def insert_schedule(schedule: dict) -> None:
    cols = ("id", "name", "cron", "prompt", "repo", "sink", "enabled", "next_run_at", "created_at")
    placeholders = ", ".join("?" for _ in cols)
    conn = connect()
    try:
        conn.execute(
            f"INSERT INTO schedules ({', '.join(cols)}) VALUES ({placeholders})",
            tuple(schedule.get(c) for c in cols),
        )
        conn.commit()
    finally:
        conn.close()


def due_schedules(now_ts: int) -> list[sqlite3.Row]:
    conn = connect()
    try:
        return conn.execute(
            "SELECT * FROM schedules WHERE enabled=1 AND next_run_at <= ?",
            (now_ts,),
        ).fetchall()
    finally:
        conn.close()


def set_schedule_next_run(schedule_id: str, next_run_at: int) -> None:
    conn = connect()
    try:
        conn.execute(
            "UPDATE schedules SET next_run_at=? WHERE id=?",
            (next_run_at, schedule_id),
        )
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print(f"initialised {DB_PATH}")
