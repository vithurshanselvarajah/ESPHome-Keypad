# ESPHome Access Controller

A production-quality access controller built on an **ESP32-S3** with a **matrix keypad**, **R503 capacitive fingerprint sensor**, and a **WS2811 LED strip** — fully integrated with Home Assistant.

- 4-digit PIN entry via 3×4 matrix keypad, firing a HA event per submission
- R503 fingerprint authentication with aura LED ring feedback
- Raw Grow UART fingerprint template **backup and restore** (base64, slot-addressable)
- WS2811 RGB status strip (4 LEDs) with colour control via HA action
- Fully encrypted HA API + OTA password protection
- Optional debug mode: web server, live diagnostics, standalone testing (no HA required)

The PCB and enclosure for this project: **[sb-ocr/esphome-keypad](https://github.com/sb-ocr/esphome-keypad)**

---

## Documentation

| Page | Contents |
|---|---|
| [Hardware & Wiring](hardware) | Components, GPIO assignments, wiring diagrams |
| [Configuration Reference](configuration) | All substitutions, secrets, production checklist |
| [Architecture](architecture) | Package system, file responsibilities, globals, boot sequence |
| [LED System](led-system) | Status meanings, colour control, keypad LED feedback |
| [Keypad & PIN](keypad-pin) | Key layout, PIN entry flow, timeout, LED feedback |
| [Fingerprint Sensor](fingerprint) | R503 config, triggers, aura LED, management |
| [Fingerprint Backup Protocol](fingerprint-backup-protocol) | Raw Grow UART backup/restore deep-dive |
| [Home Assistant Integration](homeassistant) | Events, actions, example automations |
| [Debug Mode](debug-mode) | Web server, all debug controls, testing without HA |
| [Contributing](contributing) | Local setup, tests, CI/CD, branch conventions |

---

## Quick Links

- **First time setup** → [Configuration Reference](configuration)
- **Wiring the hardware** → [Hardware & Wiring](hardware)
- **Adding fingerprints** → [Home Assistant Integration](homeassistant#actions-ha--device)
- **Backing up fingerprints** → [Fingerprint Backup Protocol](fingerprint-backup-protocol)
- **Something not working** → [Debug Mode](debug-mode)
- **Making changes** → [Contributing](contributing)
