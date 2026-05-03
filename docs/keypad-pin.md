# Keypad & PIN Entry

## Hardware

| Parameter | Value |
|---|---|
| Type | 3×4 matrix keypad |
| Rows | GPIO 4, 5, 6, 7 |
| Columns | GPIO 10, 11, 12 |
| Key string | `123456789*0#` |
| Diodes | None (`has_diodes: false`) |

### Physical Layout

```
[ 1 ] [ 2 ] [ 3 ]
[ 4 ] [ 5 ] [ 6 ]
[ 7 ] [ 8 ] [ 9 ]
[ * ] [ 0 ] [ # ]
```

---

## key_collector

The `key_collector` component accumulates keystrokes into a PIN string and fires events.

| Parameter | Value | Meaning |
|---|---|---|
| `min_length` | 4 | Minimum digits before `#` ends entry |
| `max_length` | 4 | Maximum digits (auto-caps at 4) |
| `end_keys` | `#` | Key that submits the PIN |
| `end_key_required` | true | Entry only fires `on_result` if `#` is pressed |
| `clear_keys` | `*` | Clears the current PIN buffer |
| `allowed_keys` | `0123456789` | Only digits accepted into the buffer |
| `timeout` | 5s | Time with no keypress before the session resets |

---

## Gating

PIN entry and the HA event only fire when:

```
api.connected  OR  debug_mode_enabled == true
```

This prevents stray events from being fired when HA is not connected and the device is in production mode. In debug mode the keypad works standalone.

The `on_progress` block checks this gate on every keypress; if the condition is false, keystrokes are silently consumed without LED feedback.

---

## Entry Flow

### Step 1 — First digit pressed

1. Gate check (`api.connected || debug_mode_enabled`). If false: do nothing.
2. If `keypad_active == false` (first digit of a new entry):
   - Snapshot `status_light.current_values` into `saved_r/g/b/bri/saved_on`.
   - Set `keypad_active = true`.
3. Execute `keypad_led_progress(count: 1)` — rightmost LED turns blue.

### Step 2 — Second, third digit

1. Gate check.
2. Execute `keypad_led_progress(count: 2 or 3)` — more LEDs turn blue from the right.

### Step 3 — Fourth digit (buffer full)

1. Gate check.
2. Execute `keypad_led_progress(count: 4)` — all 4 LEDs blue.

### Step 4 — `#` pressed (submit)

`on_result` fires:

1. Gate check.
2. Fire `esphome.keypad_code_entered` HA event with `{ code: "XXXX" }`.
3. Execute `keypad_led_result` — blue flash × 3 (150ms on / 150ms off), then wait 2s for HA to call `set_led_colour`. If HA responds within the window the new colour is applied on restore; otherwise the pre-entry colour is restored.

### Clear — `*` pressed

- The `key_collector` clears its internal buffer.
- A separate `binary_sensor` for the `*` key watches for press while `keypad_active`.
- If `keypad_active == true`: executes `keypad_restore_state` immediately.

### Timeout — 5s without a keypress

`on_timeout` fires:

1. If `keypad_active == true`: executes `keypad_restore_state`.

---

## LED Feedback Summary

| Event | LED Response |
|---|---|
| 1st digit | Rightmost LED → blue (20, 20, 255) |
| 2nd digit | 2 rightmost LEDs → blue |
| 3rd digit | 3 rightmost LEDs → blue |
| 4th digit | All 4 LEDs → blue |
| Submit (`#`) | Blue flash × 3 (150ms on/off), 2s HA response window, then restore saved state (or HA colour if received) |
| Clear (`*`) | Immediately restore saved state |
| Timeout | Restore saved state |

---

## HA Event: `esphome.keypad_code_entered`

Fired when a 4-digit PIN is submitted with `#`.

| Field | Type | Example |
|---|---|---|
| `code` | string | `"1234"` |

**Security note:** The `code` field contains the raw PIN as a string. Use this in HA automations to compare against a stored secret — do not log it or expose it in UI dashboards.

Example automation:

```yaml
automation:
  - alias: "Keypad grant access"
    trigger:
      - platform: event
        event_type: esphome.keypad_code_entered
        event_data:
          code: !secret door_pin
    action:
      - service: lock.unlock
        target:
          entity_id: lock.front_door
```

---

## Binary Sensor: Clear Key

```yaml
binary_sensor:
  - platform: matrix_keypad
    keypad_id: mykeypad
    id: key_clear
    key: "*"
    internal: true
    on_press:
      - if:
          condition:
            lambda: "return id(keypad_active);"
          then:
            - script.execute: keypad_restore_state
```

This is `internal: true` — it does not appear in HA. It exists purely to trigger LED restore immediately on `*` press, before the `key_collector`'s `clear_keys` processing clears the buffer.
