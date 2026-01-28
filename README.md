# FRITZ!Box CallMonitor (Raw + TR-064) — Home Assistant Custom Integration

Monitor incoming/outgoing calls from your **AVM FRITZ!Box** in Home Assistant using the built‑in **CallMonitor TCP stream (port 1012)** and optionally resolve caller names via **TR-064 phonebook** — **without** relying on `fritzconnection`.

[![Validate with HACS](https://img.shields.io/badge/HACS-validated-41BDF5)](https://hacs.xyz/)
[![hassfest](https://img.shields.io/badge/hassfest-passing-brightgreen)](https://developers.home-assistant.io/docs/creating_integration_manifest/)
[![MIT License](https://img.shields.io/badge/license-MIT-informational)](LICENSE.md)

> ⚠️ This is a third‑party project, not affiliated with AVM.

---

## ✨ Features

- **Raw CallMonitor** connection via TCP (`<fritz_ip>:1012`) with:
  - async socket reader
  - automatic reconnect with backoff
  - TCP keepalive (helps with Docker/NAT idle drops)
- Exposes a **sensor** with call state:
  - `idle` / `ringing` / `dialing` / `talking`
  - fully translated (EN/IT) via HA translation system
- Shows useful attributes like:
  - `from`, `to`, `device`, `duration`, timestamps
  - `from_name` / `to_name` / `with_name` if the phonebook can resolve numbers
- **TR-064 phonebook** name resolution:
  - downloads and parses FRITZ phonebook XML
  - supports **HTTP Digest authentication** (required on many FRITZ!OS versions)
  - supports prefixes (e.g. `+39,0039,39`) to match different number formats
- **Options flow** to edit configuration after setup (password, prefixes, phonebook id, TR-064 port).
- Automatic reload of the integration when Options are saved.

---

## ✅ Requirements / Compatibility

- Home Assistant: **2024.8** or newer (earlier may work, untested)
- FRITZ!Box must have:
  - **CallMonitor enabled** (TCP port `1012`)
  - **TR-064 enabled** (for phonebook name resolution)

> Note: Call monitoring works even without TR-064. TR-064 is only required to show contact names.

---

## 🔧 Installation

### Option A — HACS (recommended)
1. Make sure you have [HACS](https://hacs.xyz/) installed.
2. In Home Assistant: **HACS → Integrations → ⋮ (three dots) → Custom repositories**  
   Add: `https://github.com/Sanji78/fritzbox_callmonitor_raw`  
   Category: **Integration**
3. Find **FRITZ!Box CallMonitor (Raw + TR-064)** in HACS and click **Download**.
4. **Restart** Home Assistant.

### Option B — Manual
1. Copy the folder `custom_components/fritzbox_callmonitor_raw` into your HA config folder:
   - `<config>/custom_components/fritzbox_callmonitor_raw`
2. **Restart** Home Assistant.

---

## ⚙️ Configuration

1. Home Assistant → **Settings → Devices & services → Add Integration**
2. Search for **FRITZ!Box CallMonitor (Raw + TR-064)**
3. Enter:
   - **Host**: FRITZ!Box IP (e.g. `192.168.1.1`)
   - **CallMonitor port**: default `1012`
   - **TR-064 port**: default `49000`
   - **Username / Password**: your FRITZ!Box credentials (used for TR-064 phonebook)
   - **Phonebook ID**: usually `0` for the main phonebook
   - **Prefixes**: comma separated (example below)
4. On success, entities are created.

### Prefixes (recommended for Italy)
Use:
- `+39, 0039, 39`

This helps matching:
- phonebook entries stored as `+393489963985`
- call monitor events showing `3489963985`
- or other national/international formats

---

## 📟 Entities

### Sensor: Call state
A single sensor with an enum state:
- **Idle**
- **Ringing**
- **Dialing**
- **Talking**

Attributes may include:
- `type` (`incoming` / `outgoing`)
- `from`, `to`, `device`, `duration`
- `initiated`, `accepted`, `closed`
- name resolution attributes:
  - `from_name`, `to_name`, `with_name`
- diagnostics:
  - `phonebook_status`
  - `phonebook_entries`
  - `phonebook_last_refresh`

---

## 🧪 Troubleshooting

### 1) Call state changes in “History”, but you often see “Idle”
This is normal: calls can transition quickly back to idle. The entity history will show the short events.
(If you want a “hold time” feature to keep the last call state visible longer, open an issue/PR.)

### 2) No caller names appear
- Ensure TR-064 is enabled and your FRITZ user has permissions.
- Verify TR-064 is reachable:
  ```bash
  curl -s http://<FRITZ_IP>:49000/tr64desc.xml | head
  ```
- Some FRITZ!OS versions require **Digest auth** for TR-064 SOAP calls. This integration supports it.
- Use correct **prefixes** to match number formats.

### 3) Changing options doesn’t apply
Use **Settings → Devices & services → (integration) → Configure**.  
Saving options triggers an integration reload to apply the new parameters.

---

## 🙌 Contributing
PRs and issues are welcome. Please open an issue and include:
- HA logs (Settings → System → Logs)
- one raw callmonitor line (`RING/CALL/CONNECT/DISCONNECT`)
- your phone number format in the FRITZ phonebook (redact sensitive info if needed)

---

## ❤️ Donate
If this project helps you, consider buying me a coffee:  
**[PayPal](https://www.paypal.me/elenacapasso80)**

..and yes... 😊 the paypal account is correct. Thank you so much!

---

## 📜 License
[MIT](LICENSE.md)