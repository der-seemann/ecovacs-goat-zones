"""Device tracker platform for Goaty Zone Control."""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN
from .coordinates import DEFAULT_SCALE, describe_relative_position, local_to_latlon
from .settings import get_gps_calibration

CONF_INVERT_Y_AXIS = "invert_y_axis"

DEFAULT_GPS_ACCURACY = 5.0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the GPS device tracker for Goaty."""

    domain_data = hass.data.setdefault(DOMAIN, {}).setdefault(entry.entry_id, {})
    tracker = GoatyPositionTracker(domain_data, entry)
    domain_data["position_tracker"] = tracker
    async_add_entities([tracker])


class GoatyPositionTracker(TrackerEntity):
    """Expose the last known GOAT position as a GPS tracker."""

    _attr_has_entity_name = False
    _attr_source_type = SourceType.GPS

    def __init__(self, domain_data: dict[str, Any], entry: ConfigEntry) -> None:
        self._domain_data = domain_data
        self._entry = entry
        self._position_data = dict(domain_data.get("position") or {})
        device_name = str(entry.data.get("device_name") or entry.title or "Goaty").strip() or "Goaty"
        self._attr_name = f"{device_name} Position"
        self._attr_unique_id = f"{entry.entry_id}_position_tracker"

    def set_position_data(self, position_data: dict[str, Any]) -> None:
        self._position_data = dict(position_data)
        self._domain_data["position"] = self._position_data
        if self.hass is not None:
            self.async_write_ha_state()

    def _position_source(self) -> dict[str, Any]:
        source = self._domain_data.get("position", self._position_data)
        return source if isinstance(source, dict) else {}

    def _calibration(self) -> dict[str, Any]:
        return get_gps_calibration(self._entry)

    def _local_xy(self) -> tuple[float | None, float | None]:
        source = self._position_source()
        try:
            x = float(source["robot_x"])
            y = float(source["robot_y"])
        except (KeyError, TypeError, ValueError):
            return None, None
        return x, y

    def _gps_coords(self) -> tuple[float | None, float | None]:
        x, y = self._local_xy()
        if x is None or y is None:
            return None, None

        calibration = self._calibration()
        try:
            dock_lat = float(calibration["dock_latitude"])
            dock_lon = float(calibration["dock_longitude"])
        except (KeyError, TypeError, ValueError):
            return None, None

        rotation = float(calibration.get("rotation_offset_deg", 0.0) or 0.0)
        scale = float(calibration.get("scale", DEFAULT_SCALE) or DEFAULT_SCALE)
        invert_y_axis = bool(calibration.get(CONF_INVERT_Y_AXIS, False))
        return local_to_latlon(x, y, dock_lat, dock_lon, rotation, scale, invert_y_axis)

    @property
    def available(self) -> bool:
        lat, lon = self._gps_coords()
        return lat is not None and lon is not None

    @property
    def location_accuracy(self) -> float:
        calibration = self._calibration()
        try:
            return float(calibration.get("gps_accuracy", DEFAULT_GPS_ACCURACY) or DEFAULT_GPS_ACCURACY)
        except (TypeError, ValueError):
            return DEFAULT_GPS_ACCURACY

    @property
    def latitude(self) -> float | None:
        lat, _ = self._gps_coords()
        return lat

    @property
    def longitude(self) -> float | None:
        _, lon = self._gps_coords()
        return lon

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        source = self._position_source()
        calibration = self._calibration()
        lat, lon = self._gps_coords()
        x, y = self._local_xy()
        try:
            scale = float(calibration.get("scale", DEFAULT_SCALE) or DEFAULT_SCALE)
        except (TypeError, ValueError):
            scale = DEFAULT_SCALE
        invert_y_axis = bool(calibration.get(CONF_INVERT_Y_AXIS, False))
        direction = describe_relative_position(x, y, scale=scale, invert_y_axis=invert_y_axis) if x is not None and y is not None else {}
        return {
            "source": source.get("source"),
            "updated_at": source.get("updated_at"),
            "robot_state": source.get("robot_state"),
            "robot_battery": source.get("robot_battery"),
            "charger_x": source.get("charger_x"),
            "charger_y": source.get("charger_y"),
            "local_x": source.get("robot_x"),
            "local_y": source.get("robot_y"),
            "gps_accuracy": self.location_accuracy,
            "dock_latitude": calibration.get("dock_latitude"),
            "dock_longitude": calibration.get("dock_longitude"),
            "rotation_offset_deg": calibration.get("rotation_offset_deg", 0.0),
            "scale": calibration.get("scale", DEFAULT_SCALE),
            "invert_y_axis": invert_y_axis,
            "x_m": direction.get("x_m"),
            "y_m": direction.get("y_m"),
            "x_direction": direction.get("x_direction"),
            "y_direction": direction.get("y_direction"),
            "relative_position": direction.get("summary"),
            "latitude": lat,
            "longitude": lon,
        }
