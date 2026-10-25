import copy
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
    value = sample()
    mutator(value)
    assert validate(value)[0]


def test_warning_cases():
    value = sample()
    dto = value["captured_room"]
    dto["surfaces"] = [dto["surfaces"][0]]
    dto["surfaces"][0]["dimensions"][1] = 9
    errors, warnings = validate(value)
    assert not errors
    assert any("walls" in warning for warning in warnings)
    assert any("height" in warning for warning in warnings)


@pytest.mark.parametrize("mutator,fragment", [
    (lambda d: d["surfaces"][0]["transform"].__setitem__(0, 2), "rotation"),
    (lambda d: d["surfaces"][0]["transform"].__setitem__(12, 101), "translation"),
    (lambda d: d["surfaces"].__setitem__(slice(None), d["surfaces"][:2]), "walls"),
    (lambda d: d["surfaces"].__setitem__(slice(None), [s for s in d["surfaces"] if s["category"] != "floor"]), "floor"),
    (lambda d: d["objects"].__setitem__(slice(None), [o for o in d["objects"] if o["category"] != "sofa"]), "sofa"),
    (lambda d: d["objects"].__setitem__(slice(None), [o for o in d["objects"] if o["category"] != "television"]), "television"),  # noqa: E501  # preserve behavior while retaining the existing expression
    (lambda d: d["surfaces"][0]["dimensions"].__setitem__(1, 9), "height"),
])
def test_each_dto_warning_rule(mutator, fragment):
    value = sample()
    mutator(value["captured_room"])
    errors, warnings = validate(value)
    assert not errors
    assert any(fragment in warning for warning in warnings)


@pytest.mark.parametrize("mutator,fragment", [
    (lambda d: d.pop("story"), "story"),
    (lambda d: d.__setitem__("objects", None), "objects"),
    (lambda d: d["objects"][0].__setitem__("category", "lamp"), "category"),
    (lambda d: d["surfaces"][0].__setitem__("dimensions", [1, -1, 0]), "dimensions"),
    (lambda d: d["surfaces"][0]["transform"].__setitem__(15, 0), "transform[15]"),
    (lambda d: d["objects"][0].__setitem__("id", d["surfaces"][0]["id"]), "duplicate"),
])
def test_additional_dto_error_rules(mutator, fragment):
    value = sample()
    mutator(value["captured_room"])
    assert any(fragment in error for error in validate(value)[0])


def test_cli_from_any_cwd():
    path = ROOT / ".contract-dto-test.json"
    path.write_text(json.dumps(sample()))
    script = ROOT / "tools/validate_dto.py"
    try:
        result = subprocess.run([sys.executable, str(script), str(path)], cwd=ROOT.parent, capture_output=True, text=True)  # noqa: E501  # preserve behavior while retaining the existing expression
        assert result.returncode == 0 and "findings:" in result.stdout
    finally:
        path.unlink(missing_ok=True)


@pytest.mark.parametrize("change", [
    lambda x: None,
    lambda x: [],
    lambda x: "text",
    lambda x: {"captured_room": None},
    lambda x: {"captured_room": []},
    lambda x: {"captured_room": "text"},
    lambda x: {"format": ["sweetspot.roomplan.v1"], "surfaces": [], "objects": []},
    lambda x: {**x, "captured_room": {**x["captured_room"], "surfaces": [None]}},
    lambda x: {**x, "captured_room": {**x["captured_room"], "objects": [3]}},
    lambda x: _alter(x, "surfaces", "dimensions", [1, "2", 3]),
    lambda x: _alter(x, "surfaces", "dimensions", [1, [], 3]),
    lambda x: _alter(x, "surfaces", "dimensions", None),
    lambda x: _alter(x, "surfaces", "transform", [1] * 15 + ["1"]),
    lambda x: _alter(x, "surfaces", "transform", [1] * 15 + [[]]),
    lambda x: _alter(x, "surfaces", "category", []),
    lambda x: _alter(x, "surfaces", "id", []),
    lambda x: _alter(x, "objects", "category", {"bad": 1}),
])
def test_malformed_json_values_are_errors(change):
    errors, _ = validate(change(copy.deepcopy(sample())))
    assert errors


def _alter(value, collection, key, replacement):
    value["captured_room"][collection][0][key] = replacement
    return value


@pytest.mark.parametrize("contents", [None, [], "{broken", "", {"captured_room": None}, {"captured_room": []}])
def test_cli_invalid_files_are_clean_errors(tmp_path, contents):
    target = tmp_path / "dto.json"
    if contents is None:
        target = tmp_path / "missing.json"
    elif contents == []:
        target = tmp_path / "directory"
        target.mkdir()
    else:
        target.write_text(json.dumps(contents) if isinstance(contents, dict) else contents)
    result = subprocess.run([sys.executable, str(ROOT / "tools/validate_dto.py"), str(target)], cwd=tmp_path,
                            capture_output=True, text=True)
    assert result.returncode == 1
    assert "ERROR:" in result.stdout
    assert "Traceback" not in result.stdout + result.stderr
