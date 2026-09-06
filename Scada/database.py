"""
database.py — bazaga ulanish, jadvallarni yaratish va yordamchi
funksiyalar.

JADVALLAR:
  - vision_reports    : har bir skrinshotning xom AI tahlili (JSON)
  - metric_history    : vision_reports'dan chiqarilgan RAQAMLI
                         qiymatlar, vaqt bo'yicha (oddiy time-series)
  - plant_state       : ZAVODNING JORIY "XOTIRASI" — bitta qator
                         (id=1), har advisor siklida yangilanadi
  - advisor_insights  : AI maslahatchining tarixiy xulosalari (matn)
  - plant_predictions : bashorat natijalari (10/20/30 daqiqa)
  - shift_reports     : avtomatik smena hisobotlari
"""

import json
import re
from datetime import datetime, timedelta

import psycopg
from config import DB_CONFIG


def get_connection():
    return psycopg.connect(**DB_CONFIG)


def init_all_tables():
    conn = get_connection()
    with conn, conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS vision_reports (
                id SERIAL PRIMARY KEY,
                ts TIMESTAMP NOT NULL DEFAULT NOW(),
                model TEXT,
                payload JSONB NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS metric_history (
                id SERIAL PRIMARY KEY,
                ts TIMESTAMP NOT NULL DEFAULT NOW(),
                vision_report_id INTEGER REFERENCES vision_reports(id) ON DELETE CASCADE,
                metric_name TEXT NOT NULL,
                value DOUBLE PRECISION NOT NULL
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_metric_history_name_ts
            ON metric_history (metric_name, ts)
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS plant_state (
                id INTEGER PRIMARY KEY DEFAULT 1,
                ts TIMESTAMP NOT NULL DEFAULT NOW(),
                state JSONB NOT NULL,
                CONSTRAINT single_row CHECK (id = 1)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS advisor_insights (
                id SERIAL PRIMARY KEY,
                ts TIMESTAMP NOT NULL DEFAULT NOW(),
                severity TEXT,
                summary TEXT,
                trend_analysis TEXT,
                recommendation TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS plant_predictions (
                id SERIAL PRIMARY KEY,
                ts TIMESTAMP NOT NULL DEFAULT NOW(),
                interval_seconds INTEGER,
                risk_level TEXT,
                summary TEXT,
                details JSONB
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS shift_reports (
                id SERIAL PRIMARY KEY,
                ts TIMESTAMP NOT NULL DEFAULT NOW(),
                period_start TIMESTAMP,
                period_end TIMESTAMP,
                report TEXT
            )
        """)
    conn.close()


# ─────────────────────────── VISION REPORTS + METRICS ───────────────────

_NUMBER_RE = re.compile(r"-?\d[\d,]*\.?\d*")


def _try_parse_number(value) -> float | None:
    """'8,800.0 gal' -> 8800.0, '0.124' -> 0.124, '23%' -> 23.0,
    'On'/'Off' -> None (raqam emas). Faqat matndagi BIRINCHI sonni
    oladi (birlik/o'lchov nomi e'tiborsiz qoldiriladi)."""
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    m = _NUMBER_RE.search(value.replace(",", ""))
    if not m:
        return None
    try:
        return float(m.group())
    except ValueError:
        return None


def save_vision_report(payload: dict, model: str, captured_at: datetime | None = None) -> int:
    """Xom JSON tahlilni vision_reports'ga yozadi VA readings ichidagi
    har bir raqamli qiymatni metric_history'ga alohida-alohida yozadi
    (time-series uchun). Yangi yozuv id'sini qaytaradi.

    `captured_at` — skrinshot HAQIQATDA OLINGAN vaqt (agar berilsa).
    Bu MUHIM: AI tahlili bir necha soniya (yoki qayta urinishlar bilan
    bir necha daqiqa) davom etishi mumkin — agar captured_at berilmasa,
    yozuv vaqti "tahlil TUGAGAN" vaqt bo'lib qoladi, bu esa haqiqiy
    SCADA holati kuzatilgan vaqtdan farq qilishi mumkin. captured_at
    berilsa, aynan o'sha (skrinshot olingan) vaqt saqlanadi."""
    conn = get_connection()
    with conn, conn.cursor() as cur:
        if captured_at is not None:
            cur.execute(
                "INSERT INTO vision_reports (ts, model, payload) VALUES (%s, %s, %s) RETURNING id, ts",
                (captured_at, model, json.dumps(payload)),
            )
        else:
            cur.execute(
                "INSERT INTO vision_reports (model, payload) VALUES (%s, %s) RETURNING id, ts",
                (model, json.dumps(payload)),
            )
        report_id, ts = cur.fetchone()

        readings = payload.get("readings", {}) if isinstance(payload, dict) else {}
        rows = []
        for name, raw_value in readings.items():
            num = _try_parse_number(raw_value)
            if num is not None:
                rows.append((ts, report_id, name, num))

        if rows:
            cur.executemany(
                """INSERT INTO metric_history (ts, vision_report_id, metric_name, value)
                   VALUES (%s, %s, %s, %s)""",
                rows,
            )
    conn.close()
    return report_id


def get_recent_metric_series(metric_name: str, minutes: int) -> list[tuple[datetime, float]]:
    """Berilgan metrikaning oxirgi `minutes` daqiqalik (ts, value)
    juftliklarini, eskisidan yangisiga qarab qaytaradi."""
    cutoff = datetime.now() - timedelta(minutes=minutes)
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT ts, value FROM metric_history
               WHERE metric_name = %s AND ts >= %s
               ORDER BY ts ASC""",
            (metric_name, cutoff),
        )
        rows = cur.fetchall()
    conn.close()
    return rows


def get_recent_metric_names(minutes: int) -> list[str]:
    """Oxirgi `minutes` daqiqada kamida bitta marta ko'ringan barcha
    metrika nomlari ro'yxati."""
    cutoff = datetime.now() - timedelta(minutes=minutes)
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT metric_name FROM metric_history WHERE ts >= %s",
            (cutoff,),
        )
        rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]


def get_latest_vision_report() -> dict | None:
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, ts, model, payload FROM vision_reports ORDER BY id DESC LIMIT 1"
        )
        row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {"id": row[0], "ts": row[1], "model": row[2], "payload": row[3]}


# ─────────────────────────── PLANT STATE MEMORY ──────────────────────────

def get_plant_state() -> dict | None:
    """Zavodning joriy "xotira" holatini o'qiydi (bitta qator, id=1).
    Hali mavjud bo'lmasa None qaytaradi (birinchi ishga tushirish)."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT ts, state FROM plant_state WHERE id = 1")
        row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {"ts": row[0], "state": row[1]}


def save_plant_state(state: dict):
    """Zavod xotirasini yangilaydi (UPSERT — doim bitta qator, id=1)."""
    conn = get_connection()
    with conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO plant_state (id, state) VALUES (1, %s)
               ON CONFLICT (id) DO UPDATE SET state = EXCLUDED.state, ts = NOW()""",
            (json.dumps(state),),
        )
    conn.close()


# ─────────────────────────── ADVISOR INSIGHTS ────────────────────────────

def save_advisor_insight(severity: str, summary: str, trend_analysis: str, recommendation: str):
    conn = get_connection()
    with conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO advisor_insights (severity, summary, trend_analysis, recommendation)
               VALUES (%s, %s, %s, %s)""",
            (severity, summary, trend_analysis, recommendation),
        )
    conn.close()


def get_recent_insights(limit: int) -> list[dict]:
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT id, ts, severity, summary, trend_analysis, recommendation
               FROM advisor_insights ORDER BY id DESC LIMIT %s""",
            (limit,),
        )
        rows = cur.fetchall()
    conn.close()
    return [
        {"id": r[0], "ts": r[1], "severity": r[2], "summary": r[3],
         "trend_analysis": r[4], "recommendation": r[5]}
        for r in rows
    ]


def get_insights_between(start: datetime, end: datetime) -> list[dict]:
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT id, ts, severity, summary, trend_analysis, recommendation
               FROM advisor_insights WHERE ts >= %s AND ts < %s ORDER BY ts ASC""",
            (start, end),
        )
        rows = cur.fetchall()
    conn.close()
    return [
        {"id": r[0], "ts": r[1], "severity": r[2], "summary": r[3],
         "trend_analysis": r[4], "recommendation": r[5]}
        for r in rows
    ]


# ─────────────────────────── PREDICTIONS ─────────────────────────────────

def save_prediction(interval_seconds: int, risk_level: str, summary: str, details: dict):
    conn = get_connection()
    with conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO plant_predictions (interval_seconds, risk_level, summary, details)
               VALUES (%s, %s, %s, %s)""",
            (interval_seconds, risk_level, summary, json.dumps(details)),
        )
    conn.close()


def get_recent_predictions(limit: int) -> list[dict]:
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT id, ts, interval_seconds, risk_level, summary, details
               FROM plant_predictions ORDER BY id DESC LIMIT %s""",
            (limit,),
        )
        rows = cur.fetchall()
    conn.close()
    return [
        {"id": r[0], "ts": r[1], "interval_seconds": r[2], "risk_level": r[3],
         "summary": r[4], "details": r[5]}
        for r in rows
    ]


# ─────────────────────────── SHIFT REPORTS ────────────────────────────────

def save_shift_report(period_start: datetime, period_end: datetime, report: str):
    conn = get_connection()
    with conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO shift_reports (period_start, period_end, report)
               VALUES (%s, %s, %s)""",
            (period_start, period_end, report),
        )
    conn.close()


def get_recent_shift_reports(limit: int) -> list[dict]:
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT id, ts, period_start, period_end, report
               FROM shift_reports ORDER BY id DESC LIMIT %s""",
            (limit,),
        )
        rows = cur.fetchall()
    conn.close()
    return [
        {"id": r[0], "ts": r[1], "period_start": r[2], "period_end": r[3], "report": r[4]}
        for r in rows
    ]


def get_last_shift_report_end() -> datetime | None:
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT period_end FROM shift_reports ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
    conn.close()
    return row[0] if row else None
