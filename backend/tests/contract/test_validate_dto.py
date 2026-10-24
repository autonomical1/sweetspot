import json
import subprocess
import sys
from pathlib import Path
import pytest
from tools.validate_dto import validate

ROOT = Path(__file__).resolve().parents[3]


def sample(): return json.loads((ROOT / "phoneapp_context/sample_payloads/post_rooms_request.example.json").read_text())


def test_sample_is_valid():
    errors, warnings = validate(sample())
    assert errors == []


def _missing_format(x): x["captured_room"].pop("format")
def _bad_surfaces(x): x["captured_room"]["surfaces"] = "bad"
def _short_transform(x): x["captured_room"]["surfaces"][0].update(transform=[0] * 15)
def _bad_is_open(x): x["captured_room"]["surfaces"][0].update(is_open=True)
def _bad_category(x): x["captured_room"]["surfaces"][0].update(category="bad")

@pytest.mark.parametrize("mutator", [_missing_format, _bad_surfaces, _short_transform, _bad_is_open, _bad_category])
def test_dto_error_cases(mutator):
    value = sample(); mutator(value)
    assert validate(value)[0]


def test_warning_cases():
    value = sample(); dto = value["captured_room"]
    dto["surfaces"] = [dto["surfaces"][0]]
    dto["surfaces"][0]["dimensions"][1] = 9
    errors, warnings = validate(value)
    assert not errors
    assert any("walls" in warning for warning in warnings)
    assert any("height" in warning for warning in warnings)


def test_cli_from_any_cwd():
    path = ROOT / ".contract-dto-test.json"
    path.write_text(json.dumps(sample()))
    script = ROOT / "tools/validate_dto.py"
    try:
        result = subprocess.run([sys.executable, str(script), str(path)], cwd=ROOT.parent, capture_output=True, text=True)
        assert result.returncode == 0 and "findings:" in result.stdout
    finally:
        path.unlink(missing_ok=True)
