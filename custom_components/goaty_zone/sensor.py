"""Sensor platform for Goaty Zone Control."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinates import DEFAULT_SCALE, describe_relative_position, local_to_meters
from .coordinator import GoatyCoordinator
from .settings import get_gps_calibration

CONF_INVERT_Y_AXIS = "invert_y_axis"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up coordinator-backed Goaty sensors."""
    domain_data = hass.data.get("goaty_zone", {})
    runtime_data = entry.runtime_data or {}
    coordinator: GoatyCoordinator = (
        domain_data.get(entry.entry_id, {}).get("coordinator")
        or runtime_data["coordinator"]
    )
    entry_data = domain_data.setdefault(entry.entry_id, {})
    position_data = entry_data.get("position", {})

    pos_x = GoatyPositionSensor(
        entry_data,
        entry,
        axis="x",
        name="Position X",
        unit=UnitOfLength.MILLIMETERS,
        kind="raw",
        position_data=position_data,
    )
    pos_y = GoatyPositionSensor(
        entry_data,
        entry,
        axis="y",
        name="Position Y",
        unit=UnitOfLength.MILLIMETERS,
        kind="raw",
        position_data=position_data,
    )
    pos_heading = GoatyPositionSensor(
        entry_data,
        entry,
        axis="heading",
        name="Position Heading",
        unit="°",
        kind="raw",
        position_data=position_data,
        device_class=None,
    )
    pos_x_m = GoatyPositionSensor(
        entry_data,
        entry,
        axis="x",
        name="Position X M",
        unit=UnitOfLength.METERS,
        kind="meter",
        position_data=position_data,
    )
    pos_y_m = GoatyPositionSensor(
        entry_data,
        entry,
        axis="y",
        name="Position Y M",
        unit=UnitOfLength.METERS,
        kind="meter",
        position_data=position_data,
    )
    pos_direction = GoatyPositionDirectionSensor(entry_data, entry, position_data=position_data)

    entities: list[SensorEntity] = [
        GoatyMowingWindowSensor(coordinator),
        GoatyDueZonesSensor(coordinator),
        GoatyLockedZonesSensor(coordinator),
        GoatyMowerStateSensor(coordinator),
        pos_x,
        pos_y,
        pos_heading,
        pos_x_m,
        pos_y_m,
        pos_direction,
    ]
    entry_data["position_sensors"] = {
        "x": pos_x,
        "y": pos_y,
        "heading": pos_heading,
        "x_m": pos_x_m,
        "y_m": pos_y_m,
        "direction": pos_direction,
    }
    async_add_entities(entities)


class GoatyCoordinatorSensor(CoordinatorEntity[GoatyCoordinator], SensorEntity):
    """Base sensor bound to the Goaty coordinator."""

    _attr_has_entity_name = False

    def __init__(self, coordinator: GoatyCoordinator, key: str, name: str, icon: str) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"goaty_{key}"

    @property
    def _data(self) -> dict[str, Any]:
        return self.coordinator.data or {}


class GoatyMowingWindowSensor(GoatyCoordinatorSensor):
    """Expose mowing window state."""

    def __init__(self, coordinator: GoatyCoordinator) -> None:
        super().__init__(coordinator, "mowing_window", "Goaty Mahfenster", "mdi:weather-sunset")

    @property
    def native_value(self) -> str:
        window = self._data.get("window", {})
        return "Aktiv" if window.get("active") else "Inaktiv"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        window = self._data.get("window", {})
        return {
            "start": window.get("start", "–"),
            "end": window.get("end", "–"),
            "rain_active": bool(self._data.get("rain_active", False)),
            "lock_reasons": list(self._data.get("lock_reasons", [])),
            "mower_state": self._data.get("mower_state"),
            "updated_at": self._data.get("updated_at"),
        }


class GoatyDueZonesSensor(GoatyCoordinatorSensor):
    """Expose the number of due zones."""

    def __init__(self, coordinator: GoatyCoordinator) -> None:
        super().__init__(coordinator, "due_zones", "Goaty Fallige Zonen", "mdi:mower-on")

    @property
    def native_value(self) -> int:
        return len(self._data.get("due_zones", []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        zones = list(self._data.get("due_zones", []))
        return {
            "zones": zones,
            "names": ", ".join(zone.get("name", "") for zone in zones if zone.get("name")),
        }


class GoatyLockedZonesSensor(GoatyCoordinatorSensor):
    """Expose the number of locked zones."""

    def __init__(self, coordinator: GoatyCoordinator) -> None:
        super().__init__(coordinator, "locked_zones", "Goaty Gesperrte Zonen", "mdi:lock")

    @property
    def native_value(self) -> int:
        return len(self._data.get("locked_zones", []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        zones = list(self._data.get("locked_zones", []))
        return {
            "zones": zones,
            "names": ", ".join(zone.get("name", "") for zone in zones if zone.get("name")),
        }


class GoatyMowerStateSensor(GoatyCoordinatorSensor):
    """Expose the mower state from Home Assistant."""

    def __init__(self, coordinator: GoatyCoordinator) -> None:
        super().__init__(coordinator, "mower_state", "Goaty Mahstatus", "mdi:mower")

    @property
    def native_value(self) -> str:
        return str(self._data.get("mower_state") or "unavailable")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return dict(self._data.get("mower_state_attributes", {}))


class GoatyPositionSensor(SensorEntity):
    """Expose the last known GOAT position."""

    _attr_has_entity_name = False

    def __init__(
        self,
        domain_data: dict[str, Any],
        entry: ConfigEntry,
        axis: str,
        name: str,
        unit: UnitOfLength | str,
        *,
        kind: str,
        position_data: dict[str, Any] | None = None,
        device_class: SensorDeviceClass | None = SensorDeviceClass.DISTANCE,
    ) -> None:
        self._domain_data = domain_data
        self._entry = entry
        self._axis = axis
        self._kind = kind
        self._position_data = dict(position_data or {})
        self._attr_name = f"Goaty {name}"
        if kind == "raw":
            self._attr_unique_id = f"{entry.entry_id}_position_{axis}"
        else:
            self._attr_unique_id = f"{entry.entry_id}_position_{axis}_m"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = SensorStateClass.MEASUREMENT if device_class is not None else None
        self._attr_icon = "mdi:crosshairs-gps" if axis != "heading" else "mdi:compass-outline"

    def set_position_data(self, position_data: dict[str, Any]) -> None:
        self._position_data = dict(position_data)
        self._domain_data["position"] = self._position_data
        if self.hass is not None:
            self.async_write_ha_state()

    def _position_source(self) -> dict[str, Any]:
        source = self._domain_data.get("position", self._position_data)
        return source if isinstance(source, dict) else {}

    def _axis_key(self) -> str:
        return {
            "x": "robot_x",
            "y": "robot_y",
            "heading": "robot_heading",
        }.get(self._axis, self._axis)

    def _calibration(self) -> dict[str, Any]:
        return get_gps_calibration(self._entry)

    def _scale_and_inversion(self) -> tuple[float, bool]:
        calibration = self._calibration()
        try:
            scale = float(calibration.get("scale", DEFAULT_SCALE) or DEFAULT_SCALE)
        except (TypeError, ValueError):
            scale = DEFAULT_SCALE
        invert_y_axis = bool(calibration.get(CONF_INVERT_Y_AXIS, False))
        return scale, invert_y_axis

    def _raw_xy(self) -> tuple[float | None, float | None]:
        source = self._position_source()
        try:
            x = float(source["robot_x"])
            y = float(source["robot_y"])
        except (KeyError, TypeError, ValueError):
            return None, None
        return x, y

    @property
    def available(self) -> bool:
        if self._kind == "meter" or self._kind == "direction":
            x, y = self._raw_xy()
            return x is not None and y is not None
        return self._axis_key() in self._position_source()

    @property
    def native_value(self) -> float | None:
        source = self._position_source()
        if self._kind == "meter":
            x, y = self._raw_xy()
            if x is None or y is None:
                return None
            scale, invert_y_axis = self._scale_and_inversion()
            x_m, y_m = local_to_meters(x, y, scale=scale, invert_y_axis=invert_y_axis)
            return x_m if self._axis == "x" else y_m

        value = source.get(self._axis_key())
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        source = self._position_source()
        x, y = self._raw_xy()
        scale, invert_y_axis = self._scale_and_inversion()
        direction = describe_relative_position(x, y, scale=scale, invert_y_axis=invert_y_axis) if x is not None and y is not None else {}
        return {
            "source": source.get("source"),
            "updated_at": source.get("updated_at"),
            "robot_state": source.get("robot_state"),
            "robot_battery": source.get("robot_battery"),
            "charger_x": source.get("charger_x"),
            "charger_y": source.get("charger_y"),
            "raw_x": x,
            "raw_y": y,
            "x_m": direction.get("x_m"),
            "y_m": direction.get("y_m"),
            "x_direction": direction.get("x_direction"),
            "y_direction": direction.get("y_direction"),
            "invert_y_axis": invert_y_axis,
        }


class GoatyPositionDirectionSensor(SensorEntity):
    """Expose a human-readable relative position from the dock."""

    _attr_has_entity_name = False

    def __init__(self, domain_data: dict[str, Any], entry: ConfigEntry, position_data: dict[str, Any] | None = None) -> None:
        self._domain_data = domain_data
        self._entry = entry
        self._position_data = dict(position_data or {})
        self._attr_name = "Goaty Position Direction"
        self._attr_unique_id = f"{entry.entry_id}_position_direction"
        self._attr_icon = "mdi:compass"

    def set_position_data(self, position_data: dict[str, Any]) -> None:
        self._position_data = dict(position_data)
        self._domain_data["position"] = self._position_data
        if self.hass is not None:
            self.async_write_ha_state()

    def _position_source(self) -> dict[str, Any]:
        source = self._domain_data.get("position", self._position_data)
        return source if isinstance(source, dict) else {}

    def _raw_xy(self) -> tuple[float | None, float | None]:
        source = self._position_source()
        try:
            return float(source["robot_x"]), float(source["robot_y"])
        except (KeyError, TypeError, ValueError):
            return None, None

    def _calibration(self) -> dict[str, Any]:
        return get_gps_calibration(self._entry)

    @property
    def available(self) -> bool:
        x, y = self._raw_xy()
        return x is not None and y is not None

    @property
    def native_value(self) -> str | None:
        x, y = self._raw_xy()
        if x is None or y is None:
            return None
        calibration = self._calibration()
        try:
            scale = float(calibration.get("scale", DEFAULT_SCALE) or DEFAULT_SCALE)
        except (TypeError, ValueError):
            scale = DEFAULT_SCALE
        invert_y_axis = bool(calibration.get(CONF_INVERT_Y_AXIS, False))
        return describe_relative_position(x, y, scale=scale, invert_y_axis=invert_y_axis)["summary"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        x, y = self._raw_xy()
        calibration = self._calibration()
        try:
            scale = float(calibration.get("scale", DEFAULT_SCALE) or DEFAULT_SCALE)
        except (TypeError, ValueError):
            scale = DEFAULT_SCALE
        invert_y_axis = bool(calibration.get(CONF_INVERT_Y_AXIS, False))
        direction = describe_relative_position(x, y, scale=scale, invert_y_axis=invert_y_axis) if x is not None and y is not None else {}
        source = self._position_source()
        return {
            "source": source.get("source"),
            "updated_at": source.get("updated_at"),
            "raw_x": x,
            "raw_y": y,
            "x_m": direction.get("x_m"),
            "y_m": direction.get("y_m"),
            "x_direction": direction.get("x_direction"),
            "y_direction": direction.get("y_direction"),
            "summary": direction.get("summary"),
            "invert_y_axis": invert_y_axis,
        }
