"""Coordinate transforms for Goaty GPS tracking."""

from __future__ import annotations

import math
from typing import Any

METERS_PER_DEGREE_LAT = 111_320.0
DEFAULT_SCALE = 0.001


def _meters_per_degree_lon(latitude_deg: float) -> float:
    return max(1e-9, METERS_PER_DEGREE_LAT * math.cos(math.radians(latitude_deg)))


def local_to_latlon(
    x: float,
    y: float,
    dock_lat: float,
    dock_lon: float,
    rotation_deg: float,
    scale: float = DEFAULT_SCALE,
    invert_y_axis: bool = False,
) -> tuple[float, float]:
    """Convert a local GOAT position to WGS84 latitude/longitude.

    The local frame follows the integration's convention:
    - local +X points east/west when ``rotation_deg`` is 0
    - local +Y points north/south when ``rotation_deg`` is 0
    - ``scale`` converts local units to meters before projection
    - ``invert_y_axis`` flips the Y axis before projection for installations
      that use the opposite north/south sign convention
    """

    theta = math.radians(rotation_deg)
    y_local = -y if invert_y_axis else y
    x_m = scale * x
    y_m = scale * y_local
    east_m = x_m * math.cos(theta) - y_m * math.sin(theta)
    north_m = x_m * math.sin(theta) + y_m * math.cos(theta)

    lat = dock_lat + (north_m / METERS_PER_DEGREE_LAT)
    reference_lat = dock_lat + (north_m / (2.0 * METERS_PER_DEGREE_LAT))
    lon = dock_lon + (east_m / _meters_per_degree_lon(reference_lat))
    return lat, lon


def local_to_meters(x: float, y: float, scale: float = DEFAULT_SCALE, invert_y_axis: bool = False) -> tuple[float, float]:
    """Convert raw GOAT local units to signed meters relative to the dock."""

    y_local = -y if invert_y_axis else y
    return scale * x, scale * y_local


def describe_relative_position(
    x: float,
    y: float,
    scale: float = DEFAULT_SCALE,
    invert_y_axis: bool = False,
) -> dict[str, Any]:
    """Return meter values and compass labels for a local GOAT position."""

    x_m, y_m = local_to_meters(x, y, scale=scale, invert_y_axis=invert_y_axis)
    x_direction = "Ost" if x_m >= 0 else "West"
    y_direction = "Nord" if y_m >= 0 else "Süd"
    return {
        "x_m": x_m,
        "y_m": y_m,
        "x_direction": x_direction,
        "y_direction": y_direction,
        "summary": f"{abs(x_m):.1f} m {x_direction}, {abs(y_m):.1f} m {y_direction}",
    }


def derive_two_point_calibration(
    point1: dict[str, Any],
    point2: dict[str, Any],
) -> dict[str, float]:
    """Derive scale and rotation from two known local/GPS points."""

    local_x1 = float(point1["local_x"])
    local_y1 = float(point1["local_y"])
    local_x2 = float(point2["local_x"])
    local_y2 = float(point2["local_y"])
    lat1 = float(point1["latitude"])
    lon1 = float(point1["longitude"])
    lat2 = float(point2["latitude"])
    lon2 = float(point2["longitude"])

    dx_local = local_x2 - local_x1
    dy_local = local_y2 - local_y1
    local_distance = math.hypot(dx_local, dy_local)
    if local_distance == 0:
        raise ValueError("local calibration points must not be identical")

    mean_lat = (lat1 + lat2) / 2.0
    east_m = (lon2 - lon1) * _meters_per_degree_lon(mean_lat)
    north_m = (lat2 - lat1) * METERS_PER_DEGREE_LAT
    geo_distance = math.hypot(east_m, north_m)
    if geo_distance == 0:
        raise ValueError("GPS calibration points must not be identical")

    local_angle = math.degrees(math.atan2(dy_local, dx_local))
    geo_angle = math.degrees(math.atan2(north_m, east_m))

    return {
        "rotation_offset_deg": geo_angle - local_angle,
        "scale": geo_distance / local_distance,
    }
