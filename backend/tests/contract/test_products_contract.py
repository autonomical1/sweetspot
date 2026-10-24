import json
from pathlib import Path
import pytest
from .checks import assert_valid_products

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("budget", [0.034, 1, 17.77, 1500])
@pytest.mark.parametrize("with_screen", [False, True])
def test_stub_products(products_impl, budget, with_screen):
    layout = {"speakers": [{"role": role} for role in ["L", "R", "C", "LFE", "Ls", "Rs"]],
              "screen": {"wall_id": "wall_n", "center": [6, 4, 0], "width": 6, "height": 3.4} if with_screen else None}
    result = products_impl.get_products(layout, budget)
    assert_valid_products(result, budget, layout)
    assert ("screen" if with_screen else "projector") in {item["role"] for item in result["items"]}


def test_recorded_serpapi_fixture_shape():
    data = json.loads((ROOT / "fixtures/serpapi_shopping_sample.json").read_text())
    assert data["_note"]
    assert isinstance(data["search_metadata"], dict) and isinstance(data["search_parameters"], dict)
    assert len(data["shopping_results"]) >= 8
    assert all({"position", "title", "source", "thumbnail", "rating", "reviews"} <= set(item) for item in data["shopping_results"])
    assert any("price" not in item for item in data["shopping_results"])


def test_real_products_parameter_is_live_even_with_key(monkeypatch):
    from .conftest import products_impl
    monkeypatch.setenv("SERPAPI_KEY", "dummy")
    real = next(param for param in products_impl._pytestfixturefunction.params if getattr(param, "values", ()) == ("real",))
    assert any(mark.name == "live" for mark in real.marks)
