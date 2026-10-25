import time

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.tests.contract.checks import assert_valid_products
from products import catalog, get_products
from products.db import SEED
from products.dimensions import dimensions

ROLES = ("L", "R", "C", "LFE", "Ls", "Rs")


def layout(screen=False):
    return {"speakers": [{"role": role} for role in ROLES],
            "screen": {"width": 6.0, "height": 3.4} if screen else None}


def listing(title, price, link="https://example.test/product", **kwargs):
    return {"title": title, "extracted_price": price, "product_link": link,
            "source": "Shop", "rating": 4.5, "reviews": 50, **kwargs}


@pytest.fixture
def small_db(tmp_path, monkeypatch):
    path = tmp_path / "small.db"
    monkeypatch.setenv("AV_DB", str(path))
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("SERPAPI_KEY", raising=False)
    conn = catalog.init_db(str(path))
    yield conn
    conn.close()


def test_filters_mapping_pairs_and_budget(small_db):
    catalog.save_listings(small_db, "bookshelf", "speaker", [
        listing("Good Bookshelf Speakers (Pair) 100W", 120),
        listing("Used Bookshelf Speaker 100W", 50),
        listing("Refurbished Bookshelf Speaker 100W", 55),
        listing("Cheap Bookshelf Speaker 100W", 1),
        listing("No Link Bookshelf Speaker 100W", 80, link=""),
        listing("Bookshelf Speaker 100W", 150),
    ])
    catalog.save_listings(small_db, "bad category", "speaker", [listing("Subwoofer 12 inch", 90)])
    catalog.save_listings(small_db, "bass", "subwoofer", [listing("Bass Subwoofer 12 inch 300W", 110)])
    catalog.save_listings(small_db, "beam", "projector", [listing("1080p Projector 2000 lumens", 250)])
    result = get_products(layout(), 1200)
    assert_valid_products(result, 1200, layout())
    by_role = {item["role"]: item for item in result["items"]}
    assert by_role["L"]["pair_with"] == "R"
    assert by_role["R"]["pair_with"] == "L"
    assert by_role["R"]["price"] == 0
    assert by_role["LFE"]["title"].startswith("Bass")
    assert all("Used" not in item["title"] and "Refurbished" not in item["title"] for item in result["items"])
    assert all(item["link"] and item["price"] != 1 for item in result["items"] if item["role"] != "R")
    assert result["total"] <= 1200
    tiny = get_products(layout(), 10)
    assert tiny["total"] <= 10 and any("no product" in warning for warning in tiny["warnings"])


def test_value_pick_and_second_pass(small_db):
    catalog.save_listings(small_db, "speaker options", "speaker", [
        listing("Poor Bookshelf Speaker 20W", 35, rating=3.0, reviews=100),
        listing("Better Bookshelf Speaker 100W", 70, rating=5.0, reviews=500),
        listing("Premium Bookshelf Speaker 300W", 105, rating=5.0, reviews=500),
    ])
    result = get_products({"speakers": [{"role": "C"}]}, 250)
    assert "Better" in result["items"][0]["title"] or "Premium" in result["items"][0]["title"]
    result = get_products({"speakers": [{"role": "C"}]}, 130)
    assert "Better" in result["items"][0]["title"] or "Premium" in result["items"][0]["title"]
    result = get_products({"speakers": [{"role": "C"}, {"role": "LFE"}]}, 130)
    assert "Premium" in result["items"][0]["title"]


def test_dimensions_parsed_and_default():
    parsed = dimensions({"title": 'Cabinet 12" x 24" x 8"', "snippet": "", "extensions": "[]"}, "L", None)
    assert parsed == {"width": 1.0, "height": 2.0, "depth": 8 / 12, "source": "listing"}
    labelled = dimensions({"title": "Speaker W 30 cm H 60 cm D 25 cm", "snippet": "", "extensions": "[]"}, "L", None)
    assert labelled["source"] == "listing" and labelled["width"] == pytest.approx(30 / 30.48)
    default = dimensions({"title": "Unknown", "specs": {"form_factor": "floorstanding"}}, "L", None)
    assert default == {"width": 0.8, "height": 3.3, "depth": 1.0, "source": "default"}


def test_expansion_deadline_and_once_per_category(small_db, monkeypatch):
    calls = []

    def slow(conn, category, price=None, specs=None, max_queries=5):
        calls.append((category, price, specs, max_queries))
        time.sleep(0.4)
        return 0

    monkeypatch.setattr(catalog, "expand_catalog", slow)
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    monkeypatch.setenv("SERPAPI_KEY", "fake")
    monkeypatch.setenv("PRODUCTS_EXPAND_DEADLINE_S", "0.2")
    start = time.monotonic()
    result = get_products(layout(), 1000)
    assert time.monotonic() - start < 0.35
    assert "timed out" in " ".join(result["warnings"])
    assert sorted(category for category, *_ in calls) == ["projector", "speaker", "subwoofer"]
    assert all(max_queries == 3 for *_, max_queries in calls)
    monkeypatch.delenv("SERPAPI_KEY")
    calls.clear()
    result = get_products(layout(), 1000)
    assert not calls and sum("skipped" in warning for warning in result["warnings"]) == 1


def test_explicit_serpapi_key_reaches_catalog(small_db, monkeypatch):
    seen = []

    def fake(conn, category, price=None, specs=None, max_queries=5):
        import os

        seen.append(os.getenv("SERPAPI_KEY"))
        return 0

    monkeypatch.setattr(catalog, "expand_catalog", fake)
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    get_products({"speakers": [{"role": "C"}]}, 100, serpapi_key="explicit")
    assert seen == ["explicit", "explicit"]


@pytest.mark.parametrize("budget", [1500, 5000])
@pytest.mark.parametrize("screen", [False, True])
def test_seed_catalog(tmp_path, monkeypatch, budget, screen):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("AV_DB", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("SERPAPI_KEY", raising=False)
    start = time.monotonic()
    result = get_products(layout(screen), budget)
    assert time.monotonic() - start < 2
    assert_valid_products(result, budget, layout(screen))
    assert {item["role"] for item in result["items"]} >= set(ROLES)
    assert all(item["dimensions"] and isinstance(item["specs"], dict) for item in result["items"])
    assert (tmp_path / "av_prices.db").exists() and SEED.is_file()


def test_demo_api_uses_catalog(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("AV_DB", raising=False)
    monkeypatch.delenv("PRODUCTS_BACKEND", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("SERPAPI_KEY", raising=False)
    with TestClient(app) as client:
        room = client.post("/rooms/demo", json={}).json()
        optimized = client.post(f"/rooms/{room['room_id']}/optimize", json={})
        assert optimized.status_code == 200
        response = client.get(f"/rooms/{room['room_id']}/products?budget=1500")
        assert response.status_code == 200
        result = response.json()
        assert result["items"] and all(item["source"] == "google_shopping" for item in result["items"])
