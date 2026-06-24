# Ecovacs GOAT Zones

Custom Home Assistant integration for Ecovacs GOAT zone control.

## What this repo contains

- `custom_components/goaty_zone/`
- `custom_components/goaty_zone/www/goaty-zones-card.js`
- `docs/legacy_yaml_backup.md`
- `hacs.json`

## First setup in Home Assistant

1. Install the integration via HACS or copy it into `/config/custom_components/goaty_zone/`.
2. Restart Home Assistant.
3. Add `Ecovacs GOAT Zones` via Settings -> Devices & services.
4. Open Developer Tools -> Services and run `goaty_zone.get_zones` once.
5. Open Developer Tools -> Services and run `goaty_zone.create_dashboard` once.
6. Open the integration options if you want the GPS tracker: enter the dock latitude/longitude and either a rotation offset or a 2-point calibration.

Example:

```yaml
service: goaty_zone.get_zones
data: {}
```

Dashboard creation:

```yaml
service: goaty_zone.create_dashboard
data:
  dashboard_title: "Goaty"
  overwrite: false
```

After a browser reload the dashboard appears in the sidebar as `Goaty`.

If zones change later, run `goaty_zone.create_dashboard` again with `overwrite: true`.

## Notes

- Zone data is persisted in HA storage under `goaty_zone.zone_config`.
- `sensor.goaty_zones` is the source of truth for the cards and exposes the derived config attributes.
- `input_text.goaty_zones_json` and `input_text.goaty_zones_hash` remain only as compatibility/debug mirrors.
- The latest live zone snapshot is also written to `/config/goaty_zone_areas_last.json` so map edits can be replaced instead of merged forever.
- `goaty_zone.get_due_zones` is the service to use from automations.
- `goaty_zone.create_dashboard` writes a dynamic Lovelace dashboard with `goaty-day-map-card`, `goaty-zones-card`, a compact status section, and a live trail map.
- `GET /api/goaty_zone/path?date=YYYY-MM-DD` returns the historical path for one day; `GET /api/goaty_zone/path/available_dates` returns the paginatable day list.
- There are no per-zone scripts or `shell_command.goaty_*` helpers left in the repo.

## GPS tracker calibration

- Set `dock_latitude` and `dock_longitude` to the real dock position, for example from a map app or by taking the phone to the charging base and copying the coordinates.
- The internal position source is in millimeters. `scale` defaults to `0.001` for mm -> m, while the raw X/Y sensors stay exposed with millimeter units so Home Assistant can convert them to the user's preferred display unit.
- Meter-friendly sensors are exposed as `sensor.goaty_position_x_m`, `sensor.goaty_position_y_m`, plus `sensor.goaty_position_direction` for the relative compass description.
- Use `rotation_offset_deg` when the local GOAT X axis is already in the right scale and you only need orientation.
- Use the 2-point calibration when local coordinates are not in meters or the axis is skewed. Pick two known local points and enter their local values together with their real GPS coordinates. The integration derives rotation and scale from that pair and keeps the dock position as anchor.
- `y_direction` is currently less certain than `x_direction`; if the north/south sign is reversed on another installation, flip `invert_y_axis` in the GPS calibration instead of changing code.
- The integration exposes a `device_tracker` with GPS coordinates alongside the existing local position sensors.
