"""Output sinks for scheduled job results.

A schedule's ``sink`` column names where its result goes. Two forms are
supported:

- ``slack:<channel>`` — post the result text to a Slack channel.
- ``file:<path>``     — append the result text to a file.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger("argus.scheduler.sinks")


def dispatch(sink: str | None, title: str, result: str) -> None:
    if not sink:
        return
    if sink.startswith("slack:"):
        _to_slack(sink.removeprefix("slack:"), title, result)
    elif sink.startswith("file:"):
        _to_file(sink.removeprefix("file:"), title, result)
    else:
        log.warning("unknown sink form: %s", sink)


def _to_slack(channel: str, title: str, result: str) -> None:
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        log.error("slack sink: SLACK_BOT_TOKEN not set")
        return
    from slack_sdk import WebClient

    client = WebClient(token=token)
    text = f"*{title}*\n{result}" if title else result
    client.chat_postMessage(channel=channel, text=text)


def _to_file(path: str, title: str, result: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as fh:
        if title:
            fh.write(f"# {title}\n")
        fh.write(result + "\n")
