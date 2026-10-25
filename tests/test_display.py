import math
import pytest

from speakerplacer.display import (screen_geometry, throw_feasibility,
    horizontal_viewing_angle_deg, screen_brightness, pixel_visibility_distance_m,
    lens_shift_and_keystone, parse_unit_overrides, evaluate_display)


def test_screen_diagonal_aspect_and_letterboxed_image():
    screen=screen_geometry({"diag_in":120,"aspect_ratio":"16:9"})
    assert screen.width_m==pytest.approx(2.6565622)
    wide=screen_geometry({"width_m":3.0,"height_m":1.5,"aspect_ratio":"16:9","image_fit":"fit_height"})
    assert wide.image_width_m==pytest.approx(2.6666667)
    assert wide.image_height_m==pytest.approx(1.5)
    cinemascope=screen_geometry({"width_m":3.,"height_m":1.3,"aspect_ratio":"2.39:1","image_aspect_ratio":"16:9"})
    assert cinemascope.image_height_m==pytest.approx(1.3)
    assert cinemascope.image_width_m<cinemascope.width_m


def test_throw_feasibility_does_not_silently_adjust():
    row=throw_feasibility(2.,5.,1.5,2.2)
    assert not row["feasible"]
    assert row["implied_throw_ratio"]==pytest.approx(2.5)
    assert row["nearest_feasible_distance_m"]==pytest.approx(4.4)
    assert row["zoom_position"]==1.


def test_screen_photometry_viewing_angle_pixels_and_shift():
    brightness=screen_brightness(1600,1.,2.,1.125)
    assert brightness["foot_lamberts"]==pytest.approx(1600/(2*1.125/.3048**2))
    assert brightness["nits"]==pytest.approx(brightness["foot_lamberts"]*3.426)
    angle=horizontal_viewing_angle_deg([0.,0.,1.],[0.,4.,1.],[1.,0.],2.)
    assert angle==pytest.approx(2*math.degrees(math.atan(.25)))
    assert pixel_visibility_distance_m(1.,2160)==pytest.approx(1.59155)
    shift=lens_shift_and_keystone(2.,1.5,1.,4.,keystone_max_deg=10.)
    assert shift["required_vertical_shift"]==pytest.approx(.5)
    assert shift["keystone_allowed"]


def test_unit_overrides_normalize_input_units_at_boundary():
    values=parse_unit_overrides(["diag_in=100","width_in=100","throw_ft=14","aspect=16:9","throw_ratio=1.4:2.2"],"display")
    assert values["diag_in"]==100.
    assert values["width_m"]==pytest.approx(2.54)
    assert values["throw_m"]==pytest.approx(4.2672)
    assert values["aspect_ratio"]==pytest.approx(16/9)
    assert values["throw_ratio_min"]==pytest.approx(1.4)


def test_display_evaluation_reports_throw_brightness_and_seat_metrics():
    result=evaluate_display({"diag_in":100,"aspect_ratio":"16:9","gain":1.0},
        {"throw_ratio_min":1.2,"throw_ratio_max":2.0,"lumens_ansi":2400,"eco_mode_factor":1.,
         "native_resolution":"3840x2160","native_contrast":1000},
        [2.,5.,1.5],[[2.,1.,1.0],[3.,1.,1.1]],target_fl=16.)
    assert result["projector"]["feasible"]
    assert len(result["per_seat"])==2
    assert result["projector"]["lens_shift"]["required_vertical_shift"]==pytest.approx(0.)
    assert result["brightness_status"] in ("PASS","WARN")
