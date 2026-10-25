from pathlib import Path

import pytest

from .checks import assert_valid_classification

ROOT = Path(__file__).resolve().parents[3]
IDS = ["wall_n", "wall_s", "floor", "ceiling"]


def test_mock_classification(materials_impl):
    import io
    pillow = pytest.importorskip("PIL.Image", reason="Pillow is required to build a valid test JPEG")
    image = pillow.new("RGB", (1, 1), "white")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    ids = ["wall_n", "floor", "ceiling", "window_e"]
    photos = [{"surface_id": surface_id, "image_bytes": buffer.getvalue(), "mime": "image/jpeg"} for surface_id in ids]
    result = materials_impl.classify_materials(photos, backend="mock")
    assert_valid_classification(result, ids)


@pytest.mark.parametrize("name", ["good.json", "fenced_with_prose.txt", "wrong_enum.json", "missing_fields.json", "empty.json", "not_json.txt", "extra_ids.json"])  # noqa: E501  # preserve behavior while retaining the existing expression
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
