# Debug Mode

Debug mode enables a built-in web server, live diagnostics, and standalone testing without a Home Assistant connection.

---

## Enabling Debug Mode

Two changes are required in `keypad.yaml`:

```yaml
substitutions:
  debug_mode: "1"              # Enable debug gating bypass
  api_reboot_timeout: "0s"     # Disable API watchdog reboot

packages:
  # ...
  debug: !include keypad/debug.yaml   # ← uncomment this line
```

Flash, then access the web UI at `http://<device-ip>/` (or `http://esphome-keypad.local/`).

---

## Effects of `debug_mode: "1"`

| Behaviour | Production (`0`) | Debug (`1`) |
|---|---|---|
| LED on boot | Off | White 50% |
| PIN events fire | Only when HA connected | Always |
| Fingerprint auth events fire | Only when HA connected | Always |
| API reboot watchdog | 60s | 0s (disabled) |

---

## Web Server

| URL | Content |
|---|---|
| `http://<ip>/` | All entities (sensors, buttons, numbers, switches, text inputs) |
| `http://<ip>/logs` | Real-time ESPHome log stream |

`include_internal: true` is set, so internal-only entities (e.g. `key_clear` binary sensor) also appear.

---

## Globals (Debug-Only)

| ID | Type | Default | Purpose |
|---|---|---|---|
| `dbg_fp_last_result_str` | `std::string` | `"idle"` | Status string updated by debug backup/restore buttons. Displayed in the "FP Backup Last Result" text sensor. |
| `dbg_selected_slot` | `int` | `1` | Slot number controlled by the "FP Selected Slot" number. Used by all debug FP management and backup buttons. |
| `debug_ready` | `bool` | `false` | Set to `true` at boot priority `-200`. Guards the LED Digit Simulator `on_value` handler against running during `setup()`. |

---

## Diagnostic Sensors

### Numeric Sensors (updated every 10s unless noted)

| Entity | Update Interval | Description |
|---|---|---|
| Debug: Free Heap | 5s | Free heap memory in bytes |
| Debug: Max Contiguous Heap | 5s | Largest single free heap block in bytes |
| Debug: Loop Time | 5s | ESPHome main loop execution time in µs |
| Debug: WiFi RSSI | 10s | WiFi signal strength in dBm |
| Debug: Uptime | 10s | Seconds since last boot |
| Debug: CPU Temperature | 10s | ESP32-S3 internal temperature sensor |

### Text Sensors

| Entity | Update Interval | Description |
|---|---|---|
| Debug: Device Info | — | ESPHome build info, IDF version, chip details |
| Debug: Reset Reason | — | Why the device last rebooted |
| Debug: IP Address | — | Current IP address |
| Debug: WiFi SSID | — | Connected network name |
| Debug: WiFi BSSID | — | Access point MAC |
| Debug: MAC Address | — | Device WiFi MAC |
| Debug: HA Connected | 2s | `YES` or `NO` — reads `api::global_api_server->is_connected()` |
| Debug: Keypad Active | 2s | `YES — entry in progress` or `NO` — mirrors `keypad_active` |
| Debug: Saved LED State | 2s | Current saved R/G/B/Bri/On values as a string |
| Debug: FP Backup Buffer | 2s | `READY — NNN chars` or `idle — no data in buffer` |
| Debug: FP Backup Data Preview | 2s | First 80 + last 20 chars of backup data (with ellipsis) |
| Debug: FP Backup Last Result | 2s | Last result string from debug backup/restore buttons |
| Debug: FP Sensor Capacity | 5s | `N enrolled / M slots` |

---

## Numbers

### Debug: LED Digit Simulator

Range: 0–4. Simulates pressing keypad digits to test LED progress feedback.

- **Slide to 1–4:** Snapshots current LED state (if not already active), sets `keypad_active = true`, runs `keypad_led_progress(count)` — lights `count` LEDs blue from the right.
- **Slide to 0:** Runs `keypad_restore_state` — restores LED to saved state.

Guarded by `debug_ready` global to prevent execution during component `setup()`.

### Debug: FP Selected Slot

Range: 1–200. Sets `dbg_selected_slot`. All debug FP management and backup buttons operate on this slot.

---

## Buttons — Status LED

Quick LED control for visual testing. All use instant (0ms) transitions.

| Button | LED Result |
|---|---|
| Debug: LED → White 100% | All 4 LEDs, white, 100% |
| Debug: LED → Red | All 4 LEDs, red, 100% |
| Debug: LED → Green | All 4 LEDs, green, 100% |
| Debug: LED → Blue | All 4 LEDs, blue, 100% |
| Debug: LED → Pink | R=100%, G=20%, B=60%, 100% |
| Debug: LED → Off | Strip off |

---

## Buttons — PIN Entry Flow

Test PIN entry LED behaviour without physically pressing keys.

| Button | Action |
|---|---|
| Debug: PIN → Trigger Submit Flash | Runs `keypad_led_flash` (white flash → restore) |
| Debug: PIN → Restore LED State | Runs `keypad_restore_state` directly |
| Debug: PIN → Fire HA Event (code=1234) | Fires `esphome.keypad_code_entered` with `code: "1234"` |

---

## Buttons — Fingerprint Aura LED

Each button mirrors an exact real trigger so you can verify the sensor ring works correctly.

| Button | Aura LED State | Mirrors trigger |
|---|---|---|
| FP Aura → Green Breathe [match] | Green breathing, speed 200, ×2 | `on_finger_scan_matched` |
| FP Aura → Red Flash x4 [unmatched] | Red flashing, speed 30, ×4 | `on_finger_scan_unmatched` |
| FP Aura → Red Flash x2 [invalid scan] | Red flashing, speed 25, ×2 | `on_finger_scan_invalid` |
| FP Aura → Purple Flash [misplaced] | Purple flashing, speed 25, ×2 | `on_finger_scan_misplaced` |
| FP Aura → Blue Flash [enrollment scan] | Blue flashing, speed 25, ×2 | `on_enrollment_scan` (first flash) |
| FP Aura → Purple On [awaiting scan] | Purple always-on | `on_enrollment_scan` (waiting state) |
| FP Aura → Blue Breathe [enrolled OK] | Blue breathing, speed 100, ×2 | `on_enrollment_done` |
| FP Aura → Red Flash x4 [enroll failed] | Red flashing, speed 25, ×4 | `on_enrollment_failed` |
| FP Aura → Off | Always off | — |

---

## Buttons — Fingerprint Management

All operate on the slot set by the "FP Selected Slot" number.

| Button | Action |
|---|---|
| Debug: FP → Enroll Selected Slot (2 scans) | Calls `enroll_fingerprint(dbg_selected_slot, 2)` |
| Debug: FP → Cancel Enroll | Cancels any in-progress enrollment |
| Debug: FP → Delete Selected Slot | Deletes the selected slot |
| Debug: FP → Fire HA Auth Event (selected slot, conf=100) | Fires `esphome.fingerprint_authenticated` with `{id: slot, confidence: 100}` |

---

## Buttons — Fingerprint Backup / Restore

All operate on the slot set by the "FP Selected Slot" number. Results are written to `dbg_fp_last_result_str` and displayed in "Debug: FP Backup Last Result".

| Button | Action |
|---|---|
| Debug: FP → Backup Selected Slot | Runs `fp_backup::backup_slot()` for the selected slot. On success: stores result directly in `fp_backup_data_str`. |
| Debug: FP → Restore Buffer → Selected Slot | Runs `fp_backup::restore_slot()` with the data in `fp_backup_data_str` → selected slot. On success: calls `fingerprint_sensor.update()`. |
| Debug: FP → Backup All Enrolled Slots | Iterates slot 1 → `fp_count_sensor.state`. Backs up each slot via `backup_slot()`. Fires `esphome.fingerprint_backup_data` event per slot. Updates result string with count. |
| Debug: FP → Clear Buffer | Calls `fp_backup_data_str.clear()`, updates result string to `"cleared"`. |

---

## System Button

| Button | Action |
|---|---|
| Debug: System → Reboot | Calls `App.safe_reboot()` |

---

## Disabling Debug Mode

Before production flash:

1. Change `debug_mode: "0"` in `keypad.yaml`
2. Change `api_reboot_timeout: "60s"`
3. Comment out `debug: !include keypad/debug.yaml`
4. Change `log_level: "WARN"` (optional, reduces flash writes and noise)
5. Run `esphome run keypad.yaml`
