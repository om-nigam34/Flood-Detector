# Flood Guard Dashboard - backend
# Receives telemetry from the ESP32 receiver (water depth, flow rate,
# temperature, humidity, battery, signal strength) over HTTP POST,
# stores it, and serves a live dashboard + REST API for the frontend.

# Server listens on 0.0.0.0:5000 so devices on the same network
# (including the ESP32 receiver) can reach it.

import os
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone

from flask import Flask, g, jsonify, render_template, request

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.db")

# Shared-secret key the device must send in the "X-API-Key" header.
# Change this before deploying anywhere public, and set the same
# value in the ESP32 sketch / simulator.
API_KEY = os.environ.get("FLOOD_API_KEY", "changeme123")

# Thresholds used to classify a reading when the device doesn't
# already send a "status" field. Adjust to match the real sensor
# installation height / channel depth.
WARNING_DEPTH_CM = 70
CRITICAL_DEPTH_CM = 100

app = Flask(__name__)


# DB

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with closing(sqlite3.connect(DB_PATH)) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                node_id TEXT NOT NULL DEFAULT 'node-1',
                water_depth_cm REAL,
                flow_rate_lpm REAL,
                temperature_c REAL,
                humidity_pct REAL,
                battery_v REAL,
                rssi INTEGER,
                status TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                node_id TEXT NOT NULL,
                status TEXT NOT NULL,
                water_depth_cm REAL,
                message TEXT NOT NULL
            )
            """
        )
        db.commit()


# ------------------------------------------------------------ helpers

def classify(water_depth_cm, declared_status=None):
    """Decide normal / warning / critical.
    Trusts a status the device already computed, unless the raw
    depth clearly disagrees (defence in depth), otherwise falls
    back to the server-side thresholds."""
    if water_depth_cm is None:
        return declared_status or "normal"

    if water_depth_cm >= CRITICAL_DEPTH_CM:
        return "critical"
    if water_depth_cm >= WARNING_DEPTH_CM:
        return "warning"
    if declared_status in ("warning", "critical"):
        # device saw something (e.g. fast flow) the depth alone didn't capture
        return declared_status
    return "normal"


def row_to_dict(row):
    d = dict(row)
    d["iso_time"] = datetime.fromtimestamp(d["ts"], tz=timezone.utc).isoformat()
    return d


# -------------------------------------------------------------- routes

@app.route("/")
def dashboard():
    return render_template("index.html")


@app.route("/api/telemetry", methods=["POST"])
def post_telemetry():
    """Endpoint the ESP32 receiver (or the simulator) POSTs JSON to."""
    if request.headers.get("X-API-Key") != API_KEY:
        return jsonify({"error": "invalid or missing API key"}), 401

    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "expected JSON body"}), 400

    node_id = str(payload.get("node_id", "node-1"))
    water_depth_cm = payload.get("water_depth_cm")
    flow_rate_lpm = payload.get("flow_rate_lpm")
    temperature_c = payload.get("temperature_c")
    humidity_pct = payload.get("humidity_pct")
    battery_v = payload.get("battery_v")
    rssi = payload.get("rssi")
    declared_status = payload.get("status")

    status = classify(water_depth_cm, declared_status)
    ts = time.time()

    db = get_db()
    db.execute(
        """INSERT INTO readings
           (ts, node_id, water_depth_cm, flow_rate_lpm, temperature_c,
            humidity_pct, battery_v, rssi, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (ts, node_id, water_depth_cm, flow_rate_lpm, temperature_c,
         humidity_pct, battery_v, rssi, status),
    )

    if status in ("warning", "critical"):
        message = (
            f"{'CRITICAL' if status == 'critical' else 'Warning'}: "
            f"water depth {water_depth_cm:.1f} cm at {node_id}"
            if water_depth_cm is not None
            else f"{status.title()} condition reported by {node_id}"
        )
        db.execute(
            """INSERT INTO alerts (ts, node_id, status, water_depth_cm, message)
               VALUES (?, ?, ?, ?, ?)""",
            (ts, node_id, status, water_depth_cm, message),
        )

    db.commit()
    return jsonify({"ok": True, "status": status}), 201


@app.route("/api/latest")
def get_latest():
    node_id = request.args.get("node_id", "node-1")
    db = get_db()
    row = db.execute(
        "SELECT * FROM readings WHERE node_id = ? ORDER BY ts DESC LIMIT 1",
        (node_id,),
    ).fetchone()
    if row is None:
        return jsonify(None)
    return jsonify(row_to_dict(row))


@app.route("/api/history")
def get_history():
    node_id = request.args.get("node_id", "node-1")
    limit = min(int(request.args.get("limit", 100)), 1000)
    db = get_db()
    rows = db.execute(
        """SELECT * FROM (
               SELECT * FROM readings WHERE node_id = ? ORDER BY ts DESC LIMIT ?
           ) ORDER BY ts ASC""",
        (node_id, limit),
    ).fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@app.route("/api/alerts")
def get_alerts():
    limit = min(int(request.args.get("limit", 20)), 200)
    db = get_db()
    rows = db.execute(
        "SELECT * FROM alerts ORDER BY ts DESC LIMIT ?", (limit,)
    ).fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@app.route("/api/nodes")
def get_nodes():
    db = get_db()
    rows = db.execute("SELECT DISTINCT node_id FROM readings").fetchall()
    return jsonify([r["node_id"] for r in rows])


@app.route("/healthz")
def healthz():
    return jsonify({"ok": True})


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)