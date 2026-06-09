-- Every task run, scheduled or interactive.
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,                   -- 'interactive' | 'scheduled'
    schedule_id TEXT,
    user_id TEXT NOT NULL,
    channel_id TEXT,
    thread_ts TEXT,
    prompt TEXT NOT NULL,
    repo TEXT,
    model TEXT NOT NULL,
    max_iterations INTEGER,
    started_at INTEGER NOT NULL,
    finished_at INTEGER,
    cost_usd REAL,
    duration_ms INTEGER,
    exit_code INTEGER,
    summary TEXT
);

CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks(user_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_schedule ON tasks(schedule_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_started ON tasks(started_at DESC);
