-- Recurring jobs fired by scheduler/run_scheduled_job.py.
CREATE TABLE IF NOT EXISTS schedules (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    cron TEXT NOT NULL,                   -- standard 5-field cron expression
    prompt TEXT NOT NULL,
    repo TEXT,
    sink TEXT,                            -- 'slack:<channel>' | 'file:<path>'
    enabled INTEGER NOT NULL DEFAULT 1,
    next_run_at INTEGER,
    created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_schedules_due ON schedules(enabled, next_run_at);
