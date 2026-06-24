from __future__ import annotations

import importlib.util
import math
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parents[1] / "custom_components" / "goaty_zone" / "coordinates.py"
_SPEC = importlib.util.spec_from_file_location("goaty_coordinates", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

derive_two_point_calibration = _MODULE.derive_two_point_calibration
local_to_meters = _MODULE.local_to_meters
local_to_latlon = _MODULE.local_to_latlon


def test_local_to_latlon_origin_returns_dock_position() -> None:
    lat, lon = local_to_latlon(0, 0, 50.0, 10.0, 0.0, 1.0)
    assert lat == 50.0
    assert lon == 10.0


def test_local_to_latlon_northward_offset() -> None:
    lat, lon = local_to_latlon(0.0, 111_320.0, 50.0, 10.0, 0.0, 1.0)
    assert math.isclose(lat, 51.0, rel_tol=0.0, abs_tol=1e-6)
    assert math.isclose(lon, 10.0, rel_tol=0.0, abs_tol=1e-6)


def test_local_to_latlon_eastward_offset() -> None:
    dock_lat = 50.0
    lat, lon = local_to_latlon(111_320.0 * math.cos(math.radians(dock_lat)), 0.0, dock_lat, 10.0, 0.0, 1.0)
    assert math.isclose(lat, dock_lat, rel_tol=0.0, abs_tol=1e-6)
    assert math.isclose(lon, 11.0, rel_tol=0.0, abs_tol=1e-6)


def test_derive_two_point_calibration() -> None:
    calibration = derive_two_point_calibration(
        {"local_x": 0.0, "local_y": 0.0, "latitude": 50.0, "longitude": 10.0},
        {"local_x": 111_320.0 * math.cos(math.radians(50.0)), "local_y": 0.0, "latitude": 50.0, "longitude": 11.0},
    )
    assert math.isclose(calibration["scale"], 1.0, rel_tol=0.0, abs_tol=1e-6)
    assert math.isclose(calibration["rotation_offset_deg"], 0.0, rel_tol=0.0, abs_tol=1e-6)


def test_local_to_latlon_mm_regression_against_reference_measurement() -> None:
    dock_lat = 51.06321
    dock_lon = 11.89711
    x_mm = -30_076.078125
    y_mm = 11_440.641602

    x_m, y_m = local_to_meters(x_mm, y_mm, scale=0.001)
    assert math.isclose(x_m, -30.076078125, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(y_m, 11.440641602, rel_tol=0.0, abs_tol=1e-9)

    lat, lon = local_to_latlon(x_mm, y_mm, dock_lat, dock_lon, 0.0, 0.001)

    expected_lat = dock_lat + (11.440641602 / 111_320.0)
    expected_lon = dock_lon - (30.076078125 / (111_320.0 * math.cos(math.radians(dock_lat))))

    north_error_m = abs(lat - expected_lat) * 111_320.0
    east_error_m = abs(lon - expected_lon) * 111_320.0 * math.cos(math.radians(dock_lat))
    assert math.hypot(north_error_m, east_error_m) <= 2.0
