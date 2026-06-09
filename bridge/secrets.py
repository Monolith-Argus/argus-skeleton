"""Secret loading and redaction.

Two responsibilities:

- Forward deploy-platform tokens into the task container environment.
- Redact every known secret (and anything that looks like a token) from output
  before it reaches Slack or a log.
"""
from __future__ import annotations

import os
import re

# Map platform name -> env var the vendor CLI expects.
PLATFORM_ENV_VAR = {
    "vercel": "VERCEL_TOKEN",
    "fly": "FLY_API_TOKEN",
    "railway": "RAILWAY_TOKEN",
    "cloudflare": "CLOUDFLARE_API_TOKEN",
}


def all_platform_tokens() -> dict[str, str]:
    """env-var-name -> token for every platform whose token is set."""
    out: dict[str, str] = {}
    for env_var in PLATFORM_ENV_VAR.values():
        val = os.environ.get(env_var)
        if val:
            out[env_var] = val
    return out


# Exact secret strings to scrub, loaded once at startup.
_redaction_targets: set[str] = set()


def register_for_redaction(value: str | None) -> None:
    if value and len(value) >= 8:
        _redaction_targets.add(value)


def initialize_redaction() -> None:
    """Load all known secrets into the redaction set."""
    for env_key in (
        "SLACK_BOT_TOKEN",
        "SLACK_APP_TOKEN",
        "ANTHROPIC_API_KEY",
        "ARGUS_ANTHROPIC_API_KEY",
        "CLAUDE_CODE_OAUTH_TOKEN",
        "GITHUB_TOKEN",
    ):
        register_for_redaction(os.environ.get(env_key))
    for env_var in PLATFORM_ENV_VAR.values():
        register_for_redaction(os.environ.get(env_var))


# Patterns that look like tokens regardless of provenance.
_GENERIC_PATTERNS = [
    re.compile(r"xox[abp]-[A-Za-z0-9-]{10,}"),
    re.compile(r"xapp-\d+-[A-Za-z0-9-]{10,}"),
    re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{30,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{30,}"),
]


def redact(text: str) -> str:
    if not text:
        return text
    for tok in _redaction_targets:
        if tok and tok in text:
            text = text.replace(tok, "[REDACTED]")
    for pat in _GENERIC_PATTERNS:
        text = pat.sub("[REDACTED]", text)
    return text
