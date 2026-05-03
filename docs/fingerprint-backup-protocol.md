# Fingerprint Backup Protocol

## Why Raw UART?

ESPHome's `fingerprint_grow` component does not expose the raw template data stored in the sensor's flash. The only way to read or write templates programmatically is to speak the Grow UART protocol directly, bypassing the component.

`components/fingerprint_backup/fingerprint_backup.h` implements this in a standalone C++ header in the `fp_backup` namespace. It is loaded through the `fingerprint_backup` external component in `fingerprint.yaml` and called from lambda blocks in `network.yaml` (API actions) and `debug.yaml` (debug buttons).

> ESPHome is single-threaded / cooperative — lambdas run to completion. There is no UART contention with the `fingerprint_grow` component during backup/restore.

---

## Grow Protocol Overview

The R503 uses the **Grow (Zhian) fingerprint UART protocol** at 57600 baud, 8N1.

### Packet Structure

All communication is packet-based:

```
0xEF 0x01           — Fixed header
0xFF 0xFF 0xFF 0xFF — Device address (default broadcast)
<pid>               — Packet type
<len_hi> <len_lo>   — Length of (instruction + args + checksum), big-endian
<instr>             — Command byte (in command packets)
<args...>           — Variable payload
<chk_hi> <chk_lo>   — Checksum (sum of pid + len bytes + instr + args), big-endian
```

### Packet Types (PID)

| PID | Name | Direction | Description |
|---|---|---|---|
| `0x01` | Command | Host → Sensor | Commands sent by the ESP |
| `0x02` | Data | Sensor → Host | Intermediate data packets |
| `0x07` | ACK | Sensor → Host | Acknowledgement / response |
| `0x08` | End-Data | Sensor → Host | Final data packet in a stream |

### Commands Used

| Command | Code | Function |
|---|---|---|
| `LoadChar` | `0x07` | Load a stored template from flash slot → CharBuffer1 |
| `UpChar` | `0x08` | Transfer CharBuffer1 → Host (read out) |
| `DownChar` | `0x09` | Transfer Host → CharBuffer1 (write in) |
| `Store` | `0x06` | Store CharBuffer1 → flash slot |

---

## `fingerprint_backup.h` — Function Reference

### `build_cmd(instr, args)` — internal

```cpp
static std::vector<uint8_t> build_cmd(uint8_t instr, std::vector<uint8_t> args)
```

Constructs a complete Grow command packet.

1. Prepends `0xEF 0x01 0xFF 0xFF 0xFF 0xFF 0x01` (header + address + PID=command)
2. Calculates `len = 1 (instr) + args.size() + 2 (checksum)`
3. Appends `len` big-endian
4. Appends `instr` and `args`
5. Computes checksum: `sum of (pid + len_hi + len_lo + instr + all arg bytes)`
6. Appends checksum big-endian

---

### `read_pkt(uart, pid, conf, data, ms)` — internal

```cpp
static bool read_pkt(
    esphome::uart::UARTComponent *u,
    uint8_t &pid,
    uint8_t &conf,
    std::vector<uint8_t> &data,
    uint32_t ms = 3000)
```

Reads one complete packet from the UART within `ms` milliseconds.

**Watchdog feeding:** In the polling loop, if 1000ms passes without a byte arriving, `App.feed_wdt()` is called. This prevents the ESP32 watchdog from resetting the device during long waits (e.g. restore operations).

**Return value:** `true` if a complete packet was received within the timeout; `false` on timeout or parse error.

**Output parameters:**

| Param | Meaning |
|---|---|
| `pid` | Packet type (0x07 = ACK, 0x02 = data, 0x08 = end-data) |
| `conf` | For ACK packets: the confirmation code byte (`0x00` = success). For data/end-data packets: always `0` (no conf byte). |
| `data` | For ACK packets: payload after the conf byte. For data/end-data packets: full payload. Checksum bytes are stripped. |

**Algorithm:**
1. Sync on `0xEF 0x01` header (loops until found)
2. Read and discard 4-byte address
3. Read PID byte
4. Read 2-byte length
5. Read `length` payload bytes (includes trailing 2-byte checksum)
6. Strip checksum bytes from the end
7. If `pid == 0x07` (ACK): extract `conf` from first byte, remainder → `data`
8. Otherwise: `conf = 0`, all bytes → `data`

---

### `b64enc(in)` — internal

```cpp
static std::string b64enc(const std::vector<uint8_t> &in)
```

Standard base64 encoder. Converts raw bytes to a base64 string using the `A-Z a-z 0-9 + /` alphabet with `=` padding.

A 512-byte R503 template encodes to approximately **684 characters**.

---

### `b64dec(s)` — internal

```cpp
static std::vector<uint8_t> b64dec(const std::string &s)
```

Standard base64 decoder. Handles `=` padding. Silently maps unknown characters to 0.

---

### `backup_slot(uart, slot)` — **public**

```cpp
static std::string backup_slot(esphome::uart::UARTComponent *uart, int slot)
```

Reads the fingerprint template stored at `slot` from the R503's flash and returns it as a base64 string.

**Returns:** Base64-encoded template string (~684 chars), or `""` on error.

**Call requirements:**
- Sensor must be powered on and not sleeping
- No enrollment or scan in progress
- Best practice: call after a finger touch (the touch wakes the sensor; sensor stays on for `idle_period_to_sleep` = 300s)

**Step-by-step:**

```
1. UART flush
   - delay(30ms)
   - drain any pending bytes from fingerprint_grow component's scan loop

2. Send LoadChar(0x07) command: {buffer=1, slot_hi, slot_lo}
   - Read ACK
   - If conf != 0x00: log error, return ""
     (non-zero conf = empty slot, sensor error, wrong password)

3. Send UpChar(0x08) command: {buffer=1}
   - Read ACK
   - If conf != 0x00: log error, return ""

4. Collect data stream:
   - Read packets in a loop
   - pid=0x02 (data):     append payload to tmpl vector, continue loop
   - pid=0x08 (end-data): append payload to tmpl vector, exit loop
   (No ACK is sent between packets — the loop ends naturally on pid=0x08)

5. If tmpl is empty: return ""

6. Return b64enc(tmpl)
```

---

### `restore_slot(uart, slot, b64)` — **public**

```cpp
static bool restore_slot(
    esphome::uart::UARTComponent *uart,
    int slot,
    const std::string &b64)
```

Writes a base64-encoded template into slot `slot` in the R503's flash.

**Returns:** `true` on success, `false` on error.

**Call requirements:** Same as `backup_slot`. Sensor must be awake. The target slot does not need to be empty — any slot number in range can be written.

**Step-by-step:**

```
1. Decode b64 → raw bytes (tmpl vector)
   - If result is empty: log error, return false

2. UART flush
   - delay(30ms)
   - drain any pending bytes

3. Send DownChar(0x09) command: {buffer=1}
   - Read initial ACK
   - If conf != 0x00: log error, return false
     (non-zero = sensor asleep, busy, or wrong address)

4. Send template data in 128-byte chunks:
   - For each chunk except the last: pid=0x02 (data)
   - For the last chunk:             pid=0x08 (end-data)
   - After each chunk:  App.feed_wdt()   ← prevent watchdog reset
   - The sensor does NOT send an ACK after each data packet.
     It silently absorbs all packets into CharBuffer1.

5. delay(50ms)
   - Gives sensor time to finish receiving data from the TX FIFO

6. Send Store(0x06) command: {buffer=1, slot_hi, slot_lo}
   - Read ACK with 8-second timeout
     (sensor ACKs HERE — the single ACK covering the entire DownChar + Store operation)
   - If conf != 0x00 or timeout: log error, return false

7. Return true
```

**Critical protocol detail:** The Grow protocol sends exactly **one ACK** for the DownChar/data/Store sequence — after the `Store` command, not after each data packet. Waiting for a per-packet ACK will cause a timeout hang.

---

## Error Conditions

| Situation | Symptom | Resolution |
|---|---|---|
| Sensor is asleep | `LoadChar` or `DownChar` conf ≠ 0x00, or no response | Place a finger to wake the sensor (300s window), then retry |
| Empty slot | `LoadChar` returns conf ≠ 0x00 | Check that the slot is actually enrolled |
| Bad base64 | `b64dec` returns empty vector | Data was truncated or corrupted; re-run backup |
| Sensor busy (enrollment in progress) | Unexpected bytes in UART stream | Cancel enrollment first, then retry |
| WDT reset during restore | Device reboots mid-operation | `App.feed_wdt()` is called per-chunk and in the read loop |

---

## Timing Notes

- **Backup** typically completes in < 500ms (UART round-trip + data transfer)
- **Restore** typically completes in < 1s (send ~512 bytes + Store ACK)
- **Store ACK timeout** is 8 seconds — generous to allow for slow sensor flash writes
- **`idle_period_to_sleep`** = 300s gives a 5-minute window after a finger touch in which backup/restore can be safely performed

---

## Base64 Format

The backup data format is plain RFC 4648 base64 (no line breaks, no URL-safe variant). A 512-byte R503 template encodes to exactly 684 characters with padding.

Example prefix: `AQIDBA...` (binary fingerprint data)

This data is opaque — it is the raw internal template format used by the Grow ASIC. It cannot be meaningfully decoded without a compatible sensor.
