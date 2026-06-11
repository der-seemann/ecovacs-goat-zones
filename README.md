# ha-goaty

Custom Home Assistant integration for Ecovacs GOAT zone control.

## What this repo contains

- `custom_components/goaty_zone/`
- `custom_components/goaty_zone/www/goaty-zones-card.js`
- `example_packages/goaty_automations.yaml`
- `hacs.json`

## First setup in Home Assistant

1. Copy the integration into `/config/custom_components/goaty_zone/`.
2. Restart Home Assistant.
3. Open Developer Tools -> Services.
4. Run `goaty_zone.set_zone_config` once for each zone.

Example:

```yaml
service: goaty_zone.set_zone_config
data:
  zone_id: "129"
  enabled: true
  frequency_days: 3
  angles: [0, 45, 90, 135]
```

Repeat that for all configured zones.

## Notes

- Zone data is persisted in HA storage under `goaty_zone.zone_config`.
- `sensor.goaty_zones` exposes the full zone list and the derived config attributes.
- `goaty_zone.get_due_zones` is the service to use from automations.
- `example_packages/goaty_automations.yaml` is a template and must be adapted to the real zone IDs.
