# """
# database.py — bazaga ulanish va jadvallarni yaratish.
# psycopg (3-versiya) kutubxonasidan foydalanadi.

# MUHIM O'ZGARISH: avval ikkita alohida jadval bor edi
# (dashboard_vision_reports va video_vision_reports) — bu ORTIQCHA edi,
# chunki ikkalasi ham bir xil turdagi ma'lumot (SCADA skrinshotidan
# JSON). Endi BITTA jadval — vision_reports — ishlatiladi, video
# segmentga bog'liq (video_segment_id ixtiyoriy — bo'sh bo'lishi ham
# mumkin, agar kelajakda video'siz alohida capture kerak bo'lsa).
# """

# import psycopg
# from config import DB_CONFIG


# def get_connection():
#     return psycopg.connect(**DB_CONFIG)


# def init_all_tables():
#     """Butun tizim uchun kerakli barcha jadvallarni yaratadi
#     (agar hali mavjud bo'lmasa). Har bir process boshida chaqirilishi
#     kifoya — CREATE TABLE IF NOT EXISTS xavfsiz, xato bermaydi."""
#     conn = get_connection()
#     with conn, conn.cursor() as cur:
#         cur.execute("""
#             CREATE TABLE IF NOT EXISTS video_segments (
#                 id SERIAL PRIMARY KEY,
#                 started_at TIMESTAMP NOT NULL,
#                 ended_at TIMESTAMP,
#                 filepath TEXT
#             )
#         """)
#         cur.execute("""
#             CREATE TABLE IF NOT EXISTS vision_reports (
#                 id SERIAL PRIMARY KEY,
#                 ts TIMESTAMP NOT NULL DEFAULT NOW(),
#                 video_segment_id INTEGER REFERENCES video_segments(id),
#                 model TEXT,
#                 payload JSONB NOT NULL
#             )
#         """)
#         cur.execute("""
#             CREATE TABLE IF NOT EXISTS advisor_insights (
#                 id SERIAL PRIMARY KEY,
#                 ts TIMESTAMP NOT NULL DEFAULT NOW(),
#                 severity TEXT,
#                 summary TEXT,
#                 trend_analysis TEXT,
#                 recommendation TEXT
#             )
#         """)
#     conn.close()


# def save_vision_report(payload: dict, model: str, video_segment_id: int | None = None):
#     """Skrinshotdan olingan JSON tahlilni to'g'ridan-to'g'ri bazaga
#     yozadi. Endi ichki HTTP API orqali emas — bitta process ichida
#     to'g'ridan-to'g'ri yozish tezroq va soddaroq."""
#     import json

#     conn = get_connection()
#     with conn, conn.cursor() as cur:
#         cur.execute(
#             """INSERT INTO vision_reports (video_segment_id, model, payload)
#                VALUES (%s, %s, %s)""",
#             (video_segment_id, model, json.dumps(payload)),
#         )
#     conn.close()










"""
database.py — bazaga ulanish va jadvallarni yaratish.
psycopg (3-versiya) kutubxonasidan foydalanadi.

MUHIM O'ZGARISH: video yozish olib tashlanganligi sabab video_segments
jadvali VA vision_reports.video_segment_id ustuni endi KERAK EMAS.
Endi bor-yo'g'i IKKITA jadval ishlatiladi:
  - vision_reports    -> har bir skrinshotning AI tahlili (xom JSON)
  - advisor_insights  -> AI maslahatchining tarixiy xulosalari

ESKI BAZADAN O'TAYOTGANLAR UCHUN (ixtiyoriy tozalash):
Agar avvalgi versiyadan video_segments jadvali va
vision_reports.video_segment_id ustuni bazangizda hali qolgan bo'lsa,
ular endi ishlatilmaydi va xavfsiz qoldirilishi mumkin. Butunlay olib
tashlamoqchi bo'lsangiz, PostgreSQL'da qo'lda quyidagini bajaring:

    ALTER TABLE vision_reports DROP COLUMN IF EXISTS video_segment_id;
    DROP TABLE IF EXISTS video_segments;
"""

import json

import psycopg
from config import DB_CONFIG


def get_connection():
    return psycopg.connect(**DB_CONFIG)


def init_all_tables():
    """Kerakli ikkita jadvalni yaratadi (agar hali mavjud bo'lmasa)."""
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
            CREATE TABLE IF NOT EXISTS advisor_insights (
                id SERIAL PRIMARY KEY,
                ts TIMESTAMP NOT NULL DEFAULT NOW(),
                severity TEXT,
                summary TEXT,
                trend_analysis TEXT,
                recommendation TEXT
            )
        """)
    conn.close()


def save_vision_report(payload: dict, model: str):
    """Skrinshotdan olingan xom JSON tahlilni to'g'ridan-to'g'ri
    bazaga (vision_reports) yozadi."""
    conn = get_connection()
    with conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO vision_reports (model, payload) VALUES (%s, %s)",
            (model, json.dumps(payload)),
        )
    conn.close()