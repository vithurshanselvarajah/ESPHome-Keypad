# LED System

## Hardware

| Parameter | Value |
|---|---|
| Component | `esp32_rmt_led_strip` |
| Chipset | WS2811 |
| GPIO | 21 |
| LED count | 4 |
| Colour order | GRB |
| ESPHome ID | `status_light` |
| Restore mode | `ALWAYS_OFF` |

The strip starts **off** on every boot. The `ALWAYS_OFF` restore mode is intentional — the LED state machine is driven entirely by runtime logic.

---

## Status Meanings

| LED State | Meaning |
|---|---|
| Off | Device just booted, or no Home Assistant client connected |
| White 50% | Home Assistant connected and active |
| White 50% (on boot) | Debug mode enabled (`debug_mode: "1"`) |
| Blue progress LEDs | PIN entry in progress — one LED per digit, from the right |
| Blue flash × 3 | PIN submitted — blue flash 3 times (150ms on/off), 2s HA response window, then restore or HA colour |
| Custom colour | Set via `set_led_colour` API action |

---

## HA Entities

### Status Light (`status_light`)

The underlying `light` entity. Visible in HA and the device page. Use the `set_led_colour` API action to change colour — it updates the saved state globals so keypad entry restores correctly. Directly controlling the `light` entity from HA bypasses saved-state tracking.

### LED Brightness (`led_brightness`)

A `number` entity (0–100%) that controls the idle brightness level. Changes persist across reboots (`restore_value: true`). When the user sets a new value it is stored in `led_idle_brightness` and applied to the strip immediately (unless a boost or keypad animation is active). The entity is visible on the HA device page and can be controlled from automations — see `automations/led-brightness.yaml`.

---

## API Action: `set_led_colour`

Callable from HA Developer Tools → Actions, or in automations.

Action name: `esphome.esphome_keypad_set_led_colour`

| Variable | Type | Description |
|---|---|---|
| `hex` | `string` | 6-digit hex colour (`"FF8800"`), with or without `#`. Pass `"off"` to turn off. |
| `brightness` | `int` | Brightness 0–100. Values ≤ 0 or > 100 are clamped to 100. |

Behaviour:
- Parses and validates the hex string
- Updates `saved_r/g/b/bri/on` globals
- Calls `status_light.turn_on()` with 500ms transition
- Logs a warning and does nothing if the hex is invalid

---

## LED State Persistence (Globals)

During PIN entry the strip is temporarily overridden to show digit progress. These globals capture the pre-entry state and restore it afterwards.

| Global ID | Type | Default | Description |
|---|---|---|---|
| `saved_r` | `float` | `1.0` | Red channel before keypad entry (0.0–1.0) |
| `saved_g` | `float` | `1.0` | Green channel |
| `saved_b` | `float` | `1.0` | Blue channel |
| `saved_bri` | `float` | `1.0` | Brightness before keypad entry |
| `saved_on` | `bool` | `true` | Whether the light was on before keypad entry |
| `led_idle_brightness` | `float` | `1.0` | Current idle brightness (0.0–1.0); source of truth for the `led_brightness` number entity |
| `led_boost_active` | `bool` | `false` | True while the 30s brightness boost is running |

Saved state (`saved_r/g/b/bri/on`) is written in two places:
1. `keypad.yaml` — `on_progress` first digit: snapshot from `status_light.current_values`
2. `network.yaml` — `set_led_colour` action: set to the new colour

---

## Scripts

All scripts are defined in `keypad/keypad.yaml`.

### `keypad_restore_state`

Restores the LED strip to whatever state was saved before keypad entry began.

```
1. Set keypad_active = false
2. If saved_on == true:
     → light.turn_on with saved_r/g/b/bri, transition 0ms
   Else:
     → light.turn_off, transition 0ms
```

Triggered by:
- Key `*` pressed while `keypad_active` is true
- PIN entry timeout (5s)
- After `keypad_led_flash` completes

### `keypad_led_progress(count: int)`

Shows PIN entry progress on the strip. Called on every digit keypress.

```
Parameters: count (1–4, number of digits entered)

1. Get the raw AddressableLight output from status_light
2. Compute rest colour from saved_r/g/b/bri (or black if saved_on=false)
3. For each LED i (0 to 3):
     If i >= (4 - count):  → blue (20, 20, 255)  ← "digit entered"
     Else:                  → rest colour
4. schedule_show()
```

This means with `count=1` only the rightmost LED is blue; with `count=4` all four are blue.

### `keypad_led_result`

Provides visual confirmation after PIN submission and opens a 2s window for HA colour response.

```
1. Blue flash × 3:
     turn on blue (0, 0, 255) 100%, transition 0ms
     delay 150ms
     turn off, transition 0ms
     delay 150ms
     (repeat × 3)
2. Delay 2s  ← HA can call set_led_colour within this window
3. Execute keypad_restore_state
     (applies HA colour if set_led_colour was called, otherwise pre-entry colour)
```

Called by `on_result` (PIN submitted via `#`).

### `keypad_led_flash`

Legacy flash used by the **debug.yaml** test button. Not called during normal keypad operation.

```
1. Turn all 4 LEDs white 100%, transition 0ms
2. Delay 300ms
3. Execute keypad_restore_state
```

### `led_brightness_boost` (in `status_light.yaml`)

Boosts brightness to 100% for 30 seconds after any physical interaction (keypress or fingerprint scan), then returns to the configured idle level.

```
Mode: restart  (resets the 30s timer on each new interaction)
1. Set led_boost_active = true
2. Set led_brightness number entity = 100  (triggers light update)
3. Delay 30s
4. Set led_boost_active = false
5. Set led_brightness number entity = led_idle_brightness * 100
```

---

## LED Interaction Priority

When multiple things want to control the LED, this is the effective priority (highest wins):

1. **Keypad entry in progress** — `keypad_led_progress` (direct addressable write)
2. **Keypad result flash** — `keypad_led_result` (blue × 3, then 2s wait, then restore)
3. **HA colour control** — `set_led_colour` action (updates saved state; skips `turn_on` during keypad activity so blue flash is not interrupted)
4. **Brightness boost** — `led_brightness_boost` resets to 100% for 30s after any interaction; does not change colour
5. **HA connection** — `on_client_connected` sets white at `led_idle_brightness` (not hardcoded 50%)
6. **Boot** — off by default; white 50% only in debug mode
