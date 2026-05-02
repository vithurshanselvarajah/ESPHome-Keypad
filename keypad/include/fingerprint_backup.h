#pragma once

#include <vector>
#include <string>
#include "esphome/components/uart/uart.h"
#include "esphome/core/application.h"

namespace fp_backup {

static std::vector<uint8_t> build_cmd(uint8_t instr, std::vector<uint8_t> args) {
  std::vector<uint8_t> p = {0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x01};
  uint16_t len = 1 + (uint16_t)args.size() + 2;
  p.push_back(len >> 8);  p.push_back(len & 0xFF);
  p.push_back(instr);
  p.insert(p.end(), args.begin(), args.end());
  uint16_t chk = 0x01 + (len >> 8) + (len & 0xFF) + instr;
  for (auto b : args) chk += b;
  p.push_back(chk >> 8);  p.push_back(chk & 0xFF);
  return p;
}

static bool read_pkt(esphome::uart::UARTComponent *u, uint8_t &pid,
                     uint8_t &conf, std::vector<uint8_t> &data,
                     uint32_t ms = 3000) {
  uint32_t t0 = millis();
  uint32_t last_wdt = t0;
  uint8_t b;
  auto rb = [&](uint8_t &out) -> bool {
    while ((millis() - t0) < ms) {
      if (u->available()) { u->read_byte(&out); return true; }
      uint32_t now = millis();
      if (now - last_wdt >= 1000) { App.feed_wdt(); last_wdt = now; }
    }
    return false;
  };

  for (int s = 0;;) {
    if (!rb(b)) return false;
    if      (s == 0 && b == 0xEF) s = 1;
    else if (s == 1 && b == 0x01) break;
    else s = (b == 0xEF) ? 1 : 0;
  }
  for (int i = 0; i < 4; i++) if (!rb(b)) return false;
  if (!rb(pid)) return false;
  uint8_t lh, ll;
  if (!rb(lh) || !rb(ll)) return false;
  uint16_t len = ((uint16_t)lh << 8) | ll;
  std::vector<uint8_t> raw;
  raw.reserve(len);
  for (uint16_t i = 0; i < len; i++) { if (!rb(b)) return false; raw.push_back(b); }
  if (raw.size() < 2) return false;
  raw.resize(raw.size() - 2);
  if (pid == 0x07) {
    if (raw.empty()) return false;
    conf = raw[0];
    data.assign(raw.begin() + 1, raw.end());
  } else {
    conf = 0;
    data = raw;
  }
  return true;
}

static const char B64[] =
  "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

static std::string b64enc(const std::vector<uint8_t> &in) {
  std::string out;
  for (size_t i = 0; i < in.size(); i += 3) {
    uint32_t v = (uint32_t)in[i] << 16;
    if (i + 1 < in.size()) v |= (uint32_t)in[i + 1] << 8;
    if (i + 2 < in.size()) v |= in[i + 2];
    out += B64[(v >> 18) & 63];
    out += B64[(v >> 12) & 63];
    out += (i + 1 < in.size()) ? B64[(v >> 6) & 63] : '=';
    out += (i + 2 < in.size()) ? B64[v & 63]        : '=';
  }
  return out;
}

static uint8_t b64val(char c) {
  if (c >= 'A' && c <= 'Z') return c - 'A';
  if (c >= 'a' && c <= 'z') return c - 'a' + 26;
  if (c >= '0' && c <= '9') return c - '0' + 52;
  return (c == '+') ? 62 : (c == '/') ? 63 : 0;
}

static std::vector<uint8_t> b64dec(const std::string &s) {
  std::vector<uint8_t> out;
  for (size_t i = 0; i + 3 < s.size(); i += 4) {
    uint32_t v = ((uint32_t)b64val(s[i])     << 18)
               | ((uint32_t)b64val(s[i + 1]) << 12)
               | ((uint32_t)b64val(s[i + 2]) <<  6)
               |  (uint32_t)b64val(s[i + 3]);
    out.push_back((v >> 16) & 0xFF);
    if (s[i + 2] != '=') out.push_back((v >> 8) & 0xFF);
    if (s[i + 3] != '=') out.push_back(v & 0xFF);
  }
  return out;
}

static std::string backup_slot(esphome::uart::UARTComponent *uart, int slot) {
  { uint8_t d; delay(30); while (uart->available()) uart->read_byte(&d); }

  uint8_t pid, conf = 0xFF;
  std::vector<uint8_t> data;

  auto lc = build_cmd(0x07, {0x01, (uint8_t)(slot >> 8), (uint8_t)(slot & 0xFF)});
  uart->write_array(lc.data(), lc.size());
  if (!read_pkt(uart, pid, conf, data) || conf != 0x00) {
    ESP_LOGE("fp_backup", "LoadChar slot %d failed: conf=0x%02X", slot, conf);
    return "";
  }

  auto uc = build_cmd(0x08, {0x01});
  uart->write_array(uc.data(), uc.size());
  if (!read_pkt(uart, pid, conf, data) || conf != 0x00) {
    ESP_LOGE("fp_backup", "UpChar ack failed: conf=0x%02X", conf);
    return "";
  }

  std::vector<uint8_t> tmpl;
  do {
    if (!read_pkt(uart, pid, conf, data)) {
      ESP_LOGE("fp_backup", "UpChar data timeout");
      return "";
    }
    tmpl.insert(tmpl.end(), data.begin(), data.end());
  } while (pid == 0x02);

  if (tmpl.empty()) return "";
  ESP_LOGD("fp_backup", "Backup slot %d OK: %u bytes", slot, (unsigned)tmpl.size());
  return b64enc(tmpl);
}

static bool restore_slot(esphome::uart::UARTComponent *uart, int slot, const std::string &b64) {
  auto tmpl = b64dec(b64);
  if (tmpl.empty()) {
    ESP_LOGE("fp_backup", "restore_slot: empty/invalid base64");
    return false;
  }

  { uint8_t d; delay(30); while (uart->available()) uart->read_byte(&d); }

  uint8_t pid, conf = 0xFF;
  std::vector<uint8_t> data;

  auto dc = build_cmd(0x09, {0x01});
  uart->write_array(dc.data(), dc.size());
  if (!read_pkt(uart, pid, conf, data) || conf != 0x00) {
    ESP_LOGE("fp_backup", "DownChar ack failed: conf=0x%02X", conf);
    return false;
  }

  size_t off = 0;
  while (off < tmpl.size()) {
    size_t   chunk  = std::min((size_t)128, tmpl.size() - off);
    bool     last   = (off + chunk >= tmpl.size());
    uint8_t  pkg_id = last ? 0x08 : 0x02;
    uint16_t len    = (uint16_t)chunk + 2;

    std::vector<uint8_t> pkt = {
      0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF,
      pkg_id,
      (uint8_t)(len >> 8), (uint8_t)(len & 0xFF)
    };
    uint16_t chk = pkg_id + (len >> 8) + (len & 0xFF);
    for (size_t i = off; i < off + chunk; i++) {
      pkt.push_back(tmpl[i]);
      chk += tmpl[i];
    }
    pkt.push_back(chk >> 8);  pkt.push_back(chk & 0xFF);
    uart->write_array(pkt.data(), pkt.size());
    off += chunk;
    App.feed_wdt();
  }
  delay(50);

  auto st = build_cmd(0x06, {0x01, (uint8_t)(slot >> 8), (uint8_t)(slot & 0xFF)});
  uart->write_array(st.data(), st.size());
  pid = 0; conf = 0xFF; data.clear();
  if (!read_pkt(uart, pid, conf, data, 8000) || conf != 0x00) {
    ESP_LOGE("fp_backup", "Store slot %d %s: conf=0x%02X",
             slot, conf == 0xFF ? "TIMEOUT" : "failed", conf);
    return false;
  }

  ESP_LOGD("fp_backup", "Restore slot %d OK", slot);
  return true;
}

}
