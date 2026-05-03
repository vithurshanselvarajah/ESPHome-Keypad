# Home Assistant Integration

## Overview

The device integrates with HA via the **ESPHome encrypted API**. After adding the device in HA (using the `api_encryption_key` from `secrets.yaml`), the following become available:

- **HA entities** — sensors, light, and number entities on the device page
- **HA events** — fired by the device for PIN entry and fingerprint matches
- **HA actions (services)** — called from HA to control the device

---

## Multi-Keypad Setup

Each keypad has a unique `device_name` substitution in `keypad.yaml`. This prefixes all action names and distinguishes entities in HA so multiple keypads on the same instance never conflict.

| `device_name` | Action prefix | Example entity |
|---|---|---|
| `esphome-front-door` | `esphome.esphome_front_door_` | `number.front_door_led_brightness` |
| `esphome-garage` | `esphome.esphome_garage_` | `number.garage_led_brightness` |

**Events** (`keypad_code_entered`, `fingerprint_authenticated`) fire on the same event type from all keypads. Use `trigger.event.origin` in automations to identify which device fired:

```yaml
condition:
  - condition: template
    value_template: "{{ trigger.event.origin == 'esphome-front-door' }}"
```

---

## Events (Device → HA)

Events appear in **Settings → Developer Tools → Events**. Listen to them to build automations.

---

### `esphome.keypad_code_entered`

Fired when a 4-digit PIN is submitted with `#`.

**Condition:** Only fires if the HA API is connected (`api.connected`) or `debug_mode_enabled` is true.

| Field | Type | Example |
|---|---|---|
| `code` | string | `"1234"` |

**Security:** Store PINs in `secrets.yaml`, not in automation YAML. Avoid logging the `code` field. See `automations/pin-access.yaml` for a safe pattern using `input_text` helpers.

---

### `esphome.fingerprint_authenticated`

Fired when a placed finger matches an enrolled template.

**Condition:** Only fires if the HA API is connected (`api.connected`) or `debug_mode_enabled` is true.

| Field | Type | Description |
|---|---|---|
| `id` | string | Slot number of the matched fingerprint |
| `confidence` | string | Match score 0–255 (higher = better match) |

**Mapping slots to people:** Maintain a slot → name mapping using `input_text.fp_slot_N_name` helpers. See `automations/fingerprint-access.yaml`.

---

### `esphome.fingerprint_backup_data`

Fired after a successful `fingerprint_backup_slot` action call.

| Field | Type | Description |
|---|---|---|
| `slot` | string | Slot number that was backed up |
| `data` | string | Base64-encoded 512-byte fingerprint template (~684 chars) |

**Important:** This is the only way to retrieve template data. It is not stored persistently on the ESP. Capture it immediately in an automation — see `automations/fingerprint-backup.yaml`.

> **Note:** Use `input_text` helpers with `max: 1024` to store full templates.

---

## Actions (HA → Device)

Actions are called from **Settings → Developer Tools → Actions** or in automations.

Action names follow the pattern: `esphome.<device_name>_<action_name>`
With `device_name: "esphome-front-door"` the prefix is `esphome.esphome_front_door_`.

---

### `fingerprint_enroll`

Enroll a fingerprint into a specific slot.

| Variable | Type | Description |
|---|---|---|
| `slot` | `int` | Slot number (1 to sensor capacity) |
| `num_scans` | `int` | Number of scans required (typically 2–3) |

After calling: place finger on sensor when the aura LED turns purple. Lift after each blue flash. Blue breathing = enrolled. See `automations/fingerprint-enroll.yaml` for an auto-distribute workflow.

> **Auto-wake:** this action power-cycles the sensor before starting enrollment, so the sensor is always ready regardless of sleep state. The aura ring shows slow blue breathing while awake.

---

### `fingerprint_cancel_enroll`

Cancel any in-progress enrollment. No variables. Safe to call at any time.

---

### `fingerprint_sensor_wake`

Power-cycle the R503 sensor via GPIO47. No variables. The sensor is ready approximately 2 seconds after the call; the aura ring returns to slow blue breathing.

Use this before a sequence of backup/restore operations when you want the sensor awake upfront. All individual backup/restore/delete/enroll actions call this automatically, so you only need it explicitly when batching operations.

```yaml
# Wake the sensor on the front door keypad
service: esphome.esphome_front_door_fingerprint_sensor_wake
```

---

### `fingerprint_delete`

Delete a specific slot. Auto-wakes the sensor first.

| Variable | Type | Description |
|---|---|---|
| `slot` | `int` | Slot number to delete |

---

### `fingerprint_delete_all`

Delete all enrolled fingerprints. Auto-wakes the sensor first. Irreversible.

---

### `fingerprint_backup_slot`

Back up the template stored at `slot` as a base64 string.

| Variable | Type | Description |
|---|---|---|
| `slot` | `int` | Slot to read from |

**Prerequisites:**
- Slot must be enrolled

(Sensor is woken automatically before the backup is attempted.)

**On success:** Fires `esphome.fingerprint_backup_data` event. Result also held in `fp_backup_data_str` global until the next backup call clears it.

**On failure:** No event fired. Check ESPHome logs.

---

### `fingerprint_restore_slot`

Write a previously-backed-up template back into a slot.

| Variable | Type | Description |
|---|---|---|
| `slot` | `int` | Target slot number |
| `data` | `string` | Base64-encoded template from a previous `fingerprint_backup_data` event |

**Prerequisites:** Slot must be enrolled. Sensor is woken automatically.

**After success:** `Fingerprint Count` sensor is refreshed via `fingerprint_sensor.update()`.

---

### `set_led_colour`

Change the status LED colour from HA.

| Variable | Type | Description |
|---|---|---|
| `hex` | `string` | 6-digit RGB hex (`"FF8800"`, `"#FF8800"`), or `"off"` to turn off |
| `brightness` | `int` | 0–100. If 0 or omitted, the current idle brightness is used. When provided, becomes the new idle level. |

Updates the saved LED state globals. If called during the 2s result window after PIN submission, the light is not changed immediately — the colour is applied when `keypad_restore_state` runs at the end of the window.

---

## HA Entities (Device Page)

| Entity | Type | Description |
|---|---|---|
| Fingerprint Count | Sensor | Number of enrolled fingerprints |
| Fingerprint Capacity | Sensor | Maximum slots (200) |
| Status Light | Light | WS2811 strip — direct control; use `set_led_colour` for saved-state tracking |
| LED Brightness | Number | Idle brightness 0–100%. Activity boosts to 100% for 30s then returns here. |

---

## PIN Entry — LED Result Window

After `#` is pressed:
1. The strip flashes **blue x 3** (3 x 150ms on/off)
2. The device waits **2 seconds** for HA to call `set_led_colour`
3. If `set_led_colour` arrives — that colour is applied on restore
4. If nothing arrives — the pre-entry colour is restored

Use the automations in `automations/led-feedback.yaml` to send green (granted) or red (denied) during this window.

---

## Automations

Ready-to-use automations are in the `automations/` folder. See [automations/README.md](../automations/README.md) for the full list.

### PIN access

```yaml
automation:
  - alias: "Keypad: Front Door — PIN access"
    trigger:
      - platform: event
        event_type: esphome.keypad_code_entered
    condition:
      - condition: template
        value_template: "{{ trigger.event.origin == 'esphome-front-door' }}"
      - condition: template
        value_template: "{{ trigger.event.data.code == states('input_text.front_door_pin') }}"
    action:
      - service: lock.unlock
        target:
          entity_id: lock.front_door
      - service: esphome.esphome_front_door_set_led_colour
        data:
          hex: "00FF00"
          brightness: 100
```

### Fingerprint backup and restore to all keypads

```yaml
# Step 1: capture backup data
automation:
  - alias: "Fingerprint: Capture backup"
    trigger:
      - platform: event
        event_type: esphome.fingerprint_backup_data
    action:
      - service: input_text.set_value
        target:
          entity_id: "input_text.fp_backup_slot_{{ trigger.event.data.slot }}"
        data:
          value: "{{ trigger.event.data.data }}"

# Step 2: restore to all keypads
# Fire event: keypad.restore_slot_to_all  data: {slot: 1}
automation:
  - alias: "Fingerprint: Restore to all keypads"
    trigger:
      - platform: event
        event_type: keypad.restore_slot_to_all
    variables:
      slot: "{{ trigger.event.data.slot }}"
      data: "{{ states('input_text.fp_backup_slot_' ~ slot) }}"
    action:
      - service: esphome.esphome_front_door_fingerprint_restore_slot
        data:
          slot: "{{ slot | int }}"
          data: "{{ data }}"
      - delay: "00:00:02"
      - service: esphome.esphome_garage_fingerprint_restore_slot
        data:
          slot: "{{ slot | int }}"
          data: "{{ data }}"
```

Full examples for all scenarios are in `automations/`.

---

## Developer Tools Workflow

### Back up a slot and view the data

1. **Settings → Developer Tools → Events** — listen to `esphome.fingerprint_backup_data`
2. Place a finger on the sensor to wake it
3. **Settings → Developer Tools → Actions** — call `esphome.esphome_front_door_fingerprint_backup_slot` with `slot: 1`
4. The event appears with `slot` and `data` fields

### Test PIN handling

1. **Settings → Developer Tools → Events** — listen to `esphome.keypad_code_entered`
2. Enter a PIN on the physical keypad and press `#`
3. Verify the event appears with the correct `code` and the expected `origin`
