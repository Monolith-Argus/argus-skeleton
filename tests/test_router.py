from __future__ import annotations

import os

from bridge import router


def test_router_disabled_returns_adhoc_band(monkeypatch):
    monkeypatch.setenv("ARGUS_ROUTER_DISABLED", "1")
    d = router.route("do something")
    assert d["intent"] == "adhoc"
    assert d["model"] in router.MODEL_IDS


def test_user_override_model_and_iter(monkeypatch):
    monkeypatch.setenv("ARGUS_ROUTER_DISABLED", "1")
    d = router.route("rework the parser [model=opus] [iter=200]")
    assert d["model"] == "opus"
    assert d["max_iterations"] == 200
    assert "[model=opus]" not in d["prompt"]


def test_iter_override_clamped(monkeypatch):
    monkeypatch.setenv("ARGUS_ROUTER_DISABLED", "1")
    d = router.route("x [iter=9999]")
    assert d["max_iterations"] == 500


def test_model_id_falls_back_to_sonnet():
    assert router.model_id("nonsense") == router.MODEL_IDS["sonnet"]
