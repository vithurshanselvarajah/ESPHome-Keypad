# Hardware & Wiring

The PCB and enclosure design for this project is from this project - **[sb-ocr/esphome-keypad](https://github.com/sb-ocr/esphome-keypad)**.

## Components

| Component | Part / Spec |
|---|---|
| Microcontroller | ESP32-S3-DevKitC-1 (240 MHz, dual-core, 512 KB SRAM, 8 MB flash) |
| Fingerprint sensor | R503 — Grow capacitive, 200-slot, aura LED ring, UART interface |
| LED strip | WS2811 — 4 LEDs, GRB colour order, 5V, data pin with 300Ω series resistor recommended |
| Keypad | Generic 3×4 matrix keypad, **no diodes** |
| Framework | ESP-IDF (required for `fingerprint_grow` component) |

---

## GPIO Assignments

| GPIO | Direction | Function |
|---|---|---|
| 4 | Input | Keypad Row 0 (top row) |
| 5 | Input | Keypad Row 1 |
| 6 | Input | Keypad Row 2 |
| 7 | Input | Keypad Row 3 (bottom row) |
| 10 | Output | Keypad Column 0 (left) |
| 11 | Output | Keypad Column 1 |
| 12 | Output | Keypad Column 2 (right) |
| 17 | Output (UART TX) | R503 UART RX wire (green) |
| 18 | Input (UART RX) | R503 UART TX wire (white) |
| 21 | Output | WS2811 data line |
| 47 | Output (inverted) | R503 power pin (HIGH = power off; active-low) |
| 48 | Input (pull-down) | R503 sensing/touch pin (finger present = HIGH) |

---

## Fingerprint Sensor (R503)

The R503 is a capacitive fingerprint sensor with a built-in UART interface and an aura LED ring.

### Wiring

| R503 Pin | Wire Colour | ESP32-S3 Connection |
|---|---|---|
| VCC (3.3V) | Red | 3.3V |
| GND | Black | GND |
| TXD | White | GPIO18 (ESP RX) |
| RXD | Green | GPIO17 (ESP TX) |
| WAKEUP / Sensing | Yellow | GPIO48 (pull-down) |
| 3.3V Touch Sensing | Blue | GPIO47 (inverted — active-low power control) |

> **Note:** The "Blue" power line on the R503 is used to power-cycle the sensor on ESP boot via `sensor_power_pin` (GPIO47, inverted). This ensures the sensor wakes cleanly without sending a spurious 0x00 byte that could confuse the `fingerprint_grow` component.

### Key R503 Specifications

- **UART baud rate:** 57600
- **Slot capacity:** 200 fingerprints
- **Communication address:** 0xFFFFFFFF (default)
- **Password:** 32-bit, default 0x00000000 (disabled)
- **Sleep timeout:** 300 seconds (configured via `idle_period_to_sleep`)

---

## WS2811 LED Strip

| Parameter | Value |
|---|---|
| Number of LEDs | 4 |
| Data GPIO | 21 |
| Colour order | GRB |
| Driver | `esp32_rmt_led_strip` |
| Restore mode | `ALWAYS_OFF` (off on boot) |

The strip is addressable; individual LEDs are controlled during PIN entry to show progress (one LED lit per digit entered, from the right). Status colours use all 4 LEDs uniformly.

**Wiring tip:** Place a 300–470Ω resistor in series on the data line, close to the LED strip. Decouple power with a 100–1000µF capacitor across VCC/GND at the strip.

---

## Matrix Keypad

### Physical Layout

```
[ 1 ] [ 2 ] [ 3 ]
[ 4 ] [ 5 ] [ 6 ]
[ 7 ] [ 8 ] [ 9 ]
[ * ] [ 0 ] [ # ]
```

### Key Mapping

The `keys` string is read row by row, left to right:

```yaml
keys: "123456789*0#"
```

| Key | Function |
|---|---|
| `0`–`9` | PIN digit input |
| `#` | Submit / end key |
| `*` | Clear / cancel (resets PIN buffer and restores LEDs) |

### Wiring

```
          COL0  COL1  COL2
           |     |     |
           10    11    12

ROW0 — 4 —[1]  [2]  [3]
ROW1 — 5 —[4]  [5]  [6]
ROW2 — 6 —[7]  [8]  [9]
ROW3 — 7 —[*]  [0]  [#]
```

> `has_diodes: false` — no diode protection fitted. Ghost keys are possible if multiple keys pressed simultaneously; this is acceptable for a PIN-entry use case.

---

## Power

The ESP32-S3-DevKitC-1 is powered via USB-C or the 5V pin. The R503 sensor runs on 3.3V (drawn from the DevKit 3.3V rail). The WS2811 strip requires a separate 5V supply if more than a few LEDs are used at full brightness — at 50% brightness with 4 LEDs the USB 5V rail is typically sufficient.
