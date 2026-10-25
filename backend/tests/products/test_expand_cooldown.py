"""Expansion must not hold a request and must not repeat an attempt inside the cooldown."""
import time

from products import catalog, expand
from products.db import connect


def _db(tmp_path):
    path = tmp_path / "av_prices.db"
    connect(path).close()
    return path


def test_slow_expansion_returns_within_the_wait(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setenv("PRODUCTS_EXPAND_DEADLINE_S", "0.2")
    monkeypatch.setattr(catalog, "expand_catalog", lambda conn, category, **kw: time.sleep(1.5) or 0)
    start = time.monotonic()
    warnings = expand.expand(_db(tmp_path), {"projector": (300.0, {})}, "k")
    assert time.monotonic() - start < 1.0
    assert any("timed out" in w for w in warnings)


def test_same_category_and_band_is_not_retried_within_the_cooldown(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setenv("PRODUCTS_EXPAND_DEADLINE_S", "2")
    calls = []
    monkeypatch.setattr(catalog, "expand_catalog", lambda conn, category, **kw: calls.append(category) or 0)
    path = _db(tmp_path)
    expand.expand(path, {"mount": (40.0, {})}, "k")
    expand.expand(path, {"mount": (41.0, {})}, "k")  # same 1.5x price band
    assert calls == ["mount"]


def test_failed_expansion_can_be_retried(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setenv("PRODUCTS_EXPAND_DEADLINE_S", "2")
    calls = []

    def boom(conn, category, **kw):
        calls.append(category)
        raise RuntimeError("search failed")

    monkeypatch.setattr(catalog, "expand_catalog", boom)
    path = _db(tmp_path)
    expand.expand(path, {"cable": (20.0, {})}, "k")
    expand.expand(path, {"cable": (20.0, {})}, "k")
    assert calls == ["cable", "cable"]
