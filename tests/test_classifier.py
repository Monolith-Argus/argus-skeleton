from __future__ import annotations

from bridge import classifier


def test_fails_open_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ARGUS_ANTHROPIC_API_KEY", raising=False)
    intent = classifier.classify("anything at all")
    assert intent.label == "adhoc"


def test_all_intents_are_known():
    assert "code.modify" in classifier.TASK_INTENTS
    assert "adhoc" in classifier.TASK_INTENTS
