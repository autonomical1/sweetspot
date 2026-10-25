from backend.app.engine3d import enforce_pair_sides

ROOM = {"dimensions": {"width": 24.0, "length": 39.0, "height": 9.0},
        "listener": {"position": [12.0, 3.6, 20.0], "facing": [0, -1]}}


def _speaker(role: str, x: float, z: float) -> dict:
    return {"role": role, "position": [x, 6.0, z], "aim": [12.0, 3.6, 20.0], "yaw_deg": 10.0}


def test_rear_pair_on_one_side_is_mirrored_across_the_seat_axis():
    speakers = [_speaker("Lrs", 24.0, 34.0), _speaker("Rrs", 23.0, 39.0)]
    notes = enforce_pair_sides(speakers, ROOM)
    by_role = {item["role"]: item["position"] for item in speakers}
    assert len(notes) == 1
    assert by_role["Rrs"][0] > 12.0 > by_role["Lrs"][0]
    assert abs((by_role["Rrs"][0] - 12.0) + (by_role["Lrs"][0] - 12.0)) < 0.2  # symmetric about the seat
    assert by_role["Rrs"][2] == by_role["Lrs"][2] or abs(by_role["Rrs"][2] - by_role["Lrs"][2]) < 6


def test_a_correct_pair_is_left_alone():
    speakers = [_speaker("L", 3.0, 0.0), _speaker("R", 21.0, 0.0)]
    assert enforce_pair_sides(speakers, ROOM) == []
    assert speakers[0]["position"][0] == 3.0 and speakers[1]["position"][0] == 21.0
