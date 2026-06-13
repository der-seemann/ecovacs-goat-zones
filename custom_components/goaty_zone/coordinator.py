"""Coordinator for Goaty zone-control entities."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
DOMAIN = "goaty_zone"


class GoatyCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Central data source for Goaty entities."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry, zone_store: Any) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self._entry = config_entry
        self._store = zone_store
        self._cfg = dict(config_entry.data)
        self._options = dict(config_entry.options)

    async def _async_update_data(self) -> dict[str, Any]:
        zones = self._get_zones_list()
        window = self._calc_window()
        rain_active = self._check_rain()

        lock_reasons: list[str] = []
        if not window["active"]:
            lock_reasons.append(f"Außerhalb Mähfenster ({window['start']}–{window['end']})")
        if rain_active:
            delay = self._cfg.get("time_window", {}).get("rain_delay_minutes", 60)
            lock_reasons.append(f"Regen (Sperrzeit {delay} min)")

        mower_entity_id = str(self._cfg.get("mower_entity_id") or "").strip()
        mower_state = self.hass.states.get(mower_entity_id) if mower_entity_id else None
        if mower_entity_id and mower_state is None:
            _LOGGER.debug("GOAT mower entity not found yet: %s", mower_entity_id)

        locked_zones = [zone for zone in zones if zone.get("locked")]

        return {
            "zones": zones,
            "due_zones": [zone for zone in zones if zone.get("is_due")],
            "locked_zones": locked_zones,
            "window": window,
            "rain_active": rain_active,
            "lock_reasons": lock_reasons,
            "mower_state": mower_state.state if mower_state is not None else None,
            "mower_state_attributes": dict(mower_state.attributes) if mower_state is not None else {},
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _get_zones_list(self) -> list[dict[str, Any]]:
        zones: list[dict[str, Any]] = []
        for zone_id, config in sorted(self._store.get_all().items(), key=lambda item: item[0]):
            cfg = dict(config)
            try:
                angle_index = max(0, int(cfg.get("angle_index", 0)))
            except (TypeError, ValueError):
                angle_index = 0
            angles = cfg.get("angles") if isinstance(cfg.get("angles"), list) else [0]
            if not angles:
                angles = [0]
            zones.append(
                {
                    "id": str(zone_id),
                    "name": str(cfg.get("name") or zone_id),
                    "enabled": bool(cfg.get("enabled", True)),
                    "frequency_days": cfg.get("frequency_days", 1),
                    "angles": list(angles),
                    "current_angle": self._next_angle_from_config(cfg),
                    "locked": bool(cfg.get("locked", False)),
                    "locked_until": cfg.get("locked_until"),
                    "last_mowed": cfg.get("last_mowed"),
                    "is_due": self._store.is_due(zone_id),
                    "angle_index": angle_index,
                }
            )
        return zones

    def _next_angle_from_config(self, config: dict[str, Any]) -> int:
        angles = config.get("angles") if isinstance(config.get("angles"), list) else [0]
        if not angles:
            angles = [0]
        try:
            idx = int(config.get("angle_index", 0)) % len(angles)
        except (TypeError, ValueError):
            idx = 0
        try:
            return int(angles[idx])
        except (TypeError, ValueError, IndexError):
            return 0

    def _calc_window(self) -> dict[str, Any]:
        tw = self._cfg.get("time_window", {}) or {}
        now = datetime.now(timezone.utc)

        def resolve_time(mode: str, offset_min: int | str | None, fixed_time: str | None, event: str) -> datetime | None:
            if mode == "sun":
                event_time = self._astral_event(event, now)
                if event_time is not None:
                    try:
                        return event_time + timedelta(minutes=int(offset_min or 0))
                    except (TypeError, ValueError):
                        return event_time
            elif fixed_time:
                try:
                    hour, minute = [int(part) for part in str(fixed_time).split(":", 1)]
                except (TypeError, ValueError):
                    return None
                return now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            return None

        start = resolve_time(
            str(tw.get("start_mode", "sun")),
            tw.get("start_offset", 30),
            tw.get("start_time"),
            "sunrise",
        )
        end = resolve_time(
            str(tw.get("end_mode", "sun")),
            tw.get("end_offset", -60),
            tw.get("end_time"),
            "sunset",
        )
        active = bool(start and end and start <= now <= end)
        return {
            "active": active,
            "start": start.strftime("%H:%M") if start else "–",
            "end": end.strftime("%H:%M") if end else "–",
        }

    def _astral_event(self, event: str, now: datetime) -> datetime | None:
        try:
            from homeassistant.helpers import sun as sun_helper
        except Exception:
            return None

        for arg in (now, now.date(), None):
            try:
                if arg is None:
                    result = sun_helper.get_astral_event_date(self.hass, event)
                else:
                    result = sun_helper.get_astral_event_date(self.hass, event, arg)
                return result
            except TypeError:
                continue
            except Exception:
                return None
        return None

    def _check_rain(self) -> bool:
        sensor = str(self._cfg.get("time_window", {}).get("rain_sensor_entity") or "").strip()
        if not sensor:
            return False
        state = self.hass.states.get(sensor)
        return bool(state and state.state == "on")
