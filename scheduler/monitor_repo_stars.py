#!/usr/bin/env python3
"""Monitor Monolith-Argus/argus-skeleton for star/engagement surges.

Scheduled to run every 6 hours via the Argus bridge scheduler.
State persists in STATE_FILE between runs.
Alerts are posted to Slack via argus-post when a surge is detected.
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("argus.monitor_repo_stars")

REPO = "Monolith-Argus/argus-skeleton"
STATE_FILE = Path("/tmp/argus-home/argus-skeleton-monitor.json")
ALERT_CHANNEL = "argus-ops-digest"

# Surge thresholds
SURGE_ABSOLUTE = 10       # stars gained in one period → SURGE
SURGE_RELATIVE_PCT = 25   # % increase in one period → SURGE
NOTABLE_ABSOLUTE = 3      # stars gained → NOTABLE (no surge)


def fetch_metrics() -> dict:
    result = subprocess.run(
        ["gh", "api", f"repos/{REPO}"],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(result.stdout)
    return {
        "stars": data["stargazers_count"],
        "forks": data["forks_count"],
        "watchers": data["watchers_count"],
        "open_issues": data["open_issues_count"],
        "subscribers": data["subscribers_count"],
    }


def load_state() -> dict | None:
    if not STATE_FILE.exists():
        return None
    try:
        return json.loads(STATE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def save_state(metrics: dict) -> None:
    state = {
        "repo": REPO,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics,
        "alert_thresholds": {
            "stars_absolute_surge": SURGE_ABSOLUTE,
            "stars_relative_surge_pct": SURGE_RELATIVE_PCT,
            "stars_notable": NOTABLE_ABSOLUTE,
        },
    }
    STATE_FILE.write_text(json.dumps(state, indent=2))


def post_alert(text: str) -> None:
    subprocess.run(
        ["argus-post", "--channel", ALERT_CHANNEL, "--text", text],
        check=False,
    )


def classify_surge(prev_stars: int, curr_stars: int) -> str:
    delta = curr_stars - prev_stars
    if delta <= 0:
        return "QUIET"
    pct = (delta / max(prev_stars, 1)) * 100
    if delta >= SURGE_ABSOLUTE or pct >= SURGE_RELATIVE_PCT:
        return "SURGE"
    if delta >= NOTABLE_ABSOLUTE:
        return "NOTABLE"
    return "QUIET"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    try:
        current = fetch_metrics()
    except subprocess.CalledProcessError as exc:
        log.error("Failed to fetch repo metrics: %s", exc.stderr)
        return 1

    state = load_state()

    if state is None:
        save_state(current)
        log.info(
            "Baseline established — stars=%d forks=%d watchers=%d",
            current["stars"], current["forks"], current["watchers"],
        )
        return 0

    prev = state["metrics"]
    prev_checked = state.get("checked_at", "unknown")
    status = classify_surge(prev["stars"], current["stars"])

    star_delta = current["stars"] - prev["stars"]
    fork_delta = current["forks"] - prev["forks"]
    watcher_delta = current["watchers"] - prev["watchers"]

    log.info(
        "STATUS: %s | stars %d→%d (%+d) forks %d→%d (%+d) | since %s",
        status,
        prev["stars"], current["stars"], star_delta,
        prev["forks"], current["forks"], fork_delta,
        prev_checked,
    )

    if status in ("SURGE", "NOTABLE"):
        emoji = "🚀" if status == "SURGE" else "📈"
        pct = int((star_delta / max(prev["stars"], 1)) * 100)
        text = (
            f"{emoji} *argus-skeleton engagement {status.lower()}*\n"
            f"• Stars: {prev['stars']} → {current['stars']} (+{star_delta}"
            + (f", +{pct}%" if prev["stars"] > 0 else "") + ")\n"
            f"• Forks: {prev['forks']} → {current['forks']}"
            + (f" (+{fork_delta})" if fork_delta else "") + "\n"
            f"• Watchers: {prev['watchers']} → {current['watchers']}"
            + (f" (+{watcher_delta})" if watcher_delta else "") + "\n"
            f"• Period: since {prev_checked[:16].replace('T', ' ')} UTC\n"
            f"• Repo: <https://github.com/{REPO}|{REPO}>"
        )
        post_alert(text)

    save_state(current)
    return 0


if __name__ == "__main__":
    sys.exit(main())
