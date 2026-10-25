from backend.app import engine_speakerplacer


def _room(facing: list[float]) -> dict:
    return {"dimensions": {"width": 24.4, "length": 39.0, "height": 9.3}, "surfaces": [], "objects": [],
            "listener": {"position": [12.2, 3.6, 19.7], "facing": facing}}


def test_quick_layout_has_ceiling_projector_aimed_at_screen():
    layout = engine_speakerplacer.optimize(_room([0, -1]))["layout"]
    projector = layout["projector"]
    assert projector["aim"] == layout["screen"]["center"]
    assert projector["position"][1] > 8.0
    assert 0 < projector["position"][2] < 39.0


def test_center_speaker_is_between_left_and_right_when_facing_the_wall():
    positions = {item["role"]: item["position"] for item in engine_speakerplacer.optimize(_room([0, -1]))["layout"]["speakers"]}
    assert positions["L"][0] < positions["C"][0] < positions["R"][0]
