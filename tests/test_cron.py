from __future__ import annotations

import time

from scheduler.cron import next_after


def _ts(s: str) -> int:
    return int(time.mktime(time.strptime(s, "%Y-%m-%d %H:%M")))


def test_every_minute():
    base = _ts("2024-01-01 00:00")
    assert next_after("* * * * *", base) == base + 60


def test_top_of_hour():
    base = _ts("2024-01-01 09:30")
    assert next_after("0 * * * *", base) == _ts("2024-01-01 10:00")


def test_specific_time():
    base = _ts("2024-01-01 09:30")
    assert next_after("0 9 * * *", base) == _ts("2024-01-02 09:00")


def test_step_field():
    base = _ts("2024-01-01 00:05")
    assert next_after("*/15 * * * *", base) == _ts("2024-01-01 00:15")


def test_invalid_field_count():
    try:
        next_after("* * *", 0)
    except ValueError:
        return
    raise AssertionError("expected ValueError for malformed expression")
