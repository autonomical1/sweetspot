import json
from pathlib import Path
import pytest
from .checks import assert_valid_classification

ROOT = Path(__file__).resolve().parents[3]
IDS = ["wall_n", "wall_s", "floor", "ceiling"]


def test_mock_classification(materials_impl):
    result = materials_impl.classify_materials([], backend="mock")
    assert_valid_classification(result, [])


@pytest.mark.parametrize("name", ["good.json", "fenced_with_prose.txt", "wrong_enum.json", "missing_fields.json", "empty.json", "not_json.txt", "extra_ids.json"])
def test_recorded_model_outputs(materials_impl, name):
    parse = getattr(materials_impl, "parse_model_output", None)
    if parse is None:
        pytest.skip("materials module has no parse_model_output yet")
    text = (ROOT / "fixtures/gemini_responses" / name).read_text()
    try:
        result = parse(text, expected_ids=IDS)
    except TypeError:
        result = parse(text)
    assert_valid_classification(result, IDS)
