"""The stereo theater preset keeps the quick and refined role sets aligned."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import engine3d
from backend.app.main import create_app
from products import get_products
from products.theater import receiver_channels

ROOT = Path(__file__).resolve().parents[2]
STEREO_ROLES = {"L", "R", "LFE"}


def test_2_1_command_and_schema_mapping(room_rect, tmp_path):
    command = engine3d.build_command(
        room_rect, room_rect["listener"], preset="2.1", output_dir=tmp_path,
        layout_path=tmp_path / "layout.json",
    )
    assert command[command.index("--layout") + 1] == "custom"
    assert command[command.index("--speakers") + 1:command.index("--speakers") + 3] == [
        "front:2", "bass:1",
    ]
    scene = json.loads((ROOT / "fixtures/engine/layout_5.1.json").read_text(encoding="utf-8"))
    scene["speakers"] = [speaker for speaker in scene["speakers"]
                         if speaker["channel"] in STEREO_ROLES]
    scene["layout"] = "custom"
    room_rect["dimensions"] = {"width": 15, "length": 12, "height": 9}
    mapped = engine3d.to_layout(scene, room_rect)["layout"]
    assert mapped["preset"] == "2.1"
    assert {speaker["role"] for speaker in mapped["speakers"]} == STEREO_ROLES


def test_2_1_quick_optimize_and_products(data_dir, monkeypatch):
    monkeypatch.setenv("ENGINE_BACKEND", "stub")
    monkeypatch.setenv("ENGINE3D_BACKEND", "off")
    monkeypatch.delenv("AV_DB", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("SERPAPI_KEY", raising=False)
    client = TestClient(create_app())
    room = client.post("/rooms/rect", json={"width": 12, "length": 15, "budget": 1500}).json()
    root = f"/rooms/{room['room_id']}"
    assert client.post(root + "/optimize", json={"options": {"preset": "9.1"}}).status_code == 422
    response = client.post(root + "/optimize", json={"options": {"preset": "2.1"}})
    assert response.status_code == 200
    layout = response.json()["layout"]
    assert layout["stage"] == "quick" and layout["preset"] == "2.1"
    assert {speaker["role"] for speaker in layout["speakers"]} == STEREO_ROLES
    assert len(layout["speakers"]) == 3
    for speaker in layout["speakers"]:
        x, y, z = speaker["position"]
        assert 0 <= x <= 12 and 0 <= y <= room["dimensions"]["height"] and 0 <= z <= 15
    assert isinstance(response.json()["metrics"], dict)
    products = get_products(layout, 1500)
    roles = {item["role"] for item in products["items"]}
    assert STEREO_ROLES | {"receiver", "projector", "screen"} <= roles
    assert not roles & {"C", "Ls", "Rs"}
    assert products["total"] <= 1500
    by_role = {item["role"]: item for item in products["items"]}
    assert by_role["L"]["title"] == by_role["R"]["title"]
    assert receiver_channels(by_role["receiver"]) >= 2
