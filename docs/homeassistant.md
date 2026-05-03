# Home Assistant Integration

## Overview

The device integrates with HA via the **ESPHome encrypted API**. After adding the device in HA (using the `api_encryption_key` from `secrets.yaml`), the following become available:

- **HA entities** — sensors, light, number, and text sensor entities on the device page
- **HA events** — fired by the device for PIN entry and fingerprint matches
- **HA actions (services)** — called from HA to control the device

---

## Primary Use Case — Alarm Arm/Disarm

The keypad is designed to arm and disarm a home security alarm via PIN or fingerprint.
The LED colour acts as the alarm state indicator visible from the keypad:

| LED colour | Alarm state |
|---|---|
| Green `#33FF00` | Armed |
| Red `#FF0000` | Disarmed |

The `LED Colour Hex` sensor (`sensor.<device>_led_colour_hex`) exposes the current colour
to HA so automations can read it as the alarm state without a separate state entity.

### How a PIN entry works

1. User enters 4 digits and presses `#`.
2. The keypad plays a **blue flash × 3** progress indicator.
3. The LED then **breathes in the current saved colour** for ~10 seconds
   (green if armed, red if disarmed).
4. HA receives the `esphome.keypad_code_entered` event.
5. If the PIN matches, HA waits 2 seconds (so the breathing is visible),
   then calls `set_led_colour` with the new state colour and arms/disarms the alarm.
6. The new colour is visible on the LED — confirming the state change.

---

## Device Identification

Each device has a unique suffix added to its name (`name_add_mac_suffix: true`).
The actual device name will look like `esphome-keypad-58066c`.

### Finding your device_id

Events carry a `device_id` field. To find yours:

1. Go to **Settings → Developer Tools → Events**
2. Listen for `esphome.keypad_code_entered`
3. Press `#` on the keypad
4. Copy the `device_id` from the event data (e.g. `49e04c941b3fdf876fd0390eb5a6ff1a`)

Use this `device_id` in trigger `event_data` filters — it uniquely identifies
the physical device regardless of its name.

---

## Multi-Keypad Setup

Each keypad has a unique `device_name` substitution in `keypad.yaml`. This prefixes
all action names and distinguishes entities in HA so multiple keypads never conflict.

| `device_name` | Action prefix | Entity example |
|---|---|---|
| `esphome-keypad` (+ MAC) | `esphome.esphome_keypad_58066c_` | `sensor.keypad_58066c_led_colour_hex` |

**Events** (`keypad_code_entered`, `fingerprint_authenticated`) fire on the same event
type from all keypads. Filter to a specific keypad using `event_data.device_id`:

```yaml
triggers:
  - trigger: event
    event_type: esphome.keypad_code_entered
    event_data:
      device_id: 49e04c941b3fdf876fd0390eb5a6ff1a
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
| `device_id` | string | `"49e04c941b3fdf876fd0390eb5a6ff1a"` |
| `code` | string | `"1234"` |

**Security:** Never log the `code` field in notifications or automation descriptions.
Match the PIN directly in `event_data.code` in the trigger — not in a condition — so
the automation only fires for the correct PIN:

```yaml
triggers:
  - trigger: event
    event_type: esphome.keypad_code_entered
    event_data:
      device_id: YOUR_DEVICE_ID
      code: "1234"
```

---

### `esphome.fingerprint_authenticated`

Fired when a placed finger matches an enrolled template.

**Condition:** Only fires if the HA API is connected (`api.connected`) or `debug_mode_enabled` is true.

| Field | Type | Description |
|---|---|---|
| `device_id` | string | Device identifier |
| `id` | string | Slot number of the matched fingerprint |
| `confidence` | string | Match score 0–255 (higher = better match) |

Reject low-confidence matches with a condition: `{{ trigger.event.data.confidence | int >= 50 }}`.

---

### `esphome.fingerprint_backup_data`

Fired after a successful `fingerprint_backup_slot` action call.

| Field | Type | Description |
|---|---|---|
| `slot` | string | Slot number that was backed up |
| `data` | string | Base64-encoded 512-byte fingerprint template (~684 chars) |

**Important:** Capture this immediately in an automation — see `automations/fingerprint-backup.yaml`.

> **Note:** Use `input_text` helpers with max length 1024 to store full templates.
> Create them in **Settings → Devices & Services → Helpers**.

---

## Actions (HA → Device)

Actions are called from **Settings → Developer Tools → Actions** or in automations.

Action names follow the pattern: `esphome.<device_name_underscored>_<action_name>`

With `device_name: "esphome-keypad"` + MAC suffix `58066c`:
→ prefix is `esphome.esphome_keypad_58066c_`

---

### `set_led_colour`

Change the status LED colour from HA.

| Variable | Type | Description |
|---|---|---|
| `hex` | `string` | 6-digit or `#`-prefixed RGB hex (`"FF8800"`, `"#FF8800"`), or `"off"` to turn off |
| `brightness` | `int` | 0–100. When provided (≥ 1), becomes the new idle brightness level. |

The current colour is published to the `LED Colour Hex` sensor every time this action runs,
and also on reconnect via `on_client_connected`. Read it as alarm state:

```yaml
condition:
  - condition: state
    entity_id: sensor.keypad_58066c_led_colour_hex
    state: "#33FF00"   # true = alarm is armed
```

If called while the keypad is breathing after a PIN entry, the new colour is stored
and applied when the breathing finishes.

---

### `fingerprint_enroll`

Enroll a fingerprint into a specific slot.

| Variable | Type | Description |
|---|---|---|
| `slot` | `int` | Slot number (1 to sensor capacity) |
| `num_scans` | `int` | Number of scans required (typically 2–3) |

After calling: place finger on sensor when the aura LED turns purple. Lift after each blue flash.
Blue breathing = enrolled. See `automations/fingerprint-enroll.yaml`.

> **Auto-wake:** this action power-cycles the sensor before starting enrollment.

---

### `fingerprint_cancel_enroll`

Cancel any in-progress enrollment. No variables. Safe to call at any time.

---

### `fingerprint_sensor_wake`

Power-cycle the R503 sensor. No variables. Sensor ready ~2 seconds after call.
All individual backup/restore/delete/enroll actions call this automatically.

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

On success: fires `esphome.fingerprint_backup_data` event.
On failure: no event fired — check ESPHome logs.

---

### `fingerprint_restore_slot`

Write a previously-backed-up template back into a slot.

| Variable | Type | Description |
|---|---|---|
| `slot` | `int` | Target slot number |
| `data` | `string` | Base64-encoded template from a previous `fingerprint_backup_data` event |

---

## HA Entities (Device Page)

| Entity | Type | Description |
|---|---|---|
| Fingerprint Count | Sensor | Number of enrolled fingerprints |
| Fingerprint Capacity | Sensor | Maximum slots (200) |
| LED Colour Hex | Text sensor | Current LED colour as `#RRGGBB` hex string — use as alarm state indicator |
| Status Light | Light | WS2811 strip — use `set_led_colour` for saved-state tracking |
| LED Brightness | Number | Idle brightness 0–100%. Activity boosts to 100% for 30s then returns here. |

---

## LED Breathing After PIN Entry

After `#` is pressed:
1. The strip flashes **blue × 3** (confirmation of key received)
2. The LED **breathes in the current saved colour** for ~10 seconds (5 cycles)
3. HA automations should **wait 2 seconds** before calling `set_led_colour` so the
   breathing is visible before the new alarm-state colour is applied

```yaml
actions:
  - delay:
      seconds: 2
  - action: esphome.esphome_keypad_58066c_set_led_colour
    data:
      hex: "#33FF00"   # green = armed
      brightness: 50
```

Calling `set_led_colour` during breathing stops the breathing immediately and applies
the new colour.

---

## Automations

Ready-to-use single-automation files are in the `automations/` folder.
See [automations/README.md](../automations/README.md) for the full list and quick-start guide.

Each file contains one automation in the modern HA format — paste directly into
**Settings → Automations → New Automation → ⋮ → Edit in YAML**.

### Alarm toggle by PIN

```yaml
alias: "Alarm: Toggle armed/disarmed via PIN"
triggers:
  - trigger: event
    event_type: esphome.keypad_code_entered
    event_data:
      device_id: YOUR_DEVICE_ID
      code: "1234"
conditions: []
actions:
  - if:
      - condition: state
        entity_id: sensor.keypad_58066c_led_colour_hex
        state: "#33FF00"
    then:
      - delay:
          seconds: 2
      - action: esphome.esphome_keypad_58066c_set_led_colour
        data:
          hex: "#FF0000"
          brightness: 50
      - action: alarm_control_panel.alarm_disarm
        target:
          entity_id: alarm_control_panel.home_alarm
    else:
      - delay:
          seconds: 2
      - action: esphome.esphome_keypad_58066c_set_led_colour
        data:
          hex: "#33FF00"
          brightness: 50
      - action: alarm_control_panel.alarm_arm_away
        target:
          entity_id: alarm_control_panel.home_alarm
mode: single
```

---

## Developer Tools Workflow

### Find your device_id

1. **Settings → Developer Tools → Events** — listen to `esphome.keypad_code_entered`
2. Press `#` on the physical keypad
3. Copy the `device_id` from the event payload

### Test PIN handling

Same as above — the `code` field will show the entered PIN.

### Back up a fingerprint slot

1. **Settings → Developer Tools → Actions** — call `esphome.esphome_keypad_58066c_fingerprint_backup_slot` with `slot: 1`
2. **Settings → Developer Tools → Events** — listen to `esphome.fingerprint_backup_data`
3. The event appears with `slot` and `data` fields — the automation in `fingerprint-backup.yaml` captures this automatically.
