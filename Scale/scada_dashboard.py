"""
scada_dashboard.py — SCADA HMI vazifasini bajaruvchi veb-server (Flask).
Brauzerda real vaqt (2 soniyada bir marta yangilanadigan) monitoring ko'rsatadi.

Ishga tushirish: python scada_dashboard.py
So'ng brauzerda: http://localhost:5000
"""

from flask import Flask, render_template, jsonify
from database import get_connection, fetch_recent_readings, fetch_recent_alarms

app = Flask(__name__)


@app.route("/")
def dashboard():
    return render_template("dashboard.html")


@app.route("/api/latest")
def api_latest():
    conn = get_connection()
    readings = fetch_recent_readings(conn, limit=1)
    alarms = fetch_recent_alarms(conn, limit=10)
    conn.close()

    latest = readings[-1] if readings else {}
    return jsonify({
        "reading": latest,
        "alarms": alarms,
    })


@app.route("/api/trend/<sensor_name>")
def api_trend(sensor_name):
    conn = get_connection()
    readings = fetch_recent_readings(conn, limit=50)
    conn.close()
    values = [r.get(sensor_name) for r in readings]
    return jsonify({"values": values})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
