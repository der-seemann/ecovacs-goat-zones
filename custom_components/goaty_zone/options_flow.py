"""Options flow for Goaty Zone Control."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import config_validation as cv

from .config_flow import (
    CONF_DOCK_LATITUDE,
    CONF_DOCK_LONGITUDE,
    CONF_GPS_ACCURACY,
    CONF_GPS_CALIBRATION,
    CONF_GPS_MODE,
    CONF_GPS_MODE_SIMPLE,
    CONF_GPS_MODE_TWO_POINT,
    CONF_LOCAL_X1,
    CONF_LOCAL_X2,
    CONF_LOCAL_Y1,
    CONF_LOCAL_Y2,
    CONF_REAL_LAT1,
    CONF_REAL_LAT2,
    CONF_REAL_LON1,
    CONF_REAL_LON2,
    CONF_INVERT_Y_AXIS,
    CONF_ROTATION_OFFSET_DEG,
    CONF_SCALE,
    DEFAULT_GPS_ACCURACY,
)
from .coordinates import DEFAULT_SCALE, derive_two_point_calibration
from .settings import get_entry_data


class GoatyOptionsFlowHandler(config_entries.OptionsFlow):
    """Edit the Goaty GPS calibration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry
        self._gps_base: dict[str, Any] = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Alias for the GPS calibration step."""
        return await self.async_step_gps(user_input)

    async def async_step_gps(self, user_input: dict[str, Any] | None = None):
        """Collect the dock-based GPS calibration."""
        errors: dict[str, str] = {}
        existing = get_entry_data(self.config_entry).get(CONF_GPS_CALIBRATION, {})

        if user_input is not None:
            try:
                dock_latitude = float(user_input[CONF_DOCK_LATITUDE])
                dock_longitude = float(user_input[CONF_DOCK_LONGITUDE])
                rotation_offset_deg = float(user_input.get(CONF_ROTATION_OFFSET_DEG, 0.0) or 0.0)
                gps_mode = str(user_input.get(CONF_GPS_MODE) or CONF_GPS_MODE_SIMPLE)
            except (TypeError, ValueError):
                errors["base"] = "invalid_gps"
            else:
                self._gps_base = {
                    CONF_DOCK_LATITUDE: dock_latitude,
                    CONF_DOCK_LONGITUDE: dock_longitude,
                    CONF_ROTATION_OFFSET_DEG: rotation_offset_deg,
                    CONF_INVERT_Y_AXIS: bool(user_input.get(CONF_INVERT_Y_AXIS, False)),
                    CONF_GPS_MODE: gps_mode,
                    CONF_GPS_ACCURACY: DEFAULT_GPS_ACCURACY,
                }
                if gps_mode == CONF_GPS_MODE_TWO_POINT:
                    return await self.async_step_gps_two_point()

                return self.async_create_entry(
                    title="",
                    data={
                        CONF_GPS_CALIBRATION: {
                            **self._gps_base,
                            CONF_SCALE: DEFAULT_SCALE,
                        }
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_DOCK_LATITUDE, default=existing.get(CONF_DOCK_LATITUDE, "")): vol.Coerce(float),
                vol.Required(CONF_DOCK_LONGITUDE, default=existing.get(CONF_DOCK_LONGITUDE, "")): vol.Coerce(float),
                vol.Required(CONF_ROTATION_OFFSET_DEG, default=existing.get(CONF_ROTATION_OFFSET_DEG, 0.0)): vol.Coerce(float),
                vol.Required(CONF_INVERT_Y_AXIS, default=existing.get(CONF_INVERT_Y_AXIS, False)): cv.boolean,
                vol.Required(CONF_GPS_MODE, default=existing.get(CONF_GPS_MODE, CONF_GPS_MODE_SIMPLE)): vol.In(
                    {
                        CONF_GPS_MODE_SIMPLE: "Einfach: Dock + Rotation",
                        CONF_GPS_MODE_TWO_POINT: "2-Punkt-Kalibrierung",
                    }
                ),
            }
        )
        return self.async_show_form(step_id="gps", data_schema=data_schema, errors=errors)

    async def async_step_gps_two_point(self, user_input: dict[str, Any] | None = None):
        """Derive scale and rotation from two known points."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                point1 = {
                    "local_x": float(user_input[CONF_LOCAL_X1]),
                    "local_y": float(user_input[CONF_LOCAL_Y1]),
                    "latitude": float(user_input[CONF_REAL_LAT1]),
                    "longitude": float(user_input[CONF_REAL_LON1]),
                }
                point2 = {
                    "local_x": float(user_input[CONF_LOCAL_X2]),
                    "local_y": float(user_input[CONF_LOCAL_Y2]),
                    "latitude": float(user_input[CONF_REAL_LAT2]),
                    "longitude": float(user_input[CONF_REAL_LON2]),
                }
                derived = derive_two_point_calibration(point1, point2)
            except (KeyError, TypeError, ValueError):
                errors["base"] = "invalid_gps"
            else:
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_GPS_CALIBRATION: {
                            **self._gps_base,
                            CONF_ROTATION_OFFSET_DEG: derived["rotation_offset_deg"],
                            CONF_SCALE: derived["scale"],
                            "points": [point1, point2],
                        }
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_LOCAL_X1): vol.Coerce(float),
                vol.Required(CONF_LOCAL_Y1): vol.Coerce(float),
                vol.Required(CONF_REAL_LAT1): vol.Coerce(float),
                vol.Required(CONF_REAL_LON1): vol.Coerce(float),
                vol.Required(CONF_LOCAL_X2): vol.Coerce(float),
                vol.Required(CONF_LOCAL_Y2): vol.Coerce(float),
                vol.Required(CONF_REAL_LAT2): vol.Coerce(float),
                vol.Required(CONF_REAL_LON2): vol.Coerce(float),
            }
        )
        return self.async_show_form(step_id="gps_two_point", data_schema=data_schema, errors=errors)
