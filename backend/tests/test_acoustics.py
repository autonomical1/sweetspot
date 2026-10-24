import copy
import json
import math
import time
from pathlib import Path

from backend.app import acoustics
from backend.app.rooms import RectRequest, build_rect


ROOT = Path(__file__).resolve().parents[2]


def room() -> dict:
    return build_rect(RectRequest(width=18, length=13, height=9, listener=[9, 3.6, 6.5], facing=[0, -1])).model_dump()


def test_image_source_reflection_and_boundary_surfaces():
    value = room()
    layout = {"speakers": [{"role": "L", "position": [3, 3.6, 6.5], "aim": [9, 3.6, 6.5]}]}
    result = acoustics.evaluate(value, layout)
    west = next(item for item in result["reflections"] if item["surface_id"] == "wall_w")
    assert math.isclose(west["delay_ms"], 6 / 1125 * 1000, abs_tol=0.01)
    assert math.isclose(west["level_db"], -6.02 + 10 * math.log10(1 - 0.09), abs_tol=0.01)
    assert {"floor", "ceiling"} <= {item["surface_id"] for item in result["reflections"]}


def test_opening_absorption_wins_and_patches_merge():
    value = room()
    value["surfaces"].append({"id": "window_w", "kind": "window", "polygon": [[0, 2, 5], [0, 2, 8], [0, 6, 8], [0, 6, 5]],
                              "material": "glass", "absorption": {"125": .35, "250": .25, "500": .18, "1000": .5, "2000": .07, "4000": .04}})
    layout = {"speakers": [{"role": "L", "position": [3, 3.6, 6.5], "aim": [9, 3.6, 6.5]},
                            {"role": "R", "position": [3.1, 3.6, 6.5], "aim": [9, 3.6, 6.5]}]}
    result = acoustics.evaluate(value, layout)
    assert any(item["surface_id"] == "window_w" for item in result["reflections"])
    assert sum(item["surface_id"] == "window_w" for item in result["treatment_patches"]) == 1


def test_only_walls_and_windows_receive_treatment_patches():
    value = room()
    layout = {"speakers": [{"role": "L", "position": [3, 3.6, 6.5], "aim": [9, 3.6, 6.5]}]}
    result = acoustics.evaluate(value, layout)
    reflected_surfaces = {item["surface_id"] for item in result["reflections"]}
    assert {"floor", "ceiling"} <= reflected_surfaces
    assert {item["surface_id"] for item in result["treatment_patches"]}.isdisjoint({"floor", "ceiling"})


def test_sabine_area_replaces_wall_area_with_window_area():
    value = room()
    before = acoustics._absorption_area(value)
    value["surfaces"].append({"id": "window_w", "kind": "window", "polygon": [[0, 2, 5], [0, 2, 8], [0, 6, 8], [0, 6, 5]],
                              "material": "glass", "absorption": {"125": .35, "250": .25, "500": .18, "1000": .5, "2000": .07, "4000": .04}})
    # The 3 by 4 ft opening replaces drywall (alpha .08), rather than adding
    # a second overlapping piece of glass to the wall's absorption area.
    assert math.isclose(acoustics._absorption_area(value) - before, 12 * (.18 - .08), abs_tol=1e-8)


def test_score_monotonic_serializable_and_fast():
    value = room()
    near = {"speakers": [{"role": "L", "position": [6, 3.6, 1.304], "aim": [9, 3.6, 6.5]}]}
    wide = {"speakers": [{"role": "L", "position": [3.5, 3.6, 1.5], "aim": [9, 3.6, 6.5]}]}
    assert acoustics.evaluate(value, near)["score"] > acoustics.evaluate(value, wide)["score"]
    start = time.perf_counter()
    result = acoustics.evaluate(value, near)
    assert time.perf_counter() - start < .1
    json.dumps(result)
