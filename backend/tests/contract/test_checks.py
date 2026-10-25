import json
from pathlib import Path

import pytest

from .checks import (
    assert_valid_classification,
    assert_valid_layout_result,
    assert_valid_metrics,
    assert_valid_products,
    assert_valid_room,
)

ROOT = Path(__file__).resolve().parents[3]


def room():
    return json.loads((ROOT / "fixtures/room_rect.json").read_text())


def layout():
    return json.loads((ROOT / "phoneapp_context/sample_payloads/layout.example.json").read_text())


def test_golden_contracts():
    assert_valid_room(room())
    assert_valid_layout_result(layout(), full_51=False)
    # The layout sample is from a scanned room with different surface UUIDs.
    assert_valid_metrics(layout()["metrics"])
    products = {"budget": 10, "total": 9, "items": [{"role": "L", "title": "x", "price": 9, "currency": "USD", "link": "x", "thumbnail": None, "source": "test"}]}  # noqa: E501  # preserve behavior while retaining the existing expression
    assert_valid_products(products, 10)
    assert_valid_classification([{"surface_id": "wall_n", "material": "drywall", "confidence": 1}], ["wall_n"])


def _room_missing_id(x):
    x.pop("room_id")


def _room_bad_width(x):
    x["dimensions"]["width"] = 0


def _room_bad_polygon(x):
    x["surfaces"][0]["polygon"] = [[0, 0, 0]]

@pytest.mark.parametrize("mutator", [_room_missing_id, _room_bad_width, _room_bad_polygon])
def test_room_check_failures(mutator):
    value = room()
    mutator(value)
    with pytest.raises(AssertionError, match="room|surface"):
        assert_valid_room(value)


def _layout_no_speakers(x):
    x["layout"]["speakers"] = []


def _layout_nan(x):
    x["layout"]["speakers"][0]["position"] = [float("nan")] * 3


def _layout_bad_screen(x):
    x["layout"]["screen"]["width"] = 0

@pytest.mark.parametrize("mutator", [_layout_no_speakers, _layout_nan, _layout_bad_screen])
def test_layout_check_failures(mutator):
    value = layout()
    mutator(value)
    with pytest.raises(AssertionError):
        assert_valid_layout_result(value, full_51=True)


def _products_no_items(x):
    x.pop("items")


def _products_negative(x):
    x["items"][0].update(price=-1)


def _products_wrong_total(x):
    x.update(total=2)

@pytest.mark.parametrize("mutator", [_products_no_items, _products_negative, _products_wrong_total])
def test_product_check_failures(mutator):
    value = {"budget": 10, "total": 9, "items": [{"role": "L", "title": "x", "price": 9, "currency": "USD", "link": "x", "thumbnail": None, "source": "test"}]}  # noqa: E501  # preserve behavior while retaining the existing expression
    mutator(value)
    with pytest.raises(AssertionError):
        assert_valid_products(value, 10)


def _classification_no_material(x):
    x.pop("material")


def _classification_bad_material(x):
    x.update(material="marble")


def _classification_bad_confidence(x):
    x.update(confidence=2)

@pytest.mark.parametrize("mutator", [_classification_no_material, _classification_bad_material, _classification_bad_confidence])  # noqa: E501  # preserve behavior while retaining the existing expression
def test_classification_check_failures(mutator):
    value = {"surface_id": "wall_n", "material": "drywall", "confidence": 1}
    mutator(value)
    with pytest.raises(AssertionError):
        assert_valid_classification([value], ["wall_n"])


def test_classification_rejects_duplicates_and_extras():
    item = {"surface_id": "wall_n", "material": "drywall", "confidence": 1}
    for items in ([item, item.copy()], [item, {**item, "surface_id": "floor"}]):
        with pytest.raises(AssertionError, match="exactly one"):
            assert_valid_classification(items, ["wall_n"])


@pytest.mark.parametrize("field,value", [
    ("delay_ms", float("nan")), ("delay_ms", float("inf")), ("delay_ms", True),
    ("level_db", float("nan")), ("level_db", float("inf")), ("level_db", False),
    ("point", [0, float("nan"), 0]), ("point", [0, float("inf"), 0]),
    ("point", [0, True, 0]),
])
def test_reflection_rejects_nonfinite_and_boolean_numbers(field, value):
    reflection = {"speaker": "L", "surface_id": "wall_n", "delay_ms": 1.0, "level_db": -3.0, "point": [0, 0, 0]}
    reflection[field] = value
    with pytest.raises(AssertionError, match="reflection"):
        assert_valid_metrics({"score": 0.5, "reflections": [reflection], "warnings": []})
