import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def fixtures_dir():
    return ROOT / "fixtures"


@pytest.fixture
def room_rect(fixtures_dir):
    return json.loads((fixtures_dir / "room_rect.json").read_text(encoding="utf-8"))
