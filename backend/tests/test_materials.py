import io
import json
from types import SimpleNamespace

import pytest
from PIL import Image

from backend.app import materials


def test_absorption_table(fixtures_dir):
    assert set(materials.ABSORPTION) == set(materials.MATERIALS)
    for bands in materials.ABSORPTION.values():
        assert set(bands) == set(materials.BANDS)
        assert all(0 < value < 1 for value in bands.values())
    demo = json.loads((fixtures_dir / "room_demo.json").read_text())
    for surface in demo["surfaces"]:
        if surface["material"] in ("drywall", "hardwood", "glass"):
            assert surface["absorption"] == materials.ABSORPTION[surface["material"]]
    assert materials.ABSORPTION["unknown"] == materials.ABSORPTION["drywall"]


@pytest.mark.parametrize("text, expected", [
    ('[{"surface_id":"floor","material":"hardwood","confidence":0.9}]', ("hardwood", 0.9)),
    ('Some prose ```json\n[{"surface_id":"floor","material":"glass","confidence":0.7}]\n``` trailing', ("glass", 0.7)),
    ('{"surfaces":[{"surface_id":"floor","material":"tile","confidence":0.6}]}', ("tile", 0.6)),
    ("not JSON", ("unknown", 0.0)),
    ("[]", ("unknown", 0.0)),
    ('[{"surface_id":"floor","material":"marble","confidence":0.8}]', ("unknown", 0.8)),
    ('[{"surface_id":"floor"}]', ("unknown", 0.0)),
    ('[{"surface_id":"floor","material":"glass","confidence":7}]', ("glass", 1.0)),
    ('[{"surface_id":"floor","material":"glass","confidence":-1}]', ("glass", 0.0)),
])
def test_parse_variants(text, expected):
    result = materials.parse_model_output(text, ["floor"])
    assert result == [{"surface_id": "floor", "material": expected[0], "confidence": expected[1]}]


def test_parse_ids_and_duplicates():
    text = json.dumps([
        {"surface_id": "extra", "material": "glass", "confidence": 1},
        {"surface_id": "floor", "material": "carpet", "confidence": 0.6},
        {"surface_id": "floor", "material": "glass", "confidence": 1},
    ])
    assert materials.parse_model_output(text, ["floor", "wall"]) == [
        {"surface_id": "floor", "material": "carpet", "confidence": 0.6},
        {"surface_id": "wall", "material": "unknown", "confidence": 0.0},
    ]


def _image(width, height):
    stream = io.BytesIO()
    Image.new("RGBA", (width, height), "red").save(stream, "PNG")
    return stream.getvalue()


def test_prepare_image():
    for size, expected in [((4000, 3000), (1024, 768)), ((30, 20), (30, 20))]:
        encoded = materials.prepare_image(_image(*size))
        with Image.open(io.BytesIO(encoded)) as result:
            assert result.size == expected
            assert result.mode == "RGB"
            assert result.format == "JPEG"
    with pytest.raises(ValueError):
        materials.prepare_image(b"random bytes")


def test_mock_and_switch(monkeypatch):
    photos = [{"surface_id": name, "image_bytes": b"data", "mime": "image/jpeg"}
              for name in ("floor", "window_e", "ceiling", "wall_n")]
    expected = [("hardwood", 0.9), ("glass", 0.9), ("drywall", 0.9), ("drywall", 0.8)]
    result = materials.MockClassifier().classify(photos)
    assert [(item["material"], item["confidence"]) for item in result] == expected
    assert materials.classify_materials(photos, backend="mock") == result
    monkeypatch.setenv("MATERIALS_BACKEND", "mock")
    assert materials.classify_materials(photos) == result


class FakeModels:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(text=self.response)


def test_gemini_fake_client(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "test-model")
    photo = [{"surface_id": "floor", "image_bytes": b"jpeg", "mime": "image/jpeg"}]
    models = FakeModels('[{"surface_id":"floor","material":"hardwood","confidence":0.95}]')
    result = materials.GeminiClassifier(client=SimpleNamespace(models=models)).classify(photo)
    assert result[0]["material"] == "hardwood"
    assert models.calls[0]["model"] == "test-model"
    assert models.calls[0]["config"].response_mime_type == "application/json"
    parts = models.calls[0]["contents"][0].parts
    assert "surface_id: floor" in parts[1].text
    assert parts[2].inline_data.data == b"jpeg"


@pytest.mark.parametrize("models", [FakeModels(error=TimeoutError()), FakeModels("bad JSON")])
def test_gemini_failure(models):
    photo = [{"surface_id": "floor", "image_bytes": b"jpeg", "mime": "image/jpeg"}]
    assert materials.GeminiClassifier(client=SimpleNamespace(models=models)).classify(photo) == [
        {"surface_id": "floor", "material": "unknown", "confidence": 0.0}]


def test_gemini_no_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert materials.GeminiClassifier().classify([{"surface_id": "floor"}]) == [
        {"surface_id": "floor", "material": "unknown", "confidence": 0.0}]
