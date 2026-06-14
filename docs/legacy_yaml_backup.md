# Legacy YAML Backup - vor Bereinigung [2026-06-14]

## /config/configuration.yaml
```yaml

# Loads default set of integrations. Do not remove.
default_config:

# Load frontend themes from the themes folder
frontend:
  themes: !include_dir_merge_named themes

automation: !include automations.yaml
script: !include scripts.yaml
scene: !include scenes.yaml
# modbus: !include_dir_merge_list modbus/  # disabled 2026-05-19: BLW/GTW08 YAML-Modbus replaced by broetje_heating HACS integration
template: !include_dir_merge_list template/
python_script:


recorder:
  db_url: mysql://homeassistant:mein-mariaDB-Passwort@core-mariadb/homeassistant?charset=utf8mb4
  purge_keep_days: 900
  commit_interval: 60
  exclude:
    domains:
      - updater
      - persistent_notification
      - camera
      - media_player
    entities:
      - sensor.time
      - sensor.date


homeassistant:
  packages: !include_dir_named packages



  customize_glob:
    "sensor.*_voltage":
      entity_registry_enabled_default: true
    "sensor.*_current":
      entity_registry_enabled_default: true
    "sensor.*_power":
      entity_registry_enabled_default: true

  unit_system: metric

# -----------------------------------------------------------------------------
# HTTP-Konfiguration (SSL, Sicherheitsoptionen)
# -----------------------------------------------------------------------------
http:
  ssl_certificate: /ssl/fullchain.pem
  ssl_key: /ssl/privkey.pem
  ip_ban_enabled: false
  login_attempts_threshold: 5
  



#http:
#  ip_ban_enabled: true
#  login_attempts_threshold: 5


# Local service wrapper for Ecovacs GOAT zone mowing
goaty_zone:
```

## /config/packages/goaty_live_map.yaml
```yaml
# Goaty live-map coordinate conversion
# Orthophoto target: /config/www/goaty_luftbild.jpg exposed as /local/goaty_luftbild.jpg
# Image: 1452 x 2000 px; charger calibration anchor: px 978 / 637.5 = 67.35% / 31.88%
# Assumption corrected 2026-05-18: GOAT robotPos x/y are millimetres-like map units. Divisor 1000 gives real distances of a few metres.
template:
  - sensor:
      - name: "Goaty Bild Left"
        unique_id: goaty_bild_left
        unit_of_measurement: "%"
        state: >
          {% set x = states('sensor.goaty_position_x') | float(0) / 1000 %}
          {% set left = (978.0 + x * 22.4794) / 1452 * 100 %}
          {{ [0, [100, left] | min] | max | round(2) }}
        attributes:
          source_x: "{{ states('sensor.goaty_position_x') }}"
          unit_assumption: "mm"
          charger_left_pct: 67.35
      - name: "Goaty Bild Top"
        unique_id: goaty_bild_top
        unit_of_measurement: "%"
        state: >
          {% set y = states('sensor.goaty_position_y') | float(0) / 1000 %}
          {% set top = (637.5 - y * 22.4578) / 2000 * 100 %}
          {{ [0, [100, top] | min] | max | round(2) }}
        attributes:
          source_y: "{{ states('sensor.goaty_position_y') }}"
          unit_assumption: "mm"
          charger_top_pct: 31.88
      - name: "Goaty Heading Deg"
        unique_id: goaty_heading_deg
        unit_of_measurement: "°"
        state: >
          {{ (states('sensor.goaty_position_heading') | float(0) * 57.29577951308232) | round(1) }}
        attributes:
          source_heading_rad: "{{ states('sensor.goaty_position_heading') }}"
      - name: "Goaty Bild Debug"
        unique_id: goaty_bild_debug
        state: >
          {{ states('sensor.goaty_bild_left') }},{{ states('sensor.goaty_bild_top') }}
        attributes:
          left_pct: "{{ states('sensor.goaty_bild_left') }}"
          top_pct: "{{ states('sensor.goaty_bild_top') }}"
          heading_deg: "{{ states('sensor.goaty_heading_deg') }}"
          mower_state: "{{ states('lawn_mower.goaty') }}"
```

## /config/packages/goaty_mowing_control.yaml
```yaml
input_boolean:
  goaty_mowing_auto_enabled:
    name: Goaty Mähautomatik aktiv
    icon: mdi:robot-mower
  goaty_mowing_manual_override:
    name: Goaty manuelles Mähfenster erzwingen
    icon: mdi:shield-sun
  goaty_zone_active:
    name: Goaty Zone läuft
    icon: mdi:map-marker-path
  goaty_zone_paused_by_window:
    name: Goaty Zone durch Mähfenster pausiert
    icon: mdi:pause-circle
  goaty_false_returning_quiet:
    name: Goaty falsche Heimfahrt stumm
    icon: mdi:bell-off
input_text:
  goaty_current_zone_id:
    name: Goaty aktuelle Zonen-ID
    max: 16
  goaty_current_zone_name:
    name: Goaty aktuelle Zone
    max: 64
  goaty_last_started_zone_id:
    name: Goaty zuletzt gestartete Zonen-ID
    max: 16
  goaty_last_started_zone_name:
    name: Goaty zuletzt gestartete Zone
    max: 64
  goaty_last_block_reason:
    name: Goaty letzter Sperrgrund
    max: 255
    initial: Initialisiert
input_datetime:
  goaty_last_rain_activity:
    name: Goaty letzte Regenaktivität
    has_date: true
    has_time: true
  goaty_current_zone_started:
    name: Goaty aktuelle Zone gestartet
    has_date: true
    has_time: true
  goaty_last_heimfahrt_notification:
    name: Goaty letzte Heimfahrt-Benachrichtigung
    has_date: true
    has_time: true
template:
- binary_sensor:
  - name: Goaty Regen aktiv
    unique_id: goaty_rain_active
    icon: mdi:weather-rainy
    state: '{{ states(''weather.forecast_home'') in [''rainy'', ''pouring'', ''lightning-rainy'']
      }}'
  - name: Goaty Mähfenster aktiv
    unique_id: goaty_mowing_window_active
    icon: mdi:mower-on
    state: "{% set temp = states('sensor.th_outdoor_temperature') | float(state_attr('weather.forecast_home',\
      \ 'temperature') | float(states('sensor.th_outdoor_2_temperature') | float(99)))\
      \ %} {% set rain = is_state('binary_sensor.goaty_regen_aktiv', 'on') %} {% set\
      \ last_rain = as_timestamp(states('input_datetime.goaty_last_rain_activity'),\
      \ 0) %} {% set rain_ok = (not rain) and (last_rain == 0 or now().timestamp()\
      \ - last_rain > 10800) %} {% set rising = as_timestamp(state_attr('sun.sun',\
      \ 'next_rising'), 0) %} {% set setting = as_timestamp(state_attr('sun.sun',\
      \ 'next_setting'), 0) %} {% set today_start = as_timestamp(today_at('00:00'))\
      \ %} {% if rising > now().timestamp() %}\n  {% set rising = rising - 86400 %}\n\
      {% endif %} {% if setting > now().timestamp() + 43200 %}\n  {% set setting =\
      \ setting - 86400 %}\n{% endif %} {% set start = rising + 14400 %} {% set end\
      \ = setting - 3600 %} {{ is_state('input_boolean.goaty_mowing_manual_override',\
      \ 'on') or (now().timestamp() >= start and now().timestamp() <= end and temp\
      \ < 28 and rain_ok) }}"
- sensor:
  - name: mowing_window_active
    unique_id: mowing_window_active
    icon: mdi:mower-on
    state: '{{ is_state(''binary_sensor.goaty_mahfenster_aktiv'', ''on'') }}'
  - name: Goaty effektiver Fehler
    unique_id: goaty_effective_error
    icon: mdi:robot-mower-outline
    state: "{% set raw = states('sensor.goaty_fehler') | int(0) %} {% set desc = state_attr('sensor.goaty_fehler',\
      \ 'description') %} {% set mower = states('lawn_mower.goaty') %} {% set batt\
      \ = states('sensor.goaty_batterie') | float(0) %} {% if raw > 0 and desc in\
      \ [none, '', 'null'] %}\n  0\n{% else %}\n  {{ raw }}\n{% endif %}"
    attributes:
      raw_error: '{{ states(''sensor.goaty_fehler'') }}'
      raw_description: '{{ state_attr(''sensor.goaty_fehler'', ''description'') }}'
      reason: "{% set raw = states('sensor.goaty_fehler') | int(0) %} {% set desc\
        \ = state_attr('sensor.goaty_fehler', 'description') %} {% set mower = states('lawn_mower.goaty')\
        \ %} {% set batt = states('sensor.goaty_batterie') | float(0) %} {% if raw\
        \ > 0 and desc in [none, '', 'null'] %}\n  Rohfehler {{ raw }} ignoriert:\
        \ keine Fehlerbeschreibung; Kommandos werden weiter versucht\n{% else %}\n\
        \  Rohstatus\n{% endif %}"
  - name: Goaty effektiver Status
    unique_id: goaty_effective_status
    icon: mdi:robot-mower
    state: "{% if states('sensor.goaty_effektiver_fehler') | int(0) == 0 and states('sensor.goaty_fehler')\
      \ | int(0) != 0 %}\n  geladen/bereit (Rohfehler ignoriert)\n{% else %}\n  {{\
      \ states('sensor.goaty_mahstatus') }}\n{% endif %}"
  - name: Goaty Mähfenster Start
    unique_id: goaty_mowing_window_start
    device_class: timestamp
    state: '{% set rising = as_timestamp(state_attr(''sun.sun'', ''next_rising''),
      0) %} {% if rising > now().timestamp() %}{% set rising = rising - 86400 %}{%
      endif %} {{ (rising + 14400) | timestamp_custom(''%Y-%m-%dT%H:%M:%S%z'', true)
      }}'
  - name: Goaty Mähfenster Ende
    unique_id: goaty_mowing_window_end
    device_class: timestamp
    state: '{% set setting = as_timestamp(state_attr(''sun.sun'', ''next_setting''),
      0) %} {% if setting > now().timestamp() + 43200 %}{% set setting = setting -
      86400 %}{% endif %} {{ (setting - 3600) | timestamp_custom(''%Y-%m-%dT%H:%M:%S%z'',
      true) }}'
  - name: Goaty Sperrgründe
    unique_id: goaty_mowing_block_reasons
    icon: mdi:lock-alert
    state: "{% if is_state('input_boolean.goaty_mowing_manual_override', 'on') %}\n\
      \  Manuelles Mähfenster aktiv\n{% else %}\n  {% set reasons = [] %}\n  {% set\
      \ temp = states('sensor.th_outdoor_temperature') | float(state_attr('weather.forecast_home',\
      \ 'temperature') | float(states('sensor.th_outdoor_2_temperature') | float(99)))\
      \ %}\n  {% set rain = is_state('binary_sensor.goaty_regen_aktiv', 'on') %}\n\
      \  {% set last_rain = as_timestamp(states('input_datetime.goaty_last_rain_activity'),\
      \ 0) %}\n  {% set rising = as_timestamp(state_attr('sun.sun', 'next_rising'),\
      \ 0) %}\n  {% set setting = as_timestamp(state_attr('sun.sun', 'next_setting'),\
      \ 0) %}\n  {% if rising > now().timestamp() %}{% set rising = rising - 86400\
      \ %}{% endif %}\n  {% if setting > now().timestamp() + 43200 %}{% set setting\
      \ = setting - 86400 %}{% endif %}\n  {% set start = rising + 14400 %}\n  {%\
      \ set end = setting - 3600 %}\n  {% if now().timestamp() < start %}{% set reasons\
      \ = reasons + ['Uhrzeit: vor Mähfenster'] %}{% endif %}\n  {% if now().timestamp()\
      \ > end %}{% set reasons = reasons + ['Uhrzeit: nach Mähfenster'] %}{% endif\
      \ %}\n  {% if temp >= 28 %}{% set reasons = reasons + ['Temperatur: ' ~ temp\
      \ ~ ' °C'] %}{% endif %}\n  {% if rain %}{% set reasons = reasons + ['Regen\
      \ aktiv'] %}{% endif %}\n  {% if (not rain) and last_rain > 0 and now().timestamp()\
      \ - last_rain <= 10800 %}{% set reasons = reasons + ['Regenpause noch ' ~ (((10800\
      \ - (now().timestamp() - last_rain)) / 3600) | round(1)) ~ ' h'] %}{% endif\
      \ %}\n  {{ reasons | join(', ') if reasons else 'keine' }}\n{% endif %}"
  - name: Goaty Mähstatus
    unique_id: goaty_mowing_status
    icon: mdi:robot-mower
    state: '{% if is_state(''lawn_mower.goaty'', ''mowing'') %}mäht {% elif is_state(''lawn_mower.goaty'',
      ''docked'') %}lädt/gedockt {% elif not is_state(''binary_sensor.goaty_mahfenster_aktiv'',
      ''on'') %}gesperrt: {{ states(''sensor.goaty_sperrgrunde'') }} {% else %}bereit{%
      endif %}'
script:
  goaty_notify:
    alias: Goaty Benachrichtigung
    mode: parallel
    fields:
      title:
        description: Titel
      message:
        description: Nachricht
    sequence:
    - service: notify.mobile_app_s22
      continue_on_error: true
      data:
        title: '{{ title | default(''Goaty'') }}'
        message: '{{ message }}'
    - service: notify.persistent_notification
      continue_on_error: true
      data:
        title: '{{ title | default(''Goaty'') }}'
        message: '{{ message }}'
  goaty_refresh_status:
    alias: Goaty Status aktiv abfragen
    mode: single
    sequence:
    - service: homeassistant.update_entity
      continue_on_error: true
      target:
        entity_id:
        - lawn_mower.goaty
        - sensor.goaty_batterie
        - sensor.goaty_fehler
        - sensor.goaty_mahstatus
        - sensor.goaty_sperrgrunde
        - vacuum.goaty_map_proxy
    - delay: 00:00:05
  goaty_resume_current_zone:
    alias: Goaty aktuelle Zone fortsetzen
    mode: single
    sequence:
    - service: script.goaty_refresh_status
    - choose:
      - conditions:
        - condition: template
          value_template: '{{ states(''sensor.goaty_batterie'') | float(0) < 30 }}'
        sequence:
        - service: input_text.set_value
          target:
            entity_id: input_text.goaty_last_block_reason
          data:
            value: 'Akku unter 30%: {{ states(''sensor.goaty_batterie'') }}%'
        - service: lawn_mower.dock
          continue_on_error: true
          target:
            entity_id: lawn_mower.goaty
        - stop: Goaty Akku unter 30%, Fortsetzen abgebrochen.
      - conditions:
        - condition: state
          entity_id: binary_sensor.goaty_mahfenster_aktiv
          state: 'off'
        sequence:
        - stop: Goaty Mähfenster nicht aktiv, Fortsetzen abgebrochen.
      - conditions:
        - condition: template
          value_template: '{{ states(''input_text.goaty_current_zone_id'') | length
            == 0 }}'
        sequence:
        - service: input_boolean.turn_off
          target:
            entity_id: input_boolean.goaty_zone_active
        - service: script.goaty_start_next_ready_zone
        - stop: Keine gespeicherte aktuelle Zone, starte nächste bereite Zone.
    - service: input_boolean.turn_off
      target:
        entity_id: input_boolean.goaty_zone_paused_by_window
    - service: goaty_zone.resume_area
      continue_on_error: true
    - delay: 00:05:00
    - service: script.goaty_refresh_status
    - choose:
      - conditions:
        - condition: state
          entity_id: binary_sensor.goaty_mahfenster_aktiv
          state: 'off'
        sequence:
        - service: input_text.set_value
          target:
            entity_id: input_text.goaty_last_block_reason
          data:
            value: 'Fortsetzen abgebrochen: Mähfenster geschlossen, Zone bleibt pausiert.'
        - service: input_boolean.turn_on
          target:
            entity_id: input_boolean.goaty_zone_paused_by_window
        - service: goaty_zone.pause_area
          continue_on_error: true
        - service: lawn_mower.dock
          continue_on_error: true
          target:
            entity_id: lawn_mower.goaty
        - stop: Goaty Mähfenster während Fortsetzen geschlossen.
      - conditions:
        - condition: template
          value_template: '{{ states(''lawn_mower.goaty'') not in [''mowing'', ''cleaning'']
            }}'
        sequence:
        - service: goaty_zone.start_area
          continue_on_error: true
          data:
            area_id: '{{ states(''input_text.goaty_current_zone_id'') }}'
            device_name: Goaty
        - delay: 00:10:00
        - service: script.goaty_refresh_status
        - choose:
          - conditions:
            - condition: state
              entity_id: binary_sensor.goaty_mahfenster_aktiv
              state: 'off'
            sequence:
            - service: input_text.set_value
              target:
                entity_id: input_text.goaty_last_block_reason
              data:
                value: 'Fortsetzen-Nachprüfung: Mähfenster geschlossen, Zone bleibt
                  pausiert.'
            - service: input_boolean.turn_on
              target:
                entity_id: input_boolean.goaty_zone_paused_by_window
            - service: goaty_zone.pause_area
              continue_on_error: true
            - service: lawn_mower.dock
              continue_on_error: true
              target:
                entity_id: lawn_mower.goaty
          - conditions:
            - condition: template
              value_template: '{{ states(''lawn_mower.goaty'') not in [''mowing'',
                ''cleaning''] }}'
            sequence:
            - service: input_text.set_value
              target:
                entity_id: input_text.goaty_last_block_reason
              data:
                value: Fortsetzen der aktuellen Zone fehlgeschlagen, schicke zum Laden.
            - service: lawn_mower.dock
              continue_on_error: true
              target:
                entity_id: lawn_mower.goaty
  goaty_start_next_ready_zone:
    alias: Goaty nächste fällige Zone starten
    mode: single
    sequence:
    - service: script.goaty_refresh_status
    - variables:
        chosen: "{% set zones = state_attr('sensor.goaty_zones', 'zones') | default([],\
          \ true) %}\n{% set ns = namespace(value='') %}\n{% for z in zones %}\n \
          \ {% set enabled = z.enabled | default(true) %}\n  {% set locked = z.locked\
          \ | default(false) %}\n  {% set due = z.is_due | default(false) %}\n  {%\
          \ if ns.value == '' and enabled and due and not locked %}\n    {% set ns.value\
          \ = (z.id | string) ~ '|' ~ (z.name | default(z.id)) %}\n  {% endif %}\n\
          {% endfor %}\n{{ ns.value }}"
        parts: '{{ chosen.split(''|'') if chosen else [] }}'
    - choose:
      - conditions:
        - condition: template
          value_template: '{{ states(''sensor.goaty_batterie'') | float(0) < 30 }}'
        sequence:
        - service: input_text.set_value
          target:
            entity_id: input_text.goaty_last_block_reason
          data:
            value: 'Akku unter 30%: {{ states(''sensor.goaty_batterie'') }}%'
        - service: vacuum.return_to_base
          continue_on_error: true
          target:
            entity_id: vacuum.goaty_map_proxy
        - stop: Goaty Akku unter 30%, Start abgebrochen.
      - conditions:
        - condition: state
          entity_id: binary_sensor.goaty_mahfenster_aktiv
          state: 'off'
        sequence:
        - service: input_text.set_value
          target:
            entity_id: input_text.goaty_last_block_reason
          data:
            value: '{{ states(''sensor.goaty_sperrgrunde'') }}'
        - service: vacuum.return_to_base
          continue_on_error: true
          target:
            entity_id: vacuum.goaty_map_proxy
        - stop: Goaty Mähfenster nicht aktiv, Start abgebrochen.
    - choose:
      - conditions:
        - condition: template
          value_template: '{{ chosen | length > 0 }}'
        sequence:
        - service: input_text.set_value
          target:
            entity_id: input_text.goaty_current_zone_id
          data:
            value: '{{ parts[0] }}'
        - service: input_text.set_value
          target:
            entity_id: input_text.goaty_current_zone_name
          data:
            value: '{{ parts[1] }}'
        - service: input_text.set_value
          target:
            entity_id: input_text.goaty_last_started_zone_id
          data:
            value: '{{ parts[0] }}'
        - service: input_text.set_value
          target:
            entity_id: input_text.goaty_last_started_zone_name
          data:
            value: '{{ parts[1] }}'
        - service: input_datetime.set_datetime
          target:
            entity_id: input_datetime.goaty_current_zone_started
          data:
            datetime: '{{ now().strftime(''%Y-%m-%d %H:%M:%S'') }}'
        - service: input_boolean.turn_off
          target:
            entity_id: input_boolean.goaty_zone_paused_by_window
        - service: input_boolean.turn_on
          target:
            entity_id: input_boolean.goaty_zone_active
        - service: goaty_zone.mow_zone
          data:
            zone_id: '{{ parts[0] }}'
            zone_name: '{{ parts[1] }}'
        - service: script.goaty_notify
          data:
            title: Goaty startet
            message: Zone {{ parts[1] }} ({{ parts[0] }}) gestartet.
        - delay: 00:06:00
        - service: script.goaty_refresh_status
        - choose:
          - conditions:
            - condition: state
              entity_id: binary_sensor.goaty_mahfenster_aktiv
              state: 'off'
            sequence:
            - service: input_text.set_value
              target:
                entity_id: input_text.goaty_last_block_reason
              data:
                value: 'Start-Nachprüfung: Mähfenster geschlossen, Zone bleibt pausiert.'
            - service: input_boolean.turn_on
              target:
                entity_id: input_boolean.goaty_zone_paused_by_window
            - service: vacuum.return_to_base
              continue_on_error: true
              target:
                entity_id: vacuum.goaty_map_proxy
          - conditions:
            - condition: template
              value_template: '{{ states(''vacuum.goaty_map_proxy'') not in [''cleaning'',
                ''returning''] }}'
            sequence:
            - service: goaty_zone.mow_zone
              continue_on_error: true
              data:
                zone_id: '{{ parts[0] }}'
                zone_name: '{{ parts[1] }}'
      default:
      - service: input_text.set_value
        target:
          entity_id: input_text.goaty_last_block_reason
        data:
          value: Keine fällige und entsperrte Goaty-Zone gefunden.
      - service: script.goaty_notify
        data:
          title: Goaty gesperrt
          message: Keine fällige und entsperrte Goaty-Zone gefunden.
      - service: vacuum.return_to_base
        continue_on_error: true
        target:
          entity_id: vacuum.goaty_map_proxy
  goaty_start_now:
    alias: Goaty Mähen jetzt starten
    mode: single
    sequence:
    - service: input_boolean.turn_on
      target:
        entity_id: input_boolean.goaty_mowing_manual_override
    - service: script.goaty_start_next_ready_zone
  goaty_stop_and_dock:
    alias: Goaty stoppen und heimfahren
    mode: single
    sequence:
    - service: input_boolean.turn_off
      target:
        entity_id:
        - input_boolean.goaty_mowing_manual_override
        - input_boolean.goaty_zone_active
        - input_boolean.goaty_zone_paused_by_window
    - service: goaty_zone.stop_area
      continue_on_error: true
    - service: lawn_mower.dock
      target:
        entity_id: lawn_mower.goaty
    - service: script.goaty_notify
      data:
        title: Goaty Heimfahrt
        message: Goaty wurde gestoppt und zur Ladestation geschickt.
automation:
- id: goaty_track_rain_activity
  alias: Goaty Regenaktivität merken
  mode: single
  trigger:
  - platform: state
    entity_id: weather.forecast_home
  - platform: time_pattern
    minutes: /10
  condition:
  - condition: template
    value_template: '{{ states(''weather.forecast_home'') in [''rainy'', ''pouring'',
      ''lightning-rainy''] }}'
  action:
  - service: input_datetime.set_datetime
    target:
      entity_id: input_datetime.goaty_last_rain_activity
    data:
      datetime: '{{ now().strftime(''%Y-%m-%d %H:%M:%S'') }}'
- id: goaty_mowing_window_guard
  alias: Goaty Mähfenster Wächter
  mode: single
  trigger:
  - platform: state
    entity_id: binary_sensor.goaty_mahfenster_aktiv
  - platform: time_pattern
    minutes: /10
  - platform: state
    entity_id: lawn_mower.goaty
    to: docked
  - platform: state
    entity_id: lawn_mower.goaty
    to:
    - mowing
    - cleaning
  action:
  - choose:
    - conditions:
      - condition: state
        entity_id: binary_sensor.goaty_mahfenster_aktiv
        state: 'off'
      - condition: template
        value_template: '{{ states(''lawn_mower.goaty'') in [''mowing'', ''cleaning'']
          }}'
      sequence:
      - service: input_boolean.turn_off
        target:
          entity_id: input_boolean.goaty_mowing_manual_override
      - service: input_text.set_value
        target:
          entity_id: input_text.goaty_last_block_reason
        data:
          value: 'Sofortstopp: Goaty mäht außerhalb des Mähfensters / zu dunkel.'
      - choose:
        - conditions:
          - condition: state
            entity_id: input_boolean.goaty_zone_active
            state: 'on'
          sequence:
          - service: input_boolean.turn_on
            target:
              entity_id: input_boolean.goaty_zone_paused_by_window
      - service: goaty_zone.pause_area
        continue_on_error: true
      - service: lawn_mower.dock
        continue_on_error: true
        target:
          entity_id: lawn_mower.goaty
    - conditions:
      - condition: state
        entity_id: input_boolean.goaty_mowing_auto_enabled
        state: 'on'
      - condition: state
        entity_id: binary_sensor.goaty_mahfenster_aktiv
        state: 'on'
      - condition: state
        entity_id: input_boolean.goaty_zone_active
        state: 'on'
      - condition: template
        value_template: '{{ states(''sensor.goaty_batterie'') | float(0) >= 30 }}'
      - condition: template
        value_template: "{{ states('lawn_mower.goaty') in ['docked', 'idle', 'paused']\n\
          \   or (states('lawn_mower.goaty') == 'returning'\n       and as_timestamp(now())\
          \ - as_timestamp(states.lawn_mower.goaty.last_updated, 0) > 900) }}"
      sequence:
      - service: script.goaty_resume_current_zone
    - conditions:
      - condition: state
        entity_id: input_boolean.goaty_mowing_auto_enabled
        state: 'on'
      - condition: state
        entity_id: binary_sensor.goaty_mahfenster_aktiv
        state: 'on'
      - condition: state
        entity_id: input_boolean.goaty_zone_active
        state: 'off'
      - condition: template
        value_template: '{{ states(''sensor.goaty_batterie'') | float(0) >= 30 }}'
      - condition: template
        value_template: "{{ states('lawn_mower.goaty') in ['docked', 'idle', 'paused']\n\
          \   or (states('lawn_mower.goaty') == 'returning'\n       and as_timestamp(now())\
          \ - as_timestamp(states.lawn_mower.goaty.last_updated, 0) > 900) }}"
      sequence:
      - service: script.goaty_start_next_ready_zone
    - conditions:
      - condition: state
        entity_id: binary_sensor.goaty_mahfenster_aktiv
        state: 'off'
      - condition: state
        entity_id: input_boolean.goaty_zone_active
        state: 'on'
      - condition: template
        value_template: '{{ states(''lawn_mower.goaty'') not in [''docked'', ''unavailable'',
          ''unknown''] }}'
      sequence:
      - service: input_boolean.turn_off
        target:
          entity_id: input_boolean.goaty_mowing_manual_override
      - service: input_text.set_value
        target:
          entity_id: input_text.goaty_last_block_reason
        data:
          value: 'Mähfenster geschlossen, aktuelle Zone pausiert: {{ states(''input_text.goaty_current_zone_name'')
            }}'
      - service: input_boolean.turn_on
        target:
          entity_id: input_boolean.goaty_zone_paused_by_window
      - service: goaty_zone.pause_area
        continue_on_error: true
      - service: lawn_mower.dock
        target:
          entity_id: lawn_mower.goaty
      - service: script.goaty_notify
        data:
          title: Goaty pausiert
          message: Mähfenster geschlossen. Aktuelle Zone {{ states('input_text.goaty_current_zone_name')
            }} bleibt aktiv und wird beim nächsten Mähfenster fortgesetzt.
    - conditions:
      - condition: state
        entity_id: binary_sensor.goaty_mahfenster_aktiv
        state: 'off'
      - condition: template
        value_template: '{{ states(''lawn_mower.goaty'') not in [''docked'', ''unavailable'',
          ''unknown''] }}'
      sequence:
      - service: input_boolean.turn_off
        target:
          entity_id: input_boolean.goaty_mowing_manual_override
      - service: input_text.set_value
        target:
          entity_id: input_text.goaty_last_block_reason
        data:
          value: '{{ states(''sensor.goaty_sperrgrunde'') }}'
      - service: lawn_mower.dock
        target:
          entity_id: lawn_mower.goaty
      - choose:
        - conditions:
          - condition: template
            value_template: "{{ states('sensor.goaty_effektiver_fehler') | int(0)\
              \ == 0\n   and states('sensor.goaty_batterie') | float(0) >= 95 }}"
          sequence:
          - service: input_boolean.turn_on
            target:
              entity_id: input_boolean.goaty_false_returning_quiet
        default:
        - condition: template
          value_template: '{{ as_timestamp(now()) - as_timestamp(states(''input_datetime.goaty_last_heimfahrt_notification''),
            0) > 21600 }}'
        - service: input_datetime.set_datetime
          target:
            entity_id: input_datetime.goaty_last_heimfahrt_notification
          data:
            datetime: '{{ now().strftime(''%Y-%m-%d %H:%M:%S'') }}'
        - service: script.goaty_notify
          data:
            title: Goaty Heimfahrt
            message: 'Mähfenster geschlossen oder Sperrgrund aktiv: {{ states(''sensor.goaty_sperrgrunde'')
              }}. Goaty fährt zur Ladestation.'
- id: goaty_interrupted_mowing_recovery
  alias: Goaty unterbrochenes Mähen retten
  mode: single
  trigger:
  - platform: state
    entity_id: lawn_mower.goaty
    to:
    - paused
    - idle
    - returning
    - error
    for: 00:18:00
  condition:
  - condition: state
    entity_id: input_boolean.goaty_mowing_auto_enabled
    state: 'on'
  - condition: state
    entity_id: input_boolean.goaty_zone_active
    state: 'on'
  - condition: state
    entity_id: binary_sensor.goaty_mahfenster_aktiv
    state: 'on'
  - condition: template
    value_template: '{{ states(''sensor.goaty_batterie'') | float(0) >= 30 }}'
  action:
  - service: script.goaty_refresh_status
  - service: goaty_zone.resume_area
    continue_on_error: true
  - delay: 00:05:00
  - service: script.goaty_refresh_status
  - choose:
    - conditions:
      - condition: template
        value_template: '{{ states(''lawn_mower.goaty'') not in [''mowing'', ''cleaning'']
          }}'
      sequence:
      - service: goaty_zone.start_area
        continue_on_error: true
        data:
          area_id: '{{ states(''input_text.goaty_current_zone_id'') }}'
          device_name: Goaty
      - delay: 00:10:00
      - service: script.goaty_refresh_status
      - choose:
        - conditions:
          - condition: template
            value_template: '{{ states(''lawn_mower.goaty'') not in [''mowing'', ''cleaning'']
              }}'
          sequence:
          - service: input_text.set_value
            target:
              entity_id: input_text.goaty_last_block_reason
            data:
              value: 'Mähunterbrechung: Resume/Neustart versucht; Rohfehler werden
                ignoriert, Zone bleibt aktiv.'
          - service: goaty_zone.resume_area
            continue_on_error: true
          - service: goaty_zone.start_area
            continue_on_error: true
            data:
              area_id: '{{ states(''input_text.goaty_current_zone_id'') }}'
              device_name: Goaty
- id: goaty_stuck_returning_recovery
  alias: Goaty hängende Heimfahrt retten
  mode: single
  trigger:
  - platform: time_pattern
    minutes: /10
  - platform: state
    entity_id: lawn_mower.goaty
    to: returning
    for: 00:15:00
  condition:
  - condition: state
    entity_id: input_boolean.goaty_mowing_auto_enabled
    state: 'on'
  - condition: template
    value_template: "{{ states('lawn_mower.goaty') == 'returning'\n   and as_timestamp(now())\
      \ - as_timestamp(states.lawn_mower.goaty.last_updated, 0) > 900 }}"
  action:
  - service: script.goaty_refresh_status
  - service: lawn_mower.dock
    continue_on_error: true
    target:
      entity_id: lawn_mower.goaty
  - delay: 00:08:00
  - service: script.goaty_refresh_status
  - choose:
    - conditions:
      - condition: template
        value_template: "{{ states('lawn_mower.goaty') == 'returning'\n   and is_state('binary_sensor.goaty_mahfenster_aktiv',\
          \ 'on')\n   and is_state('input_boolean.goaty_zone_active', 'off')\n   and\
          \ states('sensor.goaty_batterie') | float(0) >= 30 }}"
      sequence:
      - service: script.goaty_start_next_ready_zone
      - delay: 00:08:00
      - service: script.goaty_refresh_status
      - choose:
        - conditions:
          - condition: template
            value_template: '{{ states(''lawn_mower.goaty'') not in [''mowing'', ''cleaning'']
              }}'
          sequence:
          - service: goaty_zone.stop_area
            continue_on_error: true
          - service: lawn_mower.dock
            continue_on_error: true
            target:
              entity_id: lawn_mower.goaty
    - conditions:
      - condition: template
        value_template: '{{ states(''lawn_mower.goaty'') == ''returning'' }}'
      sequence:
      - service: lawn_mower.dock
        continue_on_error: true
        target:
          entity_id: lawn_mower.goaty
- id: goaty_zone_completion_sequence
  alias: Goaty Zone abgeschlossen und nächste wählen
  mode: single
  trigger:
  - platform: state
    entity_id: sensor.goaty_reinigungen_insgesamt
  condition:
  - condition: template
    value_template: '{{ trigger.from_state is not none and trigger.to_state is not
      none and (trigger.to_state.state|int(0)) > (trigger.from_state.state|int(0))
      }}'
  - condition: state
    entity_id: input_boolean.goaty_zone_active
    state: 'on'
  - condition: state
    entity_id: input_boolean.goaty_zone_paused_by_window
    state: 'off'
  action:
  - variables:
      zid: '{% set cur = states(''input_text.goaty_current_zone_id'') %}

        {{ cur if cur | length > 0 else states(''input_text.goaty_last_started_zone_id'')
        }}'
      zname: '{% set cur = states(''input_text.goaty_current_zone_name'') %}

        {{ cur if cur | length > 0 else states(''input_text.goaty_last_started_zone_name'')
        }}'
  - choose:
    - conditions:
      - condition: template
        value_template: '{{ zid | trim | length > 0 }}'
      sequence:
      - service: goaty_zone.mark_zone_mowed
        data:
          zone_id: '{{ zid | trim }}'
          advance_angle: true
  - service: input_boolean.turn_off
    target:
      entity_id:
      - input_boolean.goaty_zone_active
      - input_boolean.goaty_zone_paused_by_window
  - service: input_text.set_value
    target:
      entity_id: input_text.goaty_current_zone_id
    data:
      value: ''
  - service: input_text.set_value
    target:
      entity_id: input_text.goaty_current_zone_name
    data:
      value: ''
  - service: script.goaty_notify
    data:
      title: Goaty Zone fertig
      message: Zone {{ zname }} ({{ zid }}) abgeschlossen. Nächste Prüfung läuft.
  - choose:
    - conditions:
      - condition: state
        entity_id: input_boolean.goaty_mowing_auto_enabled
        state: 'on'
      - condition: state
        entity_id: binary_sensor.goaty_mahfenster_aktiv
        state: 'on'
      sequence:
      - delay: 00:00:20
      - service: script.goaty_start_next_ready_zone
    default:
    - service: vacuum.return_to_base
      continue_on_error: true
      target:
        entity_id: vacuum.goaty_map_proxy
    - choose:
      - conditions:
        - condition: template
          value_template: "{{ states('sensor.goaty_effektiver_fehler') | int(0) ==\
            \ 0\n   and states('sensor.goaty_batterie') | float(0) >= 95\n   and is_state('binary_sensor.goaty_mahfenster_aktiv',\
            \ 'off') }}"
        sequence:
        - service: input_boolean.turn_on
          target:
            entity_id: input_boolean.goaty_false_returning_quiet
        - service: input_text.set_value
          target:
            entity_id: input_text.goaty_last_block_reason
          data:
            value: 'Heimfahrt-Meldung unterdrückt: Goaty wirkt geladen/in Station,
              Rohfehler {{ states(''sensor.goaty_fehler'') }}.'
      default:
      - condition: template
        value_template: '{{ as_timestamp(now()) - as_timestamp(states(''input_datetime.goaty_last_heimfahrt_notification''),
          0) > 21600 }}'
      - service: input_datetime.set_datetime
        target:
          entity_id: input_datetime.goaty_last_heimfahrt_notification
        data:
          datetime: '{{ now().strftime(''%Y-%m-%d %H:%M:%S'') }}'
      - service: script.goaty_notify
        data:
          title: Goaty Heimfahrt
          message: 'Keine weitere Zone gestartet: {{ states(''sensor.goaty_sperrgrunde'')
            }}.'
```

## /config/packages/goaty_path_history.yaml
```yaml
# Goaty path history helpers. HA recorder writes to configured DB backend (MariaDB here).
input_datetime:
  goaty_pfad_datum:
    name: "Goaty Pfad — Datum"
    has_date: true
    has_time: false
```

## /config/packages/goaty_reconnect.yaml
```yaml
# Goaty Ecovacs MQTT reconnect guard
# Reloads the Ecovacs config entry only when Goaty is unavailable and no HA-managed zone is active.

counter:
  goaty_verbindungsverluste:
    name: "Goaty Verbindungsverluste"
    initial: 0
    step: 1
    restore: true

template:
  - sensor:
      - name: "Goaty Verbindungsstatus"
        unique_id: goaty_verbindungsstatus
        icon: >-
          {% if states('lawn_mower.goaty') == 'unavailable' %}
            mdi:wifi-off
          {% else %}
            mdi:wifi
          {% endif %}
        state: >-
          {% if states('lawn_mower.goaty') == 'unavailable' %}
            Getrennt
          {% else %}
            Verbunden
          {% endif %}
      - name: "Goaty Letzte Verbindung"
        unique_id: goaty_letzte_verbindung
        icon: mdi:clock-check-outline
        state: >-
          {{ states.lawn_mower.goaty.last_changed | as_timestamp | timestamp_custom('%d.%m.%Y %H:%M:%S') }}

automation:
  - alias: "Goaty — Verbindung wiederherstellen"
    id: goaty_reconnect
    mode: single
    trigger:
      - platform: state
        entity_id: lawn_mower.goaty
        to: "unavailable"
        for:
          minutes: 2
    condition:
      - condition: state
        entity_id: input_boolean.goaty_zone_active
        state: "off"
    action:
      - service: counter.increment
        continue_on_error: true
        target:
          entity_id: counter.goaty_verbindungsverluste
      - service: logbook.log
        data:
          name: "Goaty Verbindung"
          message: "Verbindung verloren — Reconnect #{{ states('counter.goaty_verbindungsverluste') }} wird versucht."
          entity_id: lawn_mower.goaty
      - service: homeassistant.reload_config_entry
        target:
          entity_id: lawn_mower.goaty
      - service: persistent_notification.create
        data:
          title: "Goaty Verbindung"
          message: >-
            Verbindung verloren — Reconnect #{{ states('counter.goaty_verbindungsverluste') }}
            um {{ now().strftime('%H:%M:%S') }} gestartet.
      - delay:
          seconds: 10
      - choose:
          - conditions:
              - condition: template
                value_template: "{{ states('lawn_mower.goaty') != 'unavailable' }}"
            sequence:
              - service: persistent_notification.create
                data:
                  title: "Goaty Verbindung"
                  message: "Reconnect erfolgreich — Goaty wieder erreichbar."
              - service: logbook.log
                data:
                  name: "Goaty Verbindung"
                  message: "Reconnect erfolgreich — Goaty wieder erreichbar."
                  entity_id: lawn_mower.goaty
        default:
          - service: persistent_notification.create
            data:
              title: "Goaty Verbindung"
              message: "Reconnect versucht, Goaty bleibt aber unavailable."
          - service: logbook.log
            data:
              name: "Goaty Verbindung"
              message: "Reconnect versucht, Goaty bleibt aber unavailable."
              entity_id: lawn_mower.goaty

  - alias: "Goaty — Verbindungsverlust loggen"
    id: goaty_verbindung_log
    mode: queued
    trigger:
      - platform: state
        entity_id: lawn_mower.goaty
        to: "unavailable"
    action:
      - service: logbook.log
        data:
          name: "Goaty Verbindung"
          message: >-
            Verbindung verloren um {{ now().strftime('%H:%M:%S') }};
            Zone aktiv={{ states('input_boolean.goaty_zone_active') }};
            Automatik={{ states('input_boolean.goaty_mowing_auto_enabled') }}.
          entity_id: lawn_mower.goaty
      - service: system_log.write
        continue_on_error: true
        data:
          level: warning
          message: >-
            Goaty unavailable at {{ now().isoformat() }};
            zone_active={{ states('input_boolean.goaty_zone_active') }};
            mower_last_changed={{ states.lawn_mower.goaty.last_changed }}.
```

## /config/packages/goaty_vacuum_proxy.yaml
```yaml
template:
  - vacuum:
      - name: Goaty Map Proxy
        unique_id: goaty_map_proxy
        state: >-
          {% set s = states('lawn_mower.goaty') %}
          {% if s in ['mowing'] %}
            cleaning
          {% elif s in ['paused'] %}
            paused
          {% elif s in ['returning'] %}
            returning
          {% elif s in ['error'] %}
            error
          {% elif s in ['docked'] %}
            docked
          {% else %}
            idle
          {% endif %}
        battery_level: "{{ states('sensor.goaty_batterie') | int(0) }}"
        attributes:
          status: "{{ states('lawn_mower.goaty') }}"
          cleaned_area: "{{ states('sensor.goaty_flache_gereinigt') }}"
          cleaning_time: "{{ states('sensor.goaty_reinigungsdauer') }}"
          error_code: "{{ states('sensor.goaty_fehler') }}"
          error_description: "{{ state_attr('sensor.goaty_fehler', 'description') }}"
        start:
          - action: lawn_mower.start_mowing
            target:
              entity_id: lawn_mower.goaty
        pause:
          - action: lawn_mower.pause
            target:
              entity_id: lawn_mower.goaty
        return_to_base:
          - action: lawn_mower.dock
            target:
              entity_id: lawn_mower.goaty
        stop:
          - action: lawn_mower.pause
            target:
              entity_id: lawn_mower.goaty
```

## /config/packages/goaty_zone_dashboard.yaml
```yaml
# Goaty legacy dashboard helpers migrated to the goaty_zone integration storage services.
# Kept as an empty package stub so package includes do not break.
```

## /config/packages/goaty_zone_helpers.yaml
```yaml
input_text:
  goaty_zones_json:
    name: "Goaty Zonen JSON"
    max: 255
    initial: "[]"
  goaty_zones_hash:
    name: "Goaty Zonen Hash"
    max: 64
    initial: ""

input_select:
  goaty_mow_zone:
    name: "Goaty Mähzone"
    options:
      - "Keine Zonen"

template:
  - sensor:
      - name: "Goaty Fällige Zonen"
        unique_id: goaty_faellige_zonen
        icon: mdi:mower-on
        state: >-
          {% set zones = state_attr('sensor.goaty_zones', 'zones') | default([], true) %}
          {{ zones | selectattr('is_due', 'eq', true) | list | count }}
        attributes:
          zones: >-
            {% set zones = state_attr('sensor.goaty_zones', 'zones') | default([], true) %}
            {{ zones | selectattr('is_due', 'eq', true) | list }}
          names: >-
            {% set zones = state_attr('sensor.goaty_zones', 'zones') | default([], true) %}
            {{ zones | selectattr('is_due', 'eq', true) | map(attribute='name') | list | join(', ') }}

      - name: "Goaty Gesperrte Zonen"
        unique_id: goaty_gesperrte_zonen
        icon: mdi:lock
        state: >-
          {% set zones = state_attr('sensor.goaty_zones', 'zones') | default([], true) %}
          {{ zones | selectattr('locked', 'eq', true) | list | count }}
        attributes:
          zones: >-
            {% set zones = state_attr('sensor.goaty_zones', 'zones') | default([], true) %}
            {{ zones | selectattr('locked', 'eq', true) | list }}
          names: >-
            {% set zones = state_attr('sensor.goaty_zones', 'zones') | default([], true) %}
            {{ zones | selectattr('locked', 'eq', true) | map(attribute='name') | list | join(', ') }}
```

## /config/.storage/lovelace.lovelace - Goaty Views
```json
[]
```

## Aktuelle Goaty-Entities (HA Inventur)
### automation (7)
- automation.goaty_hangende_heimfahrt_retten [on] - Goaty hängende Heimfahrt retten
- automation.goaty_mahfenster_wachter [on] - Goaty Mähfenster Wächter
- automation.goaty_regenaktivitat_merken [on] - Goaty Regenaktivität merken
- automation.goaty_unterbrochenes_mahen_retten [on] - Goaty unterbrochenes Mähen retten
- automation.goaty_verbindung_wiederherstellen [off] - Goaty — Verbindung wiederherstellen
- automation.goaty_verbindungsverlust_loggen [on] - Goaty — Verbindungsverlust loggen
- automation.goaty_zone_abgeschlossen_und_nachste_wahlen [on] - Goaty Zone abgeschlossen und nächste wählen

### binary_sensor (2)
- binary_sensor.goaty_mahfenster_aktiv [off] - Goaty Mähfenster aktiv
- binary_sensor.goaty_regen_aktiv [off] - Goaty Regen aktiv

### button (5)
- button.goaty_dock [unknown] - Goaty Dock
- button.goaty_lebensdauer_der_klinge_zurucksetzen [unknown] - Goaty Lebensdauer der Klinge zurücksetzen
- button.goaty_lebensdauer_der_objektivburste_zurucksetzen [unknown] - Goaty Lebensdauer der Objektivbürste zurücksetzen
- button.goaty_mahen [unknown] - Goaty Mähen
- button.goaty_pause [unknown] - Goaty Pause

### counter (1)
- counter.goaty_verbindungsverluste [193] - Goaty Verbindungsverluste

### event (1)
- event.goaty_letzter_auftrag [unknown] - Goaty Letzter Auftrag

### input_boolean (5)
- input_boolean.goaty_false_returning_quiet [on] - Goaty falsche Heimfahrt stumm
- input_boolean.goaty_mowing_auto_enabled [off] - Goaty Mähautomatik aktiv
- input_boolean.goaty_mowing_manual_override [off] - Goaty manuelles Mähfenster erzwingen
- input_boolean.goaty_zone_active [on] - Goaty Zone läuft
- input_boolean.goaty_zone_paused_by_window [on] - Goaty Zone durch Mähfenster pausiert

### input_datetime (4)
- input_datetime.goaty_current_zone_started [2026-06-02 16:30:05] - Goaty aktuelle Zone gestartet
- input_datetime.goaty_last_heimfahrt_notification [2026-06-08 20:25:00] - Goaty letzte Heimfahrt-Benachrichtigung
- input_datetime.goaty_last_rain_activity [2026-06-14 17:50:00] - Goaty letzte Regenaktivität
- input_datetime.goaty_pfad_datum [2026-06-12] - Goaty Pfad — Datum

### input_number (5)
- input_number.goaty_zone_129_maehrichtung_index [unavailable] - Schafweg Mährichtung Index
- input_number.goaty_zone_130_maehrichtung_index [unavailable] - Hühnerweg Mährichtung Index
- input_number.goaty_zone_131_maehrichtung_index [unavailable] - Barwiesn Mährichtung Index
- input_number.goaty_zone_132_maehrichtung_index [unavailable] - Grubenweg Mährichtung Index
- input_number.goaty_zone_133_maehrichtung_index [unavailable] - Weidenwiese Mährichtung Index

### input_select (2)
- input_select.goaty_maehzone [unavailable] - Goaty Mähzone
- input_select.goaty_mow_zone [Bar1] - Goaty Mähzone

### input_text (7)
- input_text.goaty_current_zone_id [130] - Goaty aktuelle Zonen-ID
- input_text.goaty_current_zone_name [Bar2] - Goaty aktuelle Zone
- input_text.goaty_last_block_reason [Mähfenster geschlossen, aktuelle Zone pausiert: Bar2] - Goaty letzter Sperrgrund
- input_text.goaty_last_started_zone_id [129] - Goaty zuletzt gestartete Zonen-ID
- input_text.goaty_last_started_zone_name [Schafweg] - Goaty zuletzt gestartete Zone
- input_text.goaty_zones_hash [f0f2932a] - Goaty Zonen Hash
- input_text.goaty_zones_json [8 Zonen | hash=f0f2932a] - Goaty Zonen JSON

### lawn_mower (1)
- lawn_mower.goaty [docked] - Goaty

### number (2)
- number.goaty_lautstarke [5] - Goaty Lautstärke
- number.goaty_schnittrichtung [37] - Goaty Schnittrichtung

### script (6)
- script.goaty_notify [off] - Goaty Benachrichtigung
- script.goaty_refresh_status [off] - Goaty Status aktiv abfragen
- script.goaty_resume_current_zone [off] - Goaty aktuelle Zone fortsetzen
- script.goaty_start_next_ready_zone [off] - Goaty nächste fällige Zone starten
- script.goaty_start_now [off] - Goaty Mähen jetzt starten
- script.goaty_stop_and_dock [off] - Goaty stoppen und heimfahren

### select (2)
- select.goaty_mahrichtung [Auto] - Goaty Mahrichtung
- select.goaty_mahzone [Alle] - Goaty Mahzone

### sensor (35)
- sensor.goaty_batterie [100] - Goaty Batterie
- sensor.goaty_bild_debug [40.24,46.53] - Goaty Bild Debug
- sensor.goaty_bild_left [40.24] - Goaty Bild Left
- sensor.goaty_bild_top [46.53] - Goaty Bild Top
- sensor.goaty_effektiver_fehler [0] - Goaty effektiver Fehler
- sensor.goaty_effektiver_status [lädt/gedockt] - Goaty effektiver Status
- sensor.goaty_fallige_zonen [8] - Goaty Fällige Zonen
- sensor.goaty_fallige_zonen_2 [8] - Goaty Fallige Zonen
- sensor.goaty_fehler [0] - Goaty Fehler
- sensor.goaty_flache_gereinigt [99.56] - Goaty Fläche gereinigt
- sensor.goaty_gesamtdauer_der_reinigung [45.2833333333333] - Goaty Gesamtdauer der Reinigung
- sensor.goaty_gesamtflache_gereinigt [7765] - Goaty Gesamtfläche gereinigt
- sensor.goaty_gesperrte_zonen [0] - Goaty Gesperrte Zonen
- sensor.goaty_gesperrte_zonen_2 [0] - Goaty Gesperrte Zonen
- sensor.goaty_heading_deg [38.6] - Goaty Heading Deg
- sensor.goaty_ip_adresse [192.168.2.40] - Goaty IP-Adresse
- sensor.goaty_lebensdauer_der_klinge [49.62] - Goaty Lebensdauer der Klinge
- sensor.goaty_lebensdauer_der_objektivburste [36.4] - Goaty Lebensdauer der Objektivbürste
- sensor.goaty_letzte_verbindung [14.06.2026 20:58:26] - Goaty Letzte Verbindung
- sensor.goaty_mahfenster [Inaktiv] - Goaty Mahfenster
- sensor.goaty_mahfenster_ende [2026-06-14T18:28:35+00:00] - Goaty Mähfenster Ende
- sensor.goaty_mahfenster_start [2026-06-14T06:57:27+00:00] - Goaty Mähfenster Start
- sensor.goaty_mahstatus [lädt/gedockt] - Goaty Mähstatus
- sensor.goaty_mahstatus_2 [docked] - Goaty Mahstatus
- sensor.goaty_position_heading [0.673231] - Goaty Position Heading
- sensor.goaty_position_x [-17516.558594] - Goaty Position X
- sensor.goaty_position_y [-13053.991211] - Goaty Position Y
- sensor.goaty_reinigungen_insgesamt [115] - Goaty Reinigungen insgesamt
- sensor.goaty_reinigungsdauer [77.65] - Goaty Reinigungsdauer
- sensor.goaty_sperrgrunde [Uhrzeit: nach Mähfenster] - Goaty Sperrgründe
- sensor.goaty_verbindungsstatus [Verbunden] - Goaty Verbindungsstatus
- sensor.goaty_wlan_rssi [34] - Goaty WLAN-RSSI
- sensor.goaty_wlan_ssid [privat] - Goaty WLAN-SSID
- sensor.goaty_zones [8 Zonen]
- sensor.goaty_zones_2 [unavailable] - Goaty Zones

### switch (12)
- switch.goaty_barwiesn_sperre [unavailable] - Goaty Barwiesn Sperre
- switch.goaty_erweiterter_modus [on] - Goaty Erweiterter Modus
- switch.goaty_grenzschalter [on] - Goaty Grenzschalter
- switch.goaty_grubenweg_sperre [unavailable] - Goaty Grubenweg Sperre
- switch.goaty_huhnerweg_sperre [unavailable] - Goaty Hühnerweg Sperre
- switch.goaty_kindersicherung [off] - Goaty Kindersicherung
- switch.goaty_safe_protect [off] - Goaty Safe protect
- switch.goaty_schafweg_sperre [unavailable] - Goaty Schafweg Sperre
- switch.goaty_truedetect [off] - Goaty TrueDetect
- switch.goaty_warnung_vor_nach_oben [off] - Goaty Warnung vor „Nach oben“
- switch.goaty_warnung_vor_uberschreitung_der_kartengrenzen [on] - Goaty Warnung vor Überschreitung der Kartengrenzen
- switch.goaty_weidenwiese_sperre [unavailable] - Goaty Weidenwiese Sperre

### vacuum (1)
- vacuum.goaty_map_proxy [docked] - Goaty Map Proxy
