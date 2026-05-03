# Architecture

## Package System

The project uses ESPHome's `packages` / `!include` system to split configuration into focused files. `keypad.yaml` is the single entry point — it holds all substitution variables and includes the packages.

```yaml
# keypad.yaml
packages:
  board:        !include keypad/board.yaml
  network:      !include keypad/network.yaml
  fingerprint:  !include keypad/fingerprint.yaml
  keypad:       !include keypad/keypad.yaml
  status_light: !include keypad/status_light.yaml
  debug:        !include keypad/debug.yaml   # optional — debug only
```

Each package is a standalone YAML fragment. ESPHome merges them all before compiling.

---

## File Responsibilities

| File | Responsibility |
|---|---|
| `keypad.yaml` | Entry point. All user-facing substitutions. Package declarations. |
| `keypad/board.yaml` | ESP32-S3 chip config, ESP-IDF framework, logger, on-boot LED logic, `debug_mode_enabled` global. |
| `keypad/network.yaml` | WiFi, HA API (including all actions), OTA. `fp_backup_data_str` global. |
| `keypad/fingerprint.yaml` | UART, R503 sensor, all fingerprint triggers (aura LED feedback), HA sensors. Enables the `fingerprint_backup` external component. |
| `keypad/keypad.yaml` | Matrix keypad hardware, `key_collector` PIN reader, LED feedback scripts, LED state globals. |
| `keypad/status_light.yaml` | WS2811 strip (`light` entity), `led_brightness` number entity (0–100%), `led_brightness_boost` script, brightness globals. |
| `keypad/debug.yaml` | **Debug only.** Web server, ESPHome debug component, diagnostic sensors, test buttons, FP backup/restore buttons. |
| `components/fingerprint_backup/fingerprint_backup.h` | C++ header. Raw Grow UART protocol implementation for `backup_slot()` and `restore_slot()`. Loaded via `external_components`. |

---

## Global Variables

All globals are declared exactly once. Cross-file usage is possible because ESPHome compiles everything into one translation unit.

| ID | Type | Declared In | Purpose |
|---|---|---|---|
| `debug_mode_enabled` | `bool` | `board.yaml` | Mirrors `${debug_mode}` substitution. `true` = debug mode active. |
| `fp_backup_data_str` | `std::string` | `network.yaml` | Base64-encoded template data from last backup. Cleared before each new backup. |
| `saved_r` | `float` | `keypad.yaml` | Saved LED red channel (0.0–1.0) before keypad entry begins. |
| `saved_g` | `float` | `keypad.yaml` | Saved LED green channel. |
| `saved_b` | `float` | `keypad.yaml` | Saved LED blue channel. |
| `saved_bri` | `float` | `keypad.yaml` | Saved LED brightness (0.0–1.0). |
| `saved_on` | `bool` | `keypad.yaml` | Whether the LED was on before keypad entry. |
| `led_idle_brightness` | `float` | `status_light.yaml` | Configured idle brightness (0.0–1.0). Source of truth for the `led_brightness` number entity. |
| `led_boost_active` | `bool` | `status_light.yaml` | True while the 30s brightness boost script is running. |
| `keypad_active` | `bool` | `keypad.yaml` | True while a PIN entry sequence is in progress. |
| `dbg_fp_last_result_str` | `std::string` | `debug.yaml` | Status string updated by debug backup/restore buttons. |
| `dbg_selected_slot` | `int` | `debug.yaml` | Slot number selected by the debug FP slot slider. |
| `debug_ready` | `bool` | `debug.yaml` | Set true at boot priority -200 to gate the LED digit simulator's `on_value`. |

---

## Boot Sequence

ESPHome runs `on_boot` handlers in **descending priority order** (highest first). Lower (more negative) numbers run later.

| Priority | Handler | File | Action |
|---|---|---|---|
| `600` | ESPHome framework | — | All components `setup()` called |
| `-100` | `on_boot` | `board.yaml` | If `debug_mode_enabled`: turn LED white 50% |
| `-200` | `on_boot` | `debug.yaml` | Set `debug_ready = true` (gates LED digit simulator) |

**Why `-200` for `debug_ready`?**

The `TemplateNumber` component (`Debug: LED Digit Simulator`) publishes its initial value through `on_value` during `setup()`. If `keypad_led_progress` ran at that point the LED strip would not yet be fully initialised, causing a crash. The `debug_ready` flag, set at priority `-200` (after all components), prevents the script from executing during `setup()`.

---

## Component Interaction Map

```
keypad.yaml (substitutions)
  │
  ├── board.yaml
  │     └── on_boot → status_light (debug only)
  │
  ├── network.yaml
  │     ├── on_client_connected → status_light (production mode)
  │     └── actions → fingerprint_sensor, uart_fingerprint, status_light, fp_backup_data_str
  │
  ├── fingerprint.yaml
  │     └── fingerprint_grow triggers → aura_led_control, homeassistant.event
  │
  ├── keypad.yaml
  │     ├── key_collector → homeassistant.event, scripts
  │     └── scripts → status_light, globals
  │
  ├── status_light.yaml
  │     ├── status_light (light entity)
  │     ├── led_brightness (number entity)
  │     └── led_brightness_boost (script)
  │
  └── debug.yaml (optional)
        ├── web_server → all entities
        └── buttons/numbers → fingerprint_sensor, uart_fingerprint, status_light, scripts
```

---

## Data Flow: Fingerprint Backup

```
HA action call
  → fingerprint_backup_slot(slot)
  → fp_backup::backup_slot(uart_fingerprint, slot)      [C++, in fingerprint_backup.h]
      → LoadChar command over UART
      → UpChar command over UART
      → read data packets from sensor
      → base64-encode result
  → store in fp_backup_data_str global
  → fire esphome.fingerprint_backup_data HA event {slot, data}
```

```
HA action call
  → fingerprint_restore_slot(slot, data)
  → fp_backup::restore_slot(uart_fingerprint, slot, data)
      → base64-decode data
      → DownChar command over UART
      → send all data packets (no per-packet ACK)
      → Store command → wait for single ACK
  → fingerprint_sensor.update()  [refresh enrolled count]
```
