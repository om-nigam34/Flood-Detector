# Flood Guard Dashboard

A working website for the LoRa-based flood detection project. The ESP32
receiver POSTs sensor telemetry to it over WiFi; the site stores it and
shows it live, with a flashing alert banner when water levels hit
warning/critical thresholds.

## What's included
- `app.py` — Flask backend: REST API + SQLite storage + serves the dashboard
- `templates/index.html`, `static/style.css`, `static/app.js` — the live dashboard (no external dependencies, works offline)
- `simulate_sensor.py` — fake sensor that POSTs realistic rising/falling readings, so you can see it working before any hardware is wired up
- `esp32_receiver_dashboard.ino` — code to add to the receiver sketch so it posts real LoRa telemetry to this site

## 1. Run the site

```bash
pip install -r requirements.txt
python app.py
```

Open **http://localhost:5000** — you'll see the dashboard (empty until data arrives).

## 2. See it work (no hardware needed yet)

In a second terminal, with the server still running:

```bash
python simulate_sensor.py
```

Refresh the dashboard — metrics update every 3 seconds, the status card
and chart move through normal → warning → critical → back to normal on
a loop, and the red alert banner + alert log fire automatically when
the simulated depth crosses the thresholds. Stop it with Ctrl+C.

## 3. Connect the real ESP32 receiver

1. Find the IP address of the computer running `app.py` on your WiFi network (e.g. `192.168.1.50`).
2. In `esp32_receiver_dashboard.ino`, set `WIFI_SSID`, `WIFI_PASSWORD`, and `DASHBOARD_URL` to `http://<that-ip>:5000/api/telemetry`.
3. Install the `ArduinoJson` library in the Arduino IDE (Library Manager).
4. Merge the WiFi/HTTP block into your existing receiver sketch (the one handling SX1276/SX1278 LoRa receive, OLED, relay/siren, SIM800L from the report) and call `sendToDashboard(...)` right after you decode each LoRa packet — see the comments in the file.
5. Make sure the ESP32 receiver and the computer running the server are on the **same WiFi network** (or deploy the Flask app somewhere internet-reachable and use that URL instead).

The receiver keeps doing its existing job (local OLED display, siren/relay, SMS via SIM800L) — this just additionally mirrors the same readings to the website.

## API reference

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/telemetry` | POST | Device sends a reading. Requires header `X-API-Key: <key>`. Body: `{"node_id","water_depth_cm","flow_rate_lpm","temperature_c","humidity_pct","battery_v","rssi","status"}` (all optional except at least `water_depth_cm` or `status`) |
| `/api/latest` | GET | Most recent reading |
| `/api/history?limit=100` | GET | Recent readings, oldest→newest |
| `/api/alerts?limit=20` | GET | Recent warning/critical events |
| `/healthz` | GET | Health check |

## Configuration

- **API key**: set via `FLOOD_API_KEY` env var before running `app.py` (defaults to `changeme123` — change this before any real/public deployment). Use the same value in the ESP32 sketch / simulator.
- **Thresholds**: `WARNING_DEPTH_CM` and `CRITICAL_DEPTH_CM` near the top of `app.py` (defaults: 70 cm / 100 cm) — set these to match your actual sensor mounting height and the channel/riverbank depth you're monitoring.

## Deploying beyond your local network

Running `python app.py` only serves your local network. To make the
dashboard reachable from anywhere (so the ESP32 can post to it even
off your home WiFi, or so you can check it from your phone over
mobile data), deploy it to a small always-on host — e.g. Render,
Railway, Fly.io, or a cheap VPS — pointing `DASHBOARD_URL` in the
ESP32 sketch at that public URL instead. The code doesn't need any
changes for this; only `data.db` would move from a local SQLite file
to a persistent volume on the host.