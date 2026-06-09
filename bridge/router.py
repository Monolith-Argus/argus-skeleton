"""Model and iteration-budget selection.

Maps a classified intent to a model band. Bands trade cost against capability:
cheap intents run on Haiku with a small iteration budget; open-ended code work
runs on a stronger model with more turns. A user can override per message with a
trailing ``[model=opus]`` / ``[thinking=high]`` / ``[iter=120]`` token.
"""
from __future__ import annotations

import os
import re

from . import classifier

MODEL_IDS = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-8",
}

# intent -> routing band
BANDS = {
    "code.modify": {"model": "sonnet", "thinking_budget": "medium", "max_iterations": 120},
    "code.investigate": {"model": "sonnet", "thinking_budget": "low", "max_iterations": 40},
    "code.review_pr": {"model": "sonnet", "thinking_budget": "medium", "max_iterations": 60},
    "ops.diagnose": {"model": "sonnet", "thinking_budget": "low", "max_iterations": 40},
    "research": {"model": "sonnet", "thinking_budget": "low", "max_iterations": 40},
    "comms.draft": {"model": "haiku", "thinking_budget": "off", "max_iterations": 20},
    "adhoc": {"model": "sonnet", "thinking_budget": "medium", "max_iterations": 60},
}

_OVERRIDE_RE = re.compile(r"\[(model|thinking|iter)=([a-z0-9]+)\]", re.IGNORECASE)


def model_id(short: str) -> str:
    return MODEL_IDS.get(short, MODEL_IDS["sonnet"])


def _parse_overrides(prompt: str) -> tuple[str, dict]:
    overrides: dict = {}
    for key, val in _OVERRIDE_RE.findall(prompt):
        key = key.lower()
        if key == "model" and val.lower() in MODEL_IDS:
            overrides["model"] = val.lower()
        elif key == "thinking" and val.lower() in {"off", "low", "medium", "high"}:
            overrides["thinking_budget"] = val.lower()
        elif key == "iter" and val.isdigit():
            overrides["max_iterations"] = max(20, min(int(val), 500))
    cleaned = _OVERRIDE_RE.sub("", prompt).strip()
    return cleaned, overrides


def route(prompt: str, repo: str | None = None) -> dict:
    cleaned, overrides = _parse_overrides(prompt)

    if os.environ.get("ARGUS_ROUTER_DISABLED") == "1":
        decision = dict(BANDS["adhoc"])
        decision.update(overrides)
        decision.update(prompt=cleaned, intent="adhoc", rationale="router disabled")
        return decision

    intent = classifier.classify(cleaned)
    decision = dict(BANDS.get(intent.label, BANDS["adhoc"]))
    decision.update(overrides)
    decision.update(
        prompt=cleaned,
        intent=intent.label,
        rationale=f"intent={intent.label} ({intent.rationale})",
    )
    return decision
