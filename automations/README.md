# Home Assistant Automations

Ready-to-use automation YAML for all keypad scenarios.

## Multi-keypad design

Each keypad has a unique `device_name` in `keypad.yaml` / `keypad-local.yaml` (e.g. `esphome-front-door`, `esphome-garage`).
All action and event names are automatically prefixed with that name, so they never collide:

| Device name | Event prefix | Action prefix |
|---|---|---|
| `esphome-front-door` | `esphome.keypad_code_entered` | `esphome.esphome_front_door_set_led_colour` |
| `esphome-garage` | `esphome.keypad_code_entered` | `esphome.esphome_garage_set_led_colour` |

Events use `event_data.device_name` (added by the automations here) to route to the correct handler, or each automation uses `trigger.platform: device` scoped to the specific device.

## Files

| File | Covers |
|---|---|
| `pin-access.yaml` | PIN authentication — grant/deny access per keypad |
| `fingerprint-access.yaml` | Fingerprint authentication — grant/deny access per keypad |
| `led-feedback.yaml` | Colour-coded LED feedback after PIN/fingerprint result |
| `led-brightness.yaml` | Idle brightness control per keypad from HA |
| `fingerprint-backup.yaml` | Backup a slot and restore it to all keypads |
| `fingerprint-enroll.yaml` | Enroll a new fingerprint via HA |
| `notifications.yaml` | Mobile push alerts for access events |
| `offline-alert.yaml` | Alert when a keypad goes offline |
