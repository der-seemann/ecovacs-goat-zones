"""Shared helpers for Goaty zone-control configuration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry

DOMAIN = "goaty_zone"
GPS_CALIBRATION_KEY = "gps_calibration"


def get_entry_data(config_entry: ConfigEntry) -> dict[str, Any]:
    """Return config entry data merged with options, with options taking precedence."""

    merged = dict(config_entry.data or {})
    merged.update(dict(config_entry.options or {}))
    return merged


def get_gps_calibration(config_entry: ConfigEntry) -> dict[str, Any]:
    """Return the stored GPS calibration block."""

    data = get_entry_data(config_entry)
    calibration = data.get(GPS_CALIBRATION_KEY)
    return dict(calibration) if isinstance(calibration, dict) else {}
