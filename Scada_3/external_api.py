"""
external_api.py — TIZIMNING INTERFEYSI. main.py'dan ALOHIDA jarayon
sifatida ishga tushiriladi, faqat bazani o'qiydi (GET), yozmaydi.

ISHGA TUSHIRISH (development):
    py external_api.py
    -> http://localhost:5001

ISHGA TUSHIRISH (production, tavsiya etiladi):
    uvicorn external_api:app --host 0.0.0.0 --port 5001
"""

from pathlib import Path

from fastapi.responses import HTMLResponse
from fastapi import FastAPI

from database import init_all_tables, get_connection

app = FastAPI(title="SCADA AI Monitoring — Interfeys")


# ─────────────────────────── RO'YXATLAR (GET, faqat o'qish) ─────────────

@app.get("/api/reports")
def list_reports():
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, ts, model, payload
            FROM vision_reports ORDER BY id DESC LIMIT 10
        """)
        rows = cur.fetchall()
    conn.close()
    return [{"id": r[0], "ts": r[1].isoformat(), "model": r[2], "payload": r[3]} for r in rows]


@app.get("/api/insights")
def list_insights():
    """To'liq bo'lim uchun — oxirgi 10 ta xulosa (home sahifada esa
    faqat birinchisi ishlatiladi)."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, ts, severity, summary, trend_analysis, recommendation
            FROM advisor_insights ORDER BY id DESC LIMIT 10
        """)
        rows = cur.fetchall()
    conn.close()
    return [
        {"id": r[0], "ts": r[1].isoformat(), "severity": r[2], "summary": r[3],
         "trend_analysis": r[4], "recommendation": r[5]}
        for r in rows
    ]


@app.get("/api/plant-state")
def get_plant_state_api():
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT ts, state FROM plant_state WHERE id = 1")
        row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {"ts": row[0].isoformat(), "state": row[1]}


@app.get("/api/predictions")
def list_predictions():
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, ts, interval_seconds, risk_level, summary, details
            FROM plant_predictions ORDER BY id DESC LIMIT 10
        """)
        rows = cur.fetchall()
    conn.close()
    return [
        {"id": r[0], "ts": r[1].isoformat(), "interval_seconds": r[2],
         "risk_level": r[3], "summary": r[4], "details": r[5]}
        for r in rows
    ]


@app.get("/api/shift-reports")
def list_shift_reports():
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, ts, period_start, period_end, report
            FROM shift_reports ORDER BY id DESC LIMIT 10
        """)
        rows = cur.fetchall()
    conn.close()
    return [
        {"id": r[0], "ts": r[1].isoformat(),
         "period_start": r[2].isoformat() if r[2] else None,
         "period_end": r[3].isoformat() if r[3] else None,
         "report": r[4]}
        for r in rows
    ]


# ──────────────────────── BOSH SAHIFA (HTML) ─────────────────────
# Interfeys endi shu fayl ichida emas, yonidagi dashboard.html da turadi.
# Sababi: dizaynni o'zgartirish uchun Python kodiga tegish kerak emas —
# HTML faylni tahrirlab, brauzerni yangilasangiz kifoya.
#
# Ko'rsatiladigan ma'lumotlar tarkibi O'ZGARMAGAN: o'sha 6 ta bo'lim
# (Bosh sahifa, AI Maslahatchi, Zavod xotirasi, Bashorat, Smena
# hisobotlari, Xom JSON) va o'sha 5 ta API endpoint.

DASHBOARD_FILE = Path(__file__).with_name("dashboard.html")

_ZAXIRA_HTML = """<!DOCTYPE html><html lang="uz"><head><meta charset="UTF-8">
<title>SCADA AI Monitoring</title></head><body style="font-family:sans-serif;padding:40px">
<h1>Interfeys fayli topilmadi</h1>
<p><code>dashboard.html</code> fayli <code>external_api.py</code> yonida turishi kerak.</p>
<p>API hamon ishlayapti: <a href="/docs">/docs</a></p>
</body></html>"""


def _dashboard_html() -> str:
    """dashboard.html ni diskdan o'qiydi.

    HAR SO'ROVDA qayta o'qiladi — shunda dizaynni tahrirlagach serverni
    qayta ishga tushirish shart emas, brauzerni yangilash kifoya."""
    try:
        return DASHBOARD_FILE.read_text(encoding="utf-8")
    except OSError as e:
        print(f"[API] dashboard.html o'qilmadi ({e}) — zaxira sahifa berildi.")
        return _ZAXIRA_HTML


@app.get("/", response_class=HTMLResponse)
def home():
    return _dashboard_html()


if __name__ == "__main__":
    import uvicorn

    init_all_tables()
    print("Interfeys ishga tushdi: http://localhost:5001")
    print("Interaktiv (Swagger) interfeys: http://localhost:5001/docs")
    uvicorn.run(app, host="0.0.0.0", port=5001)