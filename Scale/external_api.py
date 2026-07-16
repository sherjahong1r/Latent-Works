"""
external_api.py — bizning o'z "tashqi API"miz.
ai_vision_reporter.py shu API'ga POST qilib, Groq'dan olingan JSON
hisobotni jo'natadi. Bu API ma'lumotni PostgreSQL'ga saqlaydi va
brauzerda ko'rish uchun oddiy sahifa ham beradi.

Ishga tushirish: py external_api.py
Server manzili: http://localhost:5001

Bu — httpbin.org (tashqi, ba'zan ishlamay qoladigan sinov xizmati)
o'rniga ishlatiladigan, o'zimiz to'liq nazorat qiladigan yechim.
"""

import json
from datetime import datetime

from flask import Flask, request, jsonify
from database import get_connection

app = Flask(__name__)


def init_reports_table():
    """ai_vision_reports jadvali mavjudligini ta'minlaydi."""
    conn = get_connection()
    with conn, conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ai_vision_reports (
                id SERIAL PRIMARY KEY,
                ts TIMESTAMP NOT NULL DEFAULT NOW(),
                payload JSONB NOT NULL
            )
        """)
    conn.close()


@app.route("/api/report", methods=["POST"])
def receive_report():
    """ai_vision_reporter.py dan JSON hisobotni qabul qiladi."""
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "JSON body kerak"}), 400

    conn = get_connection()
    with conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO ai_vision_reports (payload) VALUES (%s)",
            (json.dumps(data),),
        )
    conn.close()

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Yangi hisobot qabul qilindi: {data}")
    return jsonify({"status": "ok", "received": data}), 200


@app.route("/api/reports", methods=["GET"])
def list_reports():
    """So'nggi 20 ta hisobotni ko'rish uchun (JSON API)."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, ts, payload FROM ai_vision_reports ORDER BY id DESC LIMIT 20"
        )
        rows = cur.fetchall()
    conn.close()

    result = [
        {"id": r[0], "ts": r[1].isoformat(), "payload": r[2]} for r in rows
    ]
    return jsonify(result)


@app.route("/", methods=["GET"])
def home():
    """Brauzerda ko'rish uchun oddiy sahifa."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, ts, payload FROM ai_vision_reports ORDER BY id DESC LIMIT 10"
        )
        rows = cur.fetchall()
    conn.close()

    rows_html = ""
    for r in rows:
        rows_html += f"<tr><td>{r[0]}</td><td>{r[1]}</td><td><pre>{json.dumps(r[2], ensure_ascii=False, indent=2)}</pre></td></tr>"

    html = f"""
    <html><head><title>AI Vision hisobotlari</title>
    <style>
      body {{ font-family: sans-serif; padding: 24px; background: #f4f4f2; }}
      table {{ border-collapse: collapse; width: 100%; background: white; }}
      td, th {{ border: 1px solid #ddd; padding: 8px; vertical-align: top; text-align: left; }}
      pre {{ margin: 0; font-size: 12px; }}
    </style></head>
    <body>
      <h2>Qabul qilingan AI vision hisobotlari (so'nggi 10 ta)</h2>
      <table>
        <tr><th>ID</th><th>Vaqt</th><th>Ma'lumot</th></tr>
        {rows_html if rows_html else "<tr><td colspan=3>Hozircha hisobot yo'q</td></tr>"}
      </table>
    </body></html>
    """
    return html


if __name__ == "__main__":
    init_reports_table()
    print("O'z API serverimiz ishga tushdi: http://localhost:5001")
    print("Hisobotlarni ko'rish uchun brauzerda: http://localhost:5001")
    app.run(debug=True, port=5001)
