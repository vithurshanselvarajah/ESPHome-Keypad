# Home Assistant Automations

Ready-to-use automation YAML for all keypad scenarios.
Each file contains a single automation you can paste directly into the HA GUI:
**Settings → Automations → New Automation → ⋮ → Edit in YAML**

## How it works — alarm state via LED colour

The keypad LED doubles as an alarm state indicator:

| LED colour | Meaning |
|---|---|
| Green `#33FF00` | Alarm armed |
| Red `#FF0000` | Alarm disarmed |

When a correct PIN or enrolled fingerprint is scanned, the LED breathes in
the current colour for ~10 seconds. HA then sets the new colour to confirm
the state change. The `LED Colour Hex` sensor (`sensor.<device>_led_colour_hex`)
reflects the current colour so automations can read it as alarm state.

## Quick-start (single keypad)

1. Flash the firmware and add the device in HA.
2. Find your `device_id`: listen to `esphome.keypad_code_entered` in
   Developer Tools → Events, press `#` on the keypad, and copy the
   `device_id` from the event.
3. Note your action prefix (e.g. `esphome_keypad_58066c`) and sensor entity ID.
4. Copy each automation below, replace the `REPLACE_*` placeholders, and save.

## Files

| File | Purpose |
|---|---|
| `pin-access.yaml` | **Core** — correct PIN arms/disarms the alarm |
| `fingerprint-access.yaml` | Enrolled fingerprint arms/disarms the alarm |
| `led-feedback.yaml` | Wrong PIN flashes red then restores state colour |
| `led-brightness.yaml` | Dim LED at night (22:00) |
| `fingerprint-backup.yaml` | Capture backup data from any keypad into helpers |
| `fingerprint-enroll.yaml` | Enroll the next available fingerprint slot |
| `notifications.yaml` | Push notification on PIN or fingerprint event |
| `offline-alert.yaml` | Alert if keypad loses connection for > 1 min |

## Placeholders reference

Every automation contains one or more of these placeholders:

| Placeholder | Example value | Where to find it |
|---|---|---|
| `REPLACE_KEYPAD_DEVICE_ID` | `49e04c941b3fdf876fd0390eb5a6ff1a` | Developer Tools → Events → listen for `esphome.keypad_code_entered` |
| `REPLACE_ACTION_PREFIX` | `esphome_keypad_58066c` | Developer Tools → Actions → search "keypad" |
| `REPLACE_COLOUR_SENSOR` | `sensor.keypad_58066c_led_colour_hex` | Settings → Entities → search "led colour" |
| `REPLACE_DEVICE_led_brightness` | `number.esphome_keypad_58066c_led_brightness` | Settings → Entities → search "led brightness" |
| `REPLACE_DEVICE_connected` | `binary_sensor.esphome_keypad_58066c_connected` | Settings → Entities → search "connected" |
| `alarm_control_panel.home_alarm` | your alarm entity ID | Settings → Entities → search "alarm" |

## LED delay explained

After `#` is pressed the keypad breathes in the saved colour for ~10 seconds.
Automations that set the LED include a 2-second delay before calling
`set_led_colour` so the breathing is visible first.
