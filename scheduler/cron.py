"""Minimal standard 5-field cron support.

Fields: minute hour day-of-month month day-of-week. Each field accepts ``*``,
a single value, a comma list, an ``a-b`` range, and a ``*/n`` step. Day-of-week
is 0-6 with Sunday = 0.

``next_after(expr, ts)`` returns the next Unix timestamp strictly after ``ts``
that matches the expression. Minute resolution; searches up to ~4 years ahead.
"""
from __future__ import annotations

import time

_BOUNDS = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)]


def _parse_field(field: str, lo: int, hi: int) -> set[int]:
    values: set[int] = set()
    for part in field.split(","):
        step = 1
        if "/" in part:
            part, step_s = part.split("/", 1)
            step = int(step_s)
        if part in ("*", ""):
            start, end = lo, hi
        elif "-" in part:
            a, b = part.split("-", 1)
            start, end = int(a), int(b)
        else:
            start = end = int(part)
        values.update(range(start, end + 1, step))
    return {v for v in values if lo <= v <= hi}


def _matches(fields: list[set[int]], tm: time.struct_time) -> bool:
    minute, hour, dom, month, dow = fields
    # cron: when both DOM and DOW are restricted, a match on either suffices.
    dom_restricted = len(dom) < 31
    dow_restricted = len(dow) < 7
    day_ok = (tm.tm_mday in dom) if dom_restricted else True
    weekday = (tm.tm_wday + 1) % 7  # struct_time Monday=0 -> cron Sunday=0
    wday_ok = (weekday in dow) if dow_restricted else True
    if dom_restricted and dow_restricted:
        day_match = day_ok or wday_ok
    else:
        day_match = day_ok and wday_ok
    return (
        tm.tm_min in minute
        and tm.tm_hour in hour
        and day_match
        and tm.tm_mon in month
    )


def next_after(expr: str, ts: int) -> int:
    parts = expr.split()
    if len(parts) != 5:
        raise ValueError(f"expected 5 cron fields, got {len(parts)}: {expr!r}")
    fields = [_parse_field(p, lo, hi) for p, (lo, hi) in zip(parts, _BOUNDS)]

    candidate = (ts // 60 + 1) * 60  # next whole minute after ts
    limit = ts + 4 * 366 * 24 * 3600
    while candidate <= limit:
        if _matches(fields, time.localtime(candidate)):
            return candidate
        candidate += 60
    raise ValueError(f"no cron match within 4 years for {expr!r}")
