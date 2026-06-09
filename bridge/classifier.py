"""Intent classification for incoming Slack messages.

A single Haiku call maps each message to one of ``TASK_INTENTS``. The router
reads the result to pick a model and iteration budget. When no API key is set
the classifier returns ``adhoc`` so the bridge still functions without it.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

ROUTER_MODEL = os.environ.get("ARGUS_ROUTER_MODEL", "claude-haiku-4-5-20251001")

TASK_INTENTS = {
    "code.modify",       # write code in a repository
    "code.investigate",  # read-only code analysis
    "code.review_pr",    # review a pull request
    "ops.diagnose",      # investigate a runtime failure
    "research",          # fetch and synthesize information
    "comms.draft",       # draft a message or document
    "adhoc",             # classifier unsure
}

SYSTEM_PROMPT = """You classify Slack messages sent to a coding agent into one \
intent label. Reply with JSON only: {"label": "<intent>", "confidence": <0-1>}.

Labels:
- code.modify: write or change code in a repository
- code.investigate: read-only code analysis, no edits
- code.review_pr: review a pull request
- ops.diagnose: investigate a runtime failure or system health
- research: fetch and synthesize information
- comms.draft: draft a message, post, or document
- adhoc: the message does not clearly map to any label above
"""


@dataclass
class Intent:
    label: str
    confidence: float
    rationale: str = ""


def _api_key() -> str | None:
    # The bridge renames ANTHROPIC_API_KEY to ARGUS_ANTHROPIC_API_KEY in the
    # task container so the agent's SDK can't bill per-token; on the bridge
    # side either name is acceptable.
    return os.environ.get("ARGUS_ANTHROPIC_API_KEY") or os.environ.get(
        "ANTHROPIC_API_KEY"
    )


def classify(text: str) -> Intent:
    key = _api_key()
    if not key:
        return Intent("adhoc", 0.5, "no anthropic key configured")

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=key)
        resp = client.messages.create(
            model=ROUTER_MODEL,
            max_tokens=128,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text[:4000]}],
        )
        raw = resp.content[0].text.strip()
        data = json.loads(raw)
        label = data.get("label", "adhoc")
        if label not in TASK_INTENTS:
            label = "adhoc"
        return Intent(label, float(data.get("confidence", 0.5)), "haiku")
    except Exception as exc:  # fail open — never block dispatch on classifier
        return Intent("adhoc", 0.5, f"classifier error: {exc}")
