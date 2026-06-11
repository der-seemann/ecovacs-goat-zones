"""Goaty zone-control services."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

DOMAIN = "goaty_zone"
ECOVACS_DOMAIN = "ecovacs"
DEFAULT_DEVICE_NAME = "Goaty"
CARD_RESOURCE_PATH = "/local/goaty-zones-card.js"
CARD_SOURCE = "custom_components/goaty_zone/www/goaty-zones-card.js"
ZONES_TEXT_ENTITY = "input_text.goaty_zones_json"
ZONES_SELECT_ENTITY = "input_select.goaty_mow_zone"

_LOGGER = logging.getLogger(__name__)


def _matches_device(device: Any, wanted: str) -> bool:
    wanted_l = wanted.lower()
    info = getattr(device, "device_info", {}) or {}
    candidates = [
        info.get("nick"),
        info.get("deviceName"),
        info.get("name"),
        info.get("did"),
        info.get("class"),
    ]
    return any(str(value).lower() == wanted_l for value in candidates if value)


def _find_device(hass: HomeAssistant, wanted: str) -> Any:
    entries = hass.config_entries.async_entries(ECOVACS_DOMAIN)
    devices: list[Any] = []
    for entry in entries:
        controller = getattr(entry, "runtime_data", None)
        if controller is None:
            continue
        devices.extend(getattr(controller, "devices", []) or [])

    if not devices:
        raise RuntimeError("No loaded Ecovacs deebot_client devices found")

    for device in devices:
        if _matches_device(device, wanted):
            return device

    for device in devices:
        info = getattr(device, "device_info", {}) or {}
        text = " ".join(str(info.get(key, "")) for key in ("nick", "deviceName", "class"))
        if "goat" in text.lower() or "goaty" in text.lower():
            return device

    names = [getattr(device, "device_info", {}) for device in devices]
    raise RuntimeError(f"No Ecovacs device matching {wanted!r}; available={names!r}")


def _zone_sort_key(zone_id: str) -> tuple[int, str]:
    text = str(zone_id).strip()
    if text.isdecimal():
        return (0, f"{int(text):020d}")
    return (1, text)


def _normalize_subset_list(subsets: Any) -> list[dict[str, str]]:
    zones: dict[str, dict[str, str]] = {}
    if not isinstance(subsets, list):
        return []

    for item in subsets:
        zone_id: Any = None
        zone_name: Any = None

        if isinstance(item, dict):
            zone_id = item.get("mssid") or item.get("id") or item.get("zone_id")
            zone_name = item.get("name") or item.get("zone_name")
        elif isinstance(item, list) and len(item) >= 2:
            zone_id, zone_name = item[0], item[1]

        if zone_id is None or zone_name is None:
            continue

        zone_id_text = str(zone_id).strip()
        zone_name_text = str(zone_name).strip()
        if not zone_id_text or not zone_name_text:
            continue

        zones.setdefault(zone_id_text, {"id": zone_id_text, "name": zone_name_text})

    return sorted(zones.values(), key=lambda zone: _zone_sort_key(zone["id"]))


def _extract_zones_from_response(raw: Any) -> list[dict[str, str]]:
    if isinstance(raw, dict):
        subsets = raw.get("subsets")
        zones = _normalize_subset_list(subsets)
        if zones:
            return zones

        for key in ("resp", "body", "data"):
            nested = raw.get(key)
            if nested is not None:
                zones = _extract_zones_from_response(nested)
                if zones:
                    return zones

    elif isinstance(raw, list):
        for item in raw:
            zones = _extract_zones_from_response(item)
            if zones:
                return zones

    return []


async def _fetch_zones_from_device(hass: HomeAssistant, device: Any) -> list[dict[str, str]]:
    from deebot_client.commands.json.custom import CustomCommand

    commands: list[tuple[str, Any]] = [("getAreaSet", CustomCommand("getAreaSet"))]

    try:
        from deebot_client.commands.json.map import GetMapSet, GetMapSetV2
        from deebot_client.events.map import MapSetType
    except Exception:
        GetMapSet = None
        GetMapSetV2 = None
        MapSetType = None
    else:
        if GetMapSetV2 is not None and MapSetType is not None:
            commands.append(("GetMapSetV2_ROOMS", GetMapSetV2("", MapSetType.ROOMS)))
        if GetMapSet is not None and MapSetType is not None:
            commands.append(("GetMapSet_ROOMS", GetMapSet("", MapSetType.ROOMS)))

    attempts: list[dict[str, Any]] = []
    for label, command in commands:
        try:
            result = await device.execute_command(command)
            raw = result if isinstance(result, dict) else getattr(result, "raw_response", result)
            zones = _extract_zones_from_response(raw)
            attempts.append({"label": label, "zones": zones})
            if zones:
                return zones
        except Exception as exc:
            attempts.append({"label": label, "error": repr(exc)})

    raise RuntimeError(f"Could not read GOAT zones; attempts={attempts!r}")


async def _write_input_text_value(
    hass: HomeAssistant,
    entity_id: str,
    value: str,
    *,
    context: Any | None = None,
) -> None:
    if hass.states.get(entity_id) is not None:
        try:
            await hass.services.async_call(
                "input_text",
                "set_value",
                {"entity_id": entity_id, "value": value},
                blocking=True,
                context=context,
            )
            return
        except Exception:
            _LOGGER.exception("Failed to update %s via input_text service; falling back to state machine", entity_id)

    hass.states.async_set(entity_id, value, {"source": DOMAIN})


async def _write_input_select_options(
    hass: HomeAssistant,
    entity_id: str,
    options: list[str],
    *,
    context: Any | None = None,
) -> None:
    current_state = hass.states.get(entity_id)
    current_value = current_state.state if current_state is not None else None
    desired_value = current_value if current_value in options else (options[0] if options else "")

    if current_state is not None:
        try:
            await hass.services.async_call(
                "input_select",
                "set_options",
                {"entity_id": entity_id, "options": options},
                blocking=True,
                context=context,
            )
            if desired_value:
                await hass.services.async_call(
                    "input_select",
                    "select_option",
                    {"entity_id": entity_id, "option": desired_value},
                    blocking=True,
                    context=context,
                )
            return
        except Exception:
            _LOGGER.exception("Failed to update %s via input_select service; falling back to state machine", entity_id)

    hass.states.async_set(entity_id, desired_value, {"options": options, "source": DOMAIN})


async def _store_zones(
    hass: HomeAssistant,
    zones: list[dict[str, str]],
    *,
    force_update: bool,
    context: Any | None = None,
) -> tuple[bool, str]:
    normalized_zones = sorted(zones, key=lambda zone: _zone_sort_key(zone["id"]))
    new_json = json.dumps(normalized_zones, ensure_ascii=False, separators=(",", ":"))
    new_hash = hashlib.md5(new_json.encode("utf-8")).hexdigest()[:8]
    stored_state = hass.states.get(ZONES_TEXT_ENTITY)
    stored_json = stored_state.state if stored_state is not None else ""
    changed = force_update or stored_json != new_json

    if changed:
        await _write_input_text_value(hass, ZONES_TEXT_ENTITY, new_json, context=context)
        await _write_input_select_options(
            hass,
            ZONES_SELECT_ENTITY,
            [zone["name"] for zone in normalized_zones],
            context=context,
        )

    return changed, new_hash


async def _handle_get_zones_impl(
    hass: HomeAssistant,
    call: ServiceCall,
    *,
    force_update: bool,
) -> None:
    device = _find_device(hass, call.data.get("device_name", DEFAULT_DEVICE_NAME))
    zones = await _fetch_zones_from_device(hass, device)
    changed, new_hash = await _store_zones(
        hass,
        zones,
        force_update=force_update,
        context=call.context,
    )
    _LOGGER.info(
        "GOAT zones %s (%s, hash=%s, count=%d)",
        "updated" if changed else "unchanged",
        "forced" if force_update else "compared",
        new_hash,
        len(zones),
    )


async def _handle_mow_zone_impl(hass: HomeAssistant, call: ServiceCall) -> None:
    from deebot_client.commands.json.clean import CleanAreaV2
    from deebot_client.models import CleanMode

    zone_id = str(call.data["zone_id"]).strip()
    if not zone_id or not zone_id.isdecimal():
        raise ValueError("zone_id must be a decimal Ecovacs zone ID, e.g. 133")

    zone_name = str(call.data.get("zone_name", "")).strip()
    device = _find_device(hass, call.data.get("device_name", DEFAULT_DEVICE_NAME))
    info = getattr(device, "device_info", {}) or {}
    _LOGGER.warning(
        "Starting GOAT zone_id=%s zone_name=%s on Ecovacs device nick=%s class=%s",
        zone_id,
        zone_name or "-",
        info.get("nick"),
        info.get("class"),
    )
    await device.execute_command(CleanAreaV2(CleanMode.SPOT_AREA, [int(zone_id)], 1))


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Register Goaty zone services."""

    www_path = hass.config.path(CARD_SOURCE)
    if os.path.exists(www_path):
        hass.http.register_static_path(CARD_RESOURCE_PATH, www_path, cache_headers=False)

    async def handle_get_zones(call: ServiceCall) -> None:
        await _handle_get_zones_impl(hass, call, force_update=True)

    async def handle_reload_zones(call: ServiceCall) -> None:
        await _handle_get_zones_impl(hass, call, force_update=False)

    async def handle_mow_zone(call: ServiceCall) -> None:
        await _handle_mow_zone_impl(hass, call)

    hass.services.async_register(DOMAIN, "get_zones", handle_get_zones, schema=vol.Schema({}))
    hass.services.async_register(
        DOMAIN,
        "mow_zone",
        handle_mow_zone,
        schema=vol.Schema(
            {
                vol.Required("zone_id"): cv.string,
                vol.Optional("zone_name", default=""): cv.string,
                vol.Optional("device_name", default=DEFAULT_DEVICE_NAME): cv.string,
            }
        ),
    )
    hass.services.async_register(DOMAIN, "reload_zones", handle_reload_zones, schema=vol.Schema({}))
    return True
