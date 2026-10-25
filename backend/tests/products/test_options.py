"""Variety and per-item swap choices for the catalog recommender."""

import json
import time
from pathlib import Path

import pytest

from backend.app.engine import run_optimize
from backend.app.schemas import Room
from backend.tests.contract.checks import assert_valid_products
from products import catalog, get_products
from products.variety import family_key, model_key

from .test_recommend import listing


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


def test_model_key_ignores_seller_wording_and_pair_terms():
    first = {"title": "Edifier R1280DB 2.0 Bookshelf Speakers (Pair) 42W", "specs": {"brand": "Edifier"}}
    second = {"title": "New Edifier R1280DB Wireless Speaker set of 2", "specs": {"brand": "Edifier"}}
    other = {"title": "Edifier R980T Bookshelf Speakers", "specs": {"brand": "Edifier"}}
    assert model_key(first) == model_key(second)
    assert model_key(first) != model_key(other)
    assert family_key(first) == ("edifier", "r1280")


def test_alternatives_are_sorted_distinct_and_budget_safe(small_db):
    catalog.save_listings(small_db, "speaker choices", "speaker", [
        listing("Acme A100 Bookshelf Speaker 100W", 60, rating=3.5),
        listing("Acme B200 Bookshelf Speaker 120W", 90, rating=4.0),
        listing("Acme C300 Bookshelf Speaker 160W", 120, rating=4.5),
        listing("Acme D400 Bookshelf Speaker 180W", 150, rating=5.0),
        listing("Acme E500 Bookshelf Speaker 200W", 180, rating=5.0),
    ])
    layout = {"speakers": [{"role": "C"}]}
    result = get_products(layout, 170)
    assert_valid_products(result, 170, layout)
    item = result["items"][0]
    assert 1 <= len(item["alternatives"]) <= 3
    assert [alt["price"] for alt in item["alternatives"]] == sorted(
        alt["price"] for alt in item["alternatives"])
    for alt in item["alternatives"]:
        assert alt["price_delta"] == pytest.approx(round(alt["price"] - item["price"], 2))
        assert result["total"] - item["price"] + alt["price"] <= 170
        assert model_key(alt) != model_key(item)
        assert "role" not in alt and "pair_with" not in alt
        assert alt["dimensions"] and isinstance(alt["specs"], dict)


def test_pair_alternatives_cover_both_roles(small_db):
    catalog.save_listings(small_db, "speaker pairs", "speaker", [
        listing("Acme A100 Bookshelf Speakers (Pair) 100W", 100),
        listing("Acme B200 Bookshelf Speakers (Pair) 120W", 130),
        listing("Acme C300 Bookshelf Speakers (Pair) 150W", 160),
    ])
    layout = {"speakers": [{"role": "L"}, {"role": "R"}, {"role": "Ls"}, {"role": "Rs"}]}
    result = get_products(layout, 500)
    assert_valid_products(result, 500, layout)
    by_role = {item["role"]: item for item in result["items"]}
    for first, second in (("L", "R"), ("Ls", "Rs")):
        if by_role[first].get("pair_with"):
            assert by_role[second]["alternatives"] == []
            assert all("pair" in alt["title"].lower() for alt in by_role[first]["alternatives"])
            for alt in by_role[first]["alternatives"]:
                assert result["total"] - by_role[first]["price"] + alt["price"] <= 500


def test_surrounds_choose_good_different_model(small_db):
    catalog.save_listings(small_db, "speaker models", "speaker", [
        listing("Edifier R1280DB Bookshelf Speaker 150W", 90, rating=5.0, reviews=300),
        listing("Edifier R980T Bookshelf Speaker 140W", 85, rating=4.9, reviews=300),
    ])
    layout = {"speakers": [{"role": role} for role in ("L", "R", "C", "Ls", "Rs")]}
    result = get_products(layout, 900)
    assert_valid_products(result, 900, layout)
    by_role = {item["role"]: item for item in result["items"]}
    assert model_key(by_role["L"]) == model_key(by_role["R"]) == model_key(by_role["C"])
    assert model_key(by_role["Ls"]) == model_key(by_role["Rs"])
    assert model_key(by_role["Ls"]) != model_key(by_role["L"])


def test_surrounds_can_match_when_no_good_difference(small_db):
    catalog.save_listings(small_db, "speaker models", "speaker", [
        listing("Edifier R1280DB Bookshelf Speaker 150W", 90, rating=5.0, reviews=300),
        listing("Edifier R980T Bookshelf Speaker 20W", 85, rating=3.0, reviews=300),
    ])
    layout = {"speakers": [{"role": role} for role in ("L", "R", "C", "Ls", "Rs")]}
    result = get_products(layout, 900)
    by_role = {item["role"]: item for item in result["items"]}
    assert model_key(by_role["Ls"]) == model_key(by_role["L"])


def test_demo_seed_has_variety_and_options(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("AV_DB", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("SERPAPI_KEY", raising=False)
    room = Room.model_validate(json.loads(Path("fixtures/room_demo.json").read_text()))
    layout = run_optimize(room)["layout"]
    start = time.monotonic()
    result = get_products(layout, 1500)
    assert time.monotonic() - start < 3
    assert_valid_products(result, 1500, layout)
    assert len({model_key(item) for item in result["items"]}) >= 3
    assert all("alternatives" in item for item in result["items"])
    assert 1100 <= result["total"] <= 1500
