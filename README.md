# ESPHome Access Controller

A production-quality access controller built on an **ESP32-S3** with a **matrix keypad**, **R503 capacitive fingerprint sensor**, and a **WS2811 LED strip** — fully integrated with Home Assistant.

Features:
- 4-digit PIN entry via 3×4 matrix keypad, firing a HA event per submission
- R503 fingerprint authentication with aura LED ring feedback
- Raw Grow UART fingerprint template **backup and restore** (base64, slot-addressable)
- WS2811 RGB status strip (4 LEDs) with colour control via HA action
- Fully encrypted HA API + OTA password protection
- Optional debug mode: web server, live diagnostics, standalone testing (no HA required)

---

## Hardware

| Component | Part |
|---|---|
| Microcontroller | ESP32-S3-DevKitC-1 |
| Fingerprint sensor | R503 (Grow/Waveshare capacitive, aura LED) |
| LED strip | WS2811 (4 LEDs, GRB order) |
| Keypad | 3×4 matrix, no diodes |

The PCB and enclosure design for this project is at **[sb-ocr/esphome-keypad](https://github.com/sb-ocr/esphome-keypad)**.

See [docs/hardware.md](docs/hardware.md) for full GPIO wiring.

---

## Quick Start

### 1. Prerequisites

- [ESPHome](https://esphome.io) ≥ 2026.4
- Home Assistant with ESPHome integration
- Python environment with `esphome` installed

### 2. Clone & configure secrets

```bash
git clone <your-repo-url>
cd esphome
cp secrets.yaml.example secrets.yaml   # fill in your values
```

`secrets.yaml` fields required:

| Key | Description |
|---|---|
| `wifi_ssid` | Your WiFi network name |
| `wifi_password` | WiFi password |
| `api_encryption_key` | 32-byte base64 key — generate with `openssl rand -base64 32` |
| `ota_password` | OTA update password |

> **Never commit `secrets.yaml` to version control.** It contains credentials. It is in `.gitignore`.

### 3. Adjust substitutions

Two entry-point files exist:

| File | Use for |
|---|---|
| `keypad.yaml` | Fetches all packages directly from GitHub. Use this when you don't have a local clone or for reference. |
| `keypad-local.yaml` | References local files. Use this for development and flashing from your workstation. |

Open `keypad-local.yaml` and review the `substitutions` block. At minimum:

- Set `debug_mode: "0"` and `api_reboot_timeout: "60s"` for production.
- Set `fp_password` if you want to lock the fingerprint sensor (read the warning in the file first).

See [docs/configuration.md](docs/configuration.md) for a full reference.

### 4. Flash

```bash
# First flash (USB, auto-detects port)
esphome run keypad-local.yaml

# Subsequent OTA flashes
esphome run keypad-local.yaml
```

### 5. Add to Home Assistant

After the device is on the network, HA will auto-discover it. Accept the device with your `api_encryption_key`.

---

## Project Structure

```
keypad.yaml              ← Remote entry point (fetches packages from GitHub)
keypad-local.yaml        ← Local dev entry point (references local files)
secrets.yaml             ← Credentials (not committed)

keypad/
  board.yaml             ← ESP32-S3 core, boot logic, debug_mode_enabled global
  network.yaml           ← WiFi, API actions, OTA
  fingerprint.yaml       ← R503 sensor config, all triggers
  keypad.yaml            ← Matrix keypad, PIN collector, LED feedback scripts
  status_light.yaml      ← WS2811 strip (light entity only)
  debug.yaml             ← Debug-only: web server, diagnostics, test buttons

components/
  fingerprint_backup/
    __init__.py          ← ESPHome external component glue
    fingerprint_backup.h ← Raw Grow UART backup/restore (C++ header)
```

---

## Documentation

| Page | Contents |
|---|---|
| [Hardware & Wiring](docs/hardware.md) | GPIO assignments, wiring diagrams |
| [Configuration Reference](docs/configuration.md) | All substitutions, secrets, production checklist |
| [Architecture](docs/architecture.md) | Package system, globals ownership, boot sequence |
| [LED System](docs/led-system.md) | Status meanings, colour control, keypad feedback |
| [Keypad & PIN](docs/keypad-pin.md) | Key layout, PIN flow, timeout, LED feedback |
| [Fingerprint Sensor](docs/fingerprint.md) | R503 config, triggers, aura LED, management |
| [Backup Protocol](docs/fingerprint-backup-protocol.md) | Raw Grow UART backup/restore deep-dive |
| [Home Assistant Integration](docs/homeassistant.md) | Events, actions, example automations |
| [Debug Mode](docs/debug-mode.md) | Web server, all debug controls, testing without HA |

---

## Security Notes

- The HA API is encrypted with a 32-byte key (`api_encryption_key`).
- OTA is password-protected (`ota_password`).
- Fingerprint templates never leave the R503's flash in plain form; backup data is base64-encoded binary — not human-readable biometrics.
- The keypad fires PIN codes as HA events. **Treat these events as sensitive** — use HA automations with secrets rather than exposing them in logs.
