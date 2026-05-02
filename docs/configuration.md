# Configuration Reference

All user-facing configuration lives in the `substitutions` block at the top of `keypad.yaml`. Nothing else needs to be edited for normal deployment.

---

## keypad.yaml — Substitutions

### Identity

| Key | Default | Description |
|---|---|---|
| `device_name` | `esphome-keypad` | ESPHome device name. Used as the mDNS hostname (`esphome-keypad.local`). Must be lowercase letters, numbers, hyphens only. |
| `friendly_name` | `Keypad` | Display name shown in Home Assistant. |

### Network

| Key | Value source | Description |
|---|---|---|
| `wifi_ssid` | `!secret wifi_ssid` | WiFi network name. Stored in `secrets.yaml`. |
| `wifi_password` | `!secret wifi_password` | WiFi password. |
| `enable_ipv6` | `"false"` | Set to `"true"` to enable IPv6 on the network stack. Requires router and OS support. Disabled by default. |

### Security

| Key | Value source | Description |
|---|---|---|
| `api_encryption_key` | `!secret api_encryption_key` | 32-byte base64 key for HA API noise encryption. Generate with `openssl rand -base64 32`. Must match the value entered in HA when adding the device. |
| `ota_password` | `!secret ota_password` | Password required for OTA updates. |

### Fingerprint Sensor

| Key | Default | Description |
|---|---|---|
| `fp_password` | `0x00000000` | 32-bit hex password for the R503 sensor. `0x00000000` means no password (default). **Warning:** if you change this, write down the new value. If lost, the sensor is permanently locked. To change: set `new_password` in `fingerprint.yaml` first, then update this substitution to match. |

### Mode

| Key | Default | Options | Description |
|---|---|---|---|
| `debug_mode` | `"0"` | `"0"` / `"1"` | **Production (`0`):** LED off on boot; HA required for PIN/fingerprint events. **Debug (`1`):** LED white 50% on boot; events fire even without HA connected; enables standalone testing. |
| `api_reboot_timeout` | `"60s"` | `"0s"` to any duration | How long to wait without an HA API connection before rebooting. `"0s"` disables the watchdog (useful in debug). For production, `"60s"` ensures the device recovers from network dropouts. |

### Logging

| Key | Default | Options | Description |
|---|---|---|---|
| `log_level` | `"DEBUG"` | `VERBOSE`, `DEBUG`, `INFO`, `WARN`, `ERROR`, `NONE` | ESPHome log verbosity. Use `WARN` for production (reduces log noise and slightly improves performance). Use `DEBUG` during development. |

---

## secrets.yaml

Required fields:

```yaml
wifi_ssid: "YourNetworkName"
wifi_password: "YourWiFiPassword"

# Generate with: openssl rand -base64 32
api_encryption_key: "base64encodedkey=="

ota_password: "anotherSecurePassword"
```

> **Do not commit this file.** Add `secrets.yaml` to `.gitignore`.

To generate secure random values:
```bash
openssl rand -base64 32   # for api_encryption_key
openssl rand -hex 16      # for ota_password (or use base64)
```

---

## Debug Package

When `debug_mode: "1"`, also uncomment the debug package in `keypad.yaml`:

```yaml
packages:
  # ...
  debug: !include keypad/debug.yaml   # ← uncomment
```

Comment it back out before flashing production firmware. The debug package adds ~50 KB of flash usage and exposes internal state via the web server.

---

## Production Deployment Checklist

Before flashing to a permanently-installed device:

- [ ] `debug_mode: "0"`
- [ ] `api_reboot_timeout: "60s"`
- [ ] `log_level: "WARN"`
- [ ] `debug: !include keypad/debug.yaml` is **commented out**
- [ ] `api_encryption_key` is a unique, randomly generated value
- [ ] `ota_password` is a strong unique password
- [ ] `secrets.yaml` is not committed to version control

---

## Fingerprint Sensor Password (Advanced)

The R503 accepts a 32-bit hardware password. It defaults to `0x00000000` (disabled).

To set a password:

1. In `keypad/fingerprint.yaml`, find the `fingerprint_grow` section and add:
   ```yaml
   new_password: 0xDEADBEEF   # your new password
   ```
2. Flash the device. The sensor will update its password on boot.
3. Remove `new_password` from the config.
4. Update `fp_password: "0xDEADBEEF"` in `keypad.yaml`.
5. Flash again.

> **If you lose this password, the sensor cannot be recovered.** It must be replaced.
