# Fingerprint Sensor

## Hardware Config

| Parameter | Value |
|---|---|
| Component | `fingerprint_grow` |
| UART ID | `uart_fingerprint` |
| UART TX (ESP → sensor) | GPIO17 |
| UART RX (sensor → ESP) | GPIO18 |
| Baud rate | 57600 |
| Sensing pin | GPIO48, pull-down (finger touch detection) |
| Power pin | GPIO47, inverted (HIGH = off; active-low power control) |
| Sleep timeout | 300s (`idle_period_to_sleep`) |
| Password | `${fp_password}` (default `0x00000000` = disabled) |
| ESPHome ID | `fingerprint_sensor` |
| UART ID | `uart_fingerprint` |

### Why 300s sleep timeout?

The `idle_period_to_sleep` is set to 300 seconds so there is a generous window for **backup or restore operations** after a finger scan wakes it. Raw UART backup/restore requires the sensor to be powered on throughout the transfer.

All HA actions that require the sensor to be awake (`fingerprint_backup_slot`, `fingerprint_restore_slot`, `fingerprint_delete`, `fingerprint_delete_all`, `fingerprint_enroll`) **automatically power-cycle the sensor first** via the `fp_sensor_wake_impl` script. You do not need to touch the sensor before calling these actions from HA.

If you want to explicitly wake the sensor from HA (e.g., before a scripted sequence of operations), call the `fingerprint_sensor_wake` action. The sensor is ready ~2s after the call.

The sensor is **power-cycled via GPIO47 on every ESP boot** (`sensor_power_pin: inverted`). This guarantees the sensor starts fresh and does not send a spurious 0x00 wake byte that would confuse the `fingerprint_grow` component's ACK parser.

---

## Triggers and Aura LED Feedback

The R503 has a built-in aura LED ring. Each fingerprint event configures it via `fingerprint_grow.aura_led_control`.

### Idle state

When the sensor is awake and waiting for a finger, the aura ring shows **slow blue breathing** (speed 40, infinite). This is set:
- At boot (priority -100, after all components are initialised)
- After every wake cycle (`fingerprint_sensor_wake` or auto-wake before any action)
- 3 seconds after any scan result animation completes (`fp_aura_restore` script, mode restart)

During multi-scan enrollment, the idle state is replaced by solid purple ("waiting for next scan") and is not restored until enrollment finishes.

### `on_finger_scan_matched`

Fired when a placed finger matches an enrolled template.

**LED:** Green breathing (speed 200, 1 cycle) → idle blue breathing (after 3s)

**Action:** If `api.connected || debug_mode_enabled`, fires the `esphome.fingerprint_authenticated` HA event with `{ id, confidence }`.

The HA event is gated so it does not fire in production when HA is unreachable (preventing phantom events from being queued or dropped).

### `on_finger_scan_unmatched`

Fired when a placed finger does not match any enrolled template.

**LED:** Red flashing × 4 (speed 30) → idle blue breathing (after 3s)

No HA event fired.

### `on_finger_scan_misplaced`

Fired when the finger is placed incorrectly (partial coverage, wrong angle, etc.).

**LED:** Purple flashing × 2 (speed 25) → idle blue breathing (after 3s)

No HA event fired.

### `on_finger_scan_invalid`

Fired when the scan is too noisy or the image cannot be processed.

**LED:** Red flashing × 2 (speed 25) → idle blue breathing (after 3s)

No HA event fired.

### `on_enrollment_scan`

Fired after each individual scan during an enrollment sequence (not the final one).

**LED sequence:**
1. Blue flashing × 2 (speed 25) — scan accepted
2. 1s delay
3. Purple solid — waiting for next scan (stays until enrollment_done/failed)

### `on_enrollment_done`

Fired when all required scans for enrollment are complete and the template is saved.

**LED:** Blue breathing × 2 (speed 100) → idle blue breathing (after 3s)

### `on_enrollment_failed`

Fired when enrollment fails (scans too inconsistent, sensor error, etc.).

**LED:** Red flashing × 4 (speed 25) → idle blue breathing (after 3s)

---

## Aura LED Control Reference

`fingerprint_grow.aura_led_control` parameters:

| Parameter | Values |
|---|---|
| `state` | `BREATHING`, `FLASHING`, `ALWAYS_ON`, `ALWAYS_OFF` |
| `speed` | 0–255 (0 = instant; higher = slower) |
| `color` | `RED`, `GREEN`, `BLUE`, `PURPLE`, `CYAN`, `YELLOW`, `WHITE` |
| `count` | 0 = infinite; 1–255 = repeat count |

---

## Sensors (HA Entities)

Two sensors are exposed as HA numeric entities under the device.

| Entity | ID | Description |
|---|---|---|
| Fingerprint Count | `fp_count_sensor` | Number of currently enrolled fingerprints |
| Fingerprint Capacity | `fp_capacity_sensor` | Maximum slots (200 for R503) |

`fp_count_sensor` and `fp_capacity_sensor` are used internally by the backup/restore logic and the debug panel.

---

## API Actions (from HA)

All fingerprint management is done exclusively via HA API actions.

Key actions related to fingerprint management:

| Action | Purpose |
|---|---|
| `fingerprint_enroll` | Enroll into a specific slot with a specific scan count (auto-wakes sensor) |
| `fingerprint_cancel_enroll` | Cancel enrollment |
| `fingerprint_delete` | Delete a specific slot (auto-wakes sensor) |
| `fingerprint_delete_all` | Wipe all slots (auto-wakes sensor) |
| `fingerprint_backup_slot` | Back up a slot's template as base64 via HA event (auto-wakes sensor) |
| `fingerprint_restore_slot` | Restore a base64 template into a slot (auto-wakes sensor) |
| `fingerprint_sensor_wake` | Explicitly power-cycle the sensor; aura LED returns to idle blue. Sensor ready ~2s after call. |

---

## Enrollment Flow (Detailed)

When enrollment is triggered (button or API action):

```
1. enroll_fingerprint(slot, num_scans) called
2. Sensor enters enrollment mode
3. For each scan (1 to num_scans):
   a. on_enrollment_scan fires → LED feedback
   b. User places finger, sensor captures
   c. User lifts finger
4. When all scans captured:
   a. Sensor generates combined template
   b. Stores to flash at the given slot
   c. on_enrollment_done fires → LED breathing blue
```

If any scan fails or times out: `on_enrollment_failed` fires.

To cancel at any point: press "Cancel Enrollment" button or call the `fingerprint_cancel_enroll` action.
