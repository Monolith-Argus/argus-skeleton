"""Tests for scheduler/monitor_repo_stars.py."""
from __future__ import annotations

from unittest.mock import patch

from scheduler.monitor_repo_stars import classify_surge, load_state, save_state


def test_quiet_no_change() -> None:
    assert classify_surge(100, 100) == "QUIET"


def test_quiet_small_gain() -> None:
    assert classify_surge(100, 102) == "QUIET"


def test_notable_threshold() -> None:
    assert classify_surge(100, 103) == "NOTABLE"


def test_surge_absolute() -> None:
    assert classify_surge(100, 115) == "SURGE"


def test_surge_relative_pct() -> None:
    # 3 stars on a base of 8 is >25% — qualifies as SURGE even below absolute threshold
    assert classify_surge(8, 11) == "SURGE"


def test_zero_base_no_division_error() -> None:
    # Any gain from 0 stars produces ~500% relative gain, which exceeds the 25% threshold
    assert classify_surge(0, 5) == "SURGE"


def test_state_roundtrip(tmp_path: object) -> None:
    fake = tmp_path / "monitor.json"  # type: ignore[operator]
    metrics = {
        "stars": 42,
        "forks": 3,
        "watchers": 10,
        "open_issues": 1,
        "subscribers": 5,
    }
    with patch("scheduler.monitor_repo_stars.STATE_FILE", fake):
        save_state(metrics)
        state = load_state()
    assert state is not None
    assert state["metrics"]["stars"] == 42
    assert state["repo"] == "Monolith-Argus/argus-skeleton"


def test_load_state_missing(tmp_path: object) -> None:
    with patch("scheduler.monitor_repo_stars.STATE_FILE", tmp_path / "nope.json"):  # type: ignore[operator]
        assert load_state() is None


def test_load_state_corrupt(tmp_path: object) -> None:
    bad = tmp_path / "bad.json"  # type: ignore[operator]
    bad.write_text("not { valid json")
    with patch("scheduler.monitor_repo_stars.STATE_FILE", bad):
        assert load_state() is None
