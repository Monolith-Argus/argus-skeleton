from __future__ import annotations

from bridge import secrets


def test_redacts_registered_value():
    secrets.register_for_redaction("supersecretvalue123")
    out = secrets.redact("the token is supersecretvalue123 ok")
    assert "supersecretvalue123" not in out
    assert "[REDACTED]" in out


def test_redacts_generic_slack_token():
    # Built by concatenation so the literal does not appear in source (and so
    # secret scanners don't flag a deliberately-fake fixture value).
    fake = "xoxb-" + "0" * 12 + "-" + "a" * 16
    out = secrets.redact(f"the token is {fake}")
    assert "xoxb-" not in out
    assert "[REDACTED]" in out


def test_redact_empty_is_safe():
    assert secrets.redact("") == ""
