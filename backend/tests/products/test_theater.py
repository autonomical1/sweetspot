"""Complete setup rules and catalog maintenance."""

import json
import time
from pathlib import Path

import pytest

from backend.app.engine import run_optimize
from backend.app.schemas import Room
from products import catalog, get_products
from products import recommend
from products.recommend import _role_rows, _upgrades
from products.theater import bundle_roles, choose_tv, passive_speaker, receiver_channels, receiver_eligible
from products.variety import model_key
from tools import expand_catalog

from .test_recommend import listing


def test_passive_speakers_and_bundles():
    assert passive_speaker({"title": "Klipsch R-41M bookshelf speakers", "specs": {}})
    for word in ("Bluetooth", "powered", "wireless", "USB", "Sonos", "soundbar"):
        assert not passive_speaker({"title": f"Acme {word} speaker", "specs": {}})
    assert not passive_speaker({"title": "Acme speaker", "specs": {"bluetooth": "yes"}})
    assert bundle_roles("Acme bookshelf speakers (Pair)") == ("L", "R")
    assert bundle_roles("Acme bookshelf speakers (Pair)", ("Ls", "Rs")) == ("Ls", "Rs")
    assert bundle_roles("Acme speakers (Pair) with X center") == ("C", "L", "R")
    assert bundle_roles("Acme 5.1 Home Theater System") == ("C", "L", "R", "Ls", "Rs")
    assert bundle_roles("Acme 5.1.2 Home Theater System with subwoofer") == (
        "C", "L", "R", "Ls", "Rs", "LFE")
    assert bundle_roles("Acme 5.1 System with subwoofer") == ("C", "L", "R", "Ls", "Rs", "LFE")
    assert bundle_roles("Acme 5.1 Package") == ("C", "L", "R", "Ls", "Rs")
    assert bundle_roles("Acme surround speakers") == ()


def test_receiver_channels_and_filter():
    row = {"title": "Denon AVR 5.2 AV receiver", "price": 230,
           "specs": {"channels": "5.2", "channel_count": "7"}}
    assert receiver_channels(row) == 5
    assert receiver_eligible(row, 5)
    assert not receiver_eligible(row, 7)
    assert receiver_channels({"specs": {"channel_count": "9"}}) == 7
    for title in ("AV receiver manual", "AV receiver remote", "AV receiver for parts"):
        assert not receiver_eligible({**row, "title": title}, 5)
    assert not receiver_eligible({**row, "price": 149}, 5)
    projector = {"specs": {"resolution": "2160"}}
    assert not receiver_eligible({**row, "title": "1080p only receiver"}, 5, projector)


def test_tv_requires_size_and_combined_share():
    screen = {"width": 8, "height": 4.5}
    small = {"title": "75 inch TV", "price": 300, "specs": {"diagonal_in": "75in"}}
    large = {"title": "100 inch TV", "price": 2500, "specs": {"diagonal_in": "100in"}}
    assert choose_tv([small, large], screen, 1000) is None
    assert choose_tv([small, large], screen, 3000) is large
    assert choose_tv([large], screen, 1000) is None


def test_tv_pool_excludes_undersized_alternatives():
    screen = {"width": 8, "height": 4.5}
    small = {"title": "75 inch TV", "price": 300, "specs": {"diagonal_in": "75in"}}
    large = {"title": "100 inch TV", "price": 2500, "specs": {"diagonal_in": "100in"}}
    assert _role_rows({"display": [small, large]}, "tv", screen, 5) == [large]


def test_projector_upgrade_obeys_strict_double_share():
    current = {"title": "Projector A", "price": 100}
    over_cap = {"title": "Projector B", "price": 205}
    assert not list(_upgrades({"projector": current}, ("projector",), [over_cap],
                              {"projector": 100}, 500, None))


@pytest.fixture
def theater_db(tmp_path, monkeypatch):
    path = tmp_path / "theater.db"
    monkeypatch.setenv("AV_DB", str(path))
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("SERPAPI_KEY", raising=False)
    with catalog.init_db(str(path)) as conn:
        yield conn


def test_tv_reallocates_removed_mount_share(theater_db, monkeypatch):
    tv = {"title": "100 inch TV", "price": 100, "specs": {"diagonal_in": "100in"},
          "link": "https://example.test/tv", "seller": "Shop"}
    monkeypatch.setattr(recommend, "choose_tv", lambda *_: tv)
    original_choice = recommend._choice
    caps = {}

    def track_choice(rows, roles, cap, screen):
        caps[roles] = cap
        return original_choice(rows, roles, cap, screen)

    monkeypatch.setattr(recommend, "_choice", track_choice)
    layout = {"speakers": [{"role": role} for role in ("L", "R", "C")],
              "screen": {"width": 8, "height": 4.5}}
    result = get_products(layout, 1000)
    assert "tv" in {item["role"] for item in result["items"]}
    # C 3 + L/R 4 + receiver 3 + TV 4 + HDMI 0.5 = 14.5 shares.
    assert caps[("C",)] == pytest.approx(1000 * 3 / 14.5)


def test_incompatible_projector_does_not_leave_orphan_screen(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("AV_DB", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("SERPAPI_KEY", raising=False)
    room = Room.model_validate(json.loads(Path("fixtures/room_demo.json").read_text()))
    layout = run_optimize(room)["layout"]
    monkeypatch.setattr(recommend, "receiver_eligible", lambda row, needed, projector=None: projector is None)
    result = get_products(layout, 3000)
    roles = {item["role"] for item in result["items"]}
    assert "projector" not in roles and "screen" not in roles and "mount" not in roles
    assert "no compatible receiver and projector within budget" in result["warnings"]


def test_bundle_pricing_and_included_roles(theater_db):
    catalog.save_listings(theater_db, "speaker bundle", "speaker", [
        listing("Acme A100 Bookshelf Speakers (Pair) with A100 center", 260),
    ])
    result = get_products({"speakers": [{"role": role} for role in ("L", "R", "C")]}, 900)
    by_role = {item["role"]: item for item in result["items"]}
    assert {"L", "R", "C"} <= by_role.keys()
    assert len({by_role[role]["title"] for role in ("L", "R", "C")}) == 1
    assert by_role["C"]["price"] == 260
    assert by_role["L"]["included_in"] == "C" and by_role["R"]["included_in"] == "C"
    assert result["total"] <= 900


def test_full_bundle_pays_once_even_when_catalog_flags_subwoofer(theater_db):
    catalog.save_listings(theater_db, "complete bundle", "speaker", [
        listing("Acme A100 5.1 Home Theater Speaker System with Subwoofer", 700),
    ])
    result = get_products({"speakers": [{"role": role} for role in
                                        ("C", "L", "R", "LFE", "Ls", "Rs")]}, 2000)
    by_role = {item["role"]: item for item in result["items"]}
    assert {"C", "L", "R", "LFE", "Ls", "Rs"} <= by_role.keys()
    assert by_role["C"]["price"] == 700
    assert all(by_role[role]["included_in"] == "C" and by_role[role]["price"] == 0
               for role in ("L", "R", "LFE", "Ls", "Rs"))
    assert result["total"] == 700


def test_center_and_surround_alternatives_keep_context(theater_db):
    catalog.save_listings(theater_db, "speaker families", "speaker", [
        listing("Acme A100 Bookshelf Speaker 150W", 100, rating=4.9, reviews=500),
        listing("Acme A100C Bookshelf Speaker 120W", 120, rating=4.8, reviews=500),
        listing("Acme A100D Bookshelf Speaker 130W", 140, rating=4.7, reviews=500),
        listing("Other B200 Bookshelf Speaker 140W", 90, rating=4.8, reviews=500),
        listing("Other B300 Bookshelf Speaker 130W", 110, rating=4.7, reviews=500),
    ])
    layout = {"speakers": [{"role": role} for role in ("L", "R", "C", "Ls", "Rs")]}
    result = get_products(layout, 2000)
    by_role = {item["role"]: item for item in result["items"]}
    fronts = {model_key(by_role[role]) for role in ("L", "R", "C")}
    assert by_role["C"]["alternatives"]
    assert all(item["specs"].get("brand") == by_role["L"]["specs"].get("brand")
               for item in by_role["C"]["alternatives"])
    assert all(model_key(item) not in fronts for item in by_role["Ls"]["alternatives"])


@pytest.mark.parametrize("budget", [1500, 3000, 5000])
def test_seed_demo_complete_and_fast(tmp_path, monkeypatch, budget):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("AV_DB", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("SERPAPI_KEY", raising=False)
    room = Room.model_validate(json.loads(Path("fixtures/room_demo.json").read_text()))
    layout = run_optimize(room)["layout"]
    start = time.monotonic()
    result = get_products(layout, budget)
    assert time.monotonic() - start < 3
    by_role = {item["role"]: item for item in result["items"]}
    assert {"C", "L", "R", "LFE", "Ls", "Rs", "receiver", "hdmi_cable"} <= by_role.keys()
    assert "tv" in by_role or {"projector", "screen"} <= by_role.keys()
    assert result["total"] <= budget
    assert all(passive_speaker(by_role[role]) for role in ("L", "R", "C", "Ls", "Rs"))
    if budget == 1500:
        assert 1100 <= result["total"]


def test_expand_catalog_dry_run_and_fetch(theater_db, monkeypatch, capsys, tmp_path):
    assert len(expand_catalog.EXTRA_QUERIES) == 20
    queries = expand_catalog.selected_queries("receiver", 2)
    assert len(queries) == 2 and all(category == "av_receiver" for _, category in queries)
    db = tmp_path / "expanded.db"
    assert expand_catalog.run(db, queries, None, dry_run=True) == 0
    assert not db.exists()
    with pytest.raises(ValueError, match="SERPAPI_KEY"):
        expand_catalog.run(db, queries, None)
    calls = []

    def fetch(query, key):
        calls.append((query, key))
        return [listing("Denon AVR-S570BT 5.2 AV receiver", 250)]

    monkeypatch.setattr(catalog, "fetch_with_retry", fetch)
    assert expand_catalog.run(db, queries, "test-key") == 0
    assert len(calls) == 2
    assert "saved 1" in capsys.readouterr().out
    assert db.exists()
