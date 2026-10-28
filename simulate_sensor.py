"""
Sensor simulator — stands in for the real ESP32 receiver so you can
test the dashboard end-to-end before hardware is wired up.

Run (server must already be running):
    python simulate_sensor.py
"""

import argparse
import math
import random
import time

import requests

parser = argparse.ArgumentParser()
parser.add_argument("--url", default="http://localhost:5000")
parser.add_argument("--key", default="changeme123")
parser.add_argument("--node-id", default="node-1")
parser.add_argument("--interval", type=float, default=3.0)
args = parser.parse_args()

endpoint = args.url.rstrip("/") + "/api/telemetry"
headers = {"X-API-Key": args.key}

print(f"Simulating sensor '{args.node_id}' -> {endpoint}  (Ctrl+C to stop)")

start = time.time()
cycle_seconds = 90  # one full rise-and-fall cycle

try:
    while True:
        elapsed = time.time() - start
        phase = (elapsed % cycle_seconds) / cycle_seconds * 2 * math.pi
        water_depth_cm = round(65 + 55 * math.sin(phase) + random.uniform(-2, 2), 1)
        water_depth_cm = max(water_depth_cm, 0)

        flow_rate_lpm = round(max(0, water_depth_cm * 0.15 + random.uniform(-1, 1)), 2)
        temperature_c = round(27 + random.uniform(-1.5, 1.5), 1)
        humidity_pct = round(65 + random.uniform(-5, 5), 1)
        battery_v = round(3.9 - (elapsed / 10000), 2)
        rssi = -random.randint(60, 95)

        payload = {
            "node_id": args.node_id,
            "water_depth_cm": water_depth_cm,
            "flow_rate_lpm": flow_rate_lpm,
            "temperature_c": temperature_c,
            "humidity_pct": humidity_pct,
            "battery_v": battery_v,
            "rssi": rssi,
        }

        try:
            r = requests.post(endpoint, json=payload, headers=headers, timeout=5)
            print(f"depth={water_depth_cm:6.1f}cm  -> {r.status_code} {r.json()}")
        except requests.RequestException as e:
            print(f"POST failed: {e}")

        time.sleep(args.interval)
except KeyboardInterrupt:
    print("\nStopped.")