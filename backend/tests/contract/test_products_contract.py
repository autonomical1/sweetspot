import json
from pathlib import Path
import pytest
from .checks import assert_valid_products

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("budget", [0.034, 1, 17.77, 1500])
def test_stub_products(products_impl, budget):
    result = products_impl.get_products({"speakers": [{"role": role} for role in ["L", "R", "C", "LFE", "Ls", "Rs"]], "screen": None}, budget)
    assert_valid_products(result, budget, {"speakers": [{"role": role} for role in ["L", "R", "C", "LFE", "Ls", "Rs"]]})


def test_recorded_serpapi_fixture_shape():
    data = json.loads((ROOT / "fixtures/serpapi_shopping_sample.json").read_text())
    assert data["_note"]
    assert isinstance(data["search_metadata"], dict) and isinstance(data["search_parameters"], dict)
    assert len(data["shopping_results"]) >= 8
    assert all({"position", "title", "source", "thumbnail", "rating", "reviews"} <= set(item) for item in data["shopping_results"])
    assert any("price" not in item for item in data["shopping_results"])
