# """
# ai_advisor.py — ikkinchi AI qatlami: matn LLM yordamida vision_reports
# jadvalidagi tarixiy hisobotlarni tahlil qilib, XULOSA + TENDENSIYA +
# TAVSIYA yozadi (o'zbek tilida). Bazaga advisor_insights jadvaliga
# yozadi.

# MUHIM O'ZGARISH: endi dashboard_vision_reports EMAS, balki BITTA
# birlashtirilgan vision_reports jadvalidan o'qiydi (chunki endi faqat
# bitta capture oqimi bor — capture_pipeline.py).

# Ishga tushirish (yakka o'zi): py ai_advisor.py
# Yoki barchasi bitta jarayonda: py main.py
# """

# import json
# import time
# from datetime import datetime

# import requests

# from database import get_connection, init_all_tables
# from config import (
#     OLLAMA_BASE_URL,
#     OLLAMA_TEXT_MODEL,
#     ADVISOR_CYCLE_SECONDS,
#     ADVISOR_HISTORY_LIMIT,
# )

# ADVISOR_PROMPT_TEMPLATE = """Sen sanoat SCADA tizimini kuzatuvchi tajribali muhandis-maslahatchisan.

# Quyida vaqt bo'yicha tartiblangan (eng eskisidan eng yangisigacha) SCADA
# hisobotlari tarixi berilgan:

# {history_json}

# VAZIFANG:
# 1. Ushbu tarixni tahlil qil — qaysi qiymatlar g'ayrioddiy, barqaror
#    o'sayotgan yoki xavfli tendentsiyaga ega ekanini top.
# 2. Agar avval biror muammoli holat bo'lgan va u davom etgan/qaytarilgan
#    bo'lsa — buni ANIQ vaqt bilan ko'rsatib ta'kidla.
# 3. Hozirgi (eng oxirgi) holat qanchalik jiddiy ekanini bahola.
# 4. Operator uchun ANIQ, AMALIY tavsiya yoz.

# MUHIM TIL QOIDASI: "severity" maydoni FAQAT quyidagi uchta inglizcha
# so'zdan biri bo'lishi shart: NORMAL, WARNING yoki CRITICAL. "summary",
# "trend_analysis" va "recommendation" maydonlari esa FAQAT O'ZBEK
# TILIDA, tabiiy va tushunarli uslubda yozilishi shart — bironta ham
# inglizcha gap aralashtirmang.

# Javobni FAQAT quyidagi JSON formatida qaytar, boshqa hech narsa yozma:

# {{
#   "severity": "<NORMAL yoki WARNING yoki CRITICAL>",
#   "summary": "<vaziyatning 1-2 gapli qisqa tavsifi — O'ZBEK TILIDA>",
#   "trend_analysis": "<tarixiy tendentsiya haqida topilma — O'ZBEK TILIDA>",
#   "recommendation": "<operator uchun aniq, amaliy tavsiya — O'ZBEK TILIDA>"
# }}

# Agar hammasi normal bo'lsa, "severity": "NORMAL" deb yoz va shunga mos
# qisqa xulosa ber — xavf yo'q joyda sun'iy xavf o'ylab topma."""


# def fetch_recent_reports(limit: int) -> list:
#     """vision_reports jadvalidan oxirgi `limit` ta hisobotni o'qiydi."""
#     conn = get_connection()
#     with conn.cursor() as cur:
#         cur.execute(
#             "SELECT ts, payload FROM vision_reports ORDER BY id DESC LIMIT %s",
#             (limit,),
#         )
#         rows = cur.fetchall()
#     conn.close()
#     rows = list(reversed(rows))   # eng eskisidan eng yangisigacha
#     return [{"ts": r[0].isoformat(), "data": r[1]} for r in rows]


# def ask_advisor(history: list) -> dict:
#     history_json = json.dumps(history, ensure_ascii=False, indent=2)
#     prompt = ADVISOR_PROMPT_TEMPLATE.format(history_json=history_json)

#     response = requests.post(
#         f"{OLLAMA_BASE_URL}/api/chat",
#         headers={
#             "ngrok-skip-browser-warning": "true",
#             "Content-Type": "application/json",
#         },
#         json={
#             "model": OLLAMA_TEXT_MODEL,
#             "messages": [{"role": "user", "content": prompt}],
#             "stream": False,
#             "format": "json",
#             "options": {"temperature": 0.2},
#         },
#         timeout=180,
#     )
#     response.raise_for_status()
#     raw = response.json()["message"]["content"]
#     return json.loads(raw)


# def save_insight(insight: dict):
#     conn = get_connection()
#     with conn, conn.cursor() as cur:
#         cur.execute(
#             """INSERT INTO advisor_insights (severity, summary, trend_analysis, recommendation)
#                VALUES (%s, %s, %s, %s)""",
#             (
#                 insight.get("severity", "UNKNOWN"),
#                 insight.get("summary", ""),
#                 insight.get("trend_analysis", ""),
#                 insight.get("recommendation", ""),
#             ),
#         )
#     conn.close()


# def main():
#     print(f"AI advisor ishga tushdi. Model: {OLLAMA_TEXT_MODEL!r}. "
#           f"Har {ADVISOR_CYCLE_SECONDS}s, oxirgi {ADVISOR_HISTORY_LIMIT} "
#           f"hisobotni tahlil qiladi.")

#     while True:
#         try:
#             history = fetch_recent_reports(ADVISOR_HISTORY_LIMIT)

#             if len(history) < 2:
#                 print("Tahlil uchun yetarli tarix yo'q, kutilmoqda...")
#             else:
#                 insight = ask_advisor(history)
#                 save_insight(insight)

#                 ts = datetime.now().strftime("%H:%M:%S")
#                 print(f"\n[{ts}] XULOSA ({insight.get('severity')}):")
#                 print(f"  {insight.get('summary')}")
#                 if insight.get("trend_analysis"):
#                     print(f"  Tendentsiya: {insight.get('trend_analysis')}")
#                 if insight.get("recommendation"):
#                     print(f"  Tavsiya: {insight.get('recommendation')}")

#         except Exception as e:
#             print(f"[XATO] Advisor siklida muammo: {e}")

#         time.sleep(ADVISOR_CYCLE_SECONDS)


# if __name__ == "__main__":
#     init_all_tables()
#     main()









"""
ai_advisor.py — ikkinchi AI qatlami: matn LLM yordamida vision_reports
jadvalidagi tarixiy hisobotlarni tahlil qilib, XULOSA + TENDENSIYA +
TAVSIYA yozadi (o'zbek tilida). Bazaga advisor_insights jadvaliga
yozadi.

MUHIM O'ZGARISH: endi dashboard_vision_reports EMAS, balki BITTA
birlashtirilgan vision_reports jadvalidan o'qiydi (chunki endi faqat
bitta capture oqimi bor — capture_pipeline.py).

Ishga tushirish (yakka o'zi): py ai_advisor.py
Yoki barchasi bitta jarayonda: py main.py
"""

import json
import time
from datetime import datetime

import requests

from database import get_connection, init_all_tables
from config import (
    OLLAMA_BASE_URL,
    OLLAMA_TEXT_MODEL,
    OLLAMA_TIMEOUT_SECONDS,
    ADVISOR_CYCLE_SECONDS,
    ADVISOR_HISTORY_LIMIT,
)

ADVISOR_PROMPT_TEMPLATE = """Sen sanoat SCADA tizimini kuzatuvchi tajribali muhandis-maslahatchisan.

Quyida vaqt bo'yicha tartiblangan (eng eskisidan eng yangisigacha) SCADA
hisobotlari tarixi berilgan:

{history_json}

VAZIFANG:
1. Ushbu tarixni tahlil qil — qaysi qiymatlar g'ayrioddiy, barqaror
   o'sayotgan yoki xavfli tendentsiyaga ega ekanini top.
2. Agar avval biror muammoli holat bo'lgan va u davom etgan/qaytarilgan
   bo'lsa — buni ANIQ vaqt bilan ko'rsatib ta'kidla.
3. Hozirgi (eng oxirgi) holat qanchalik jiddiy ekanini bahola.
4. Operator uchun ANIQ, AMALIY tavsiya yoz.

MUHIM TIL QOIDASI: "severity" maydoni FAQAT quyidagi uchta inglizcha
so'zdan biri bo'lishi shart: NORMAL, WARNING yoki CRITICAL. "summary",
"trend_analysis" va "recommendation" maydonlari esa FAQAT O'ZBEK
TILIDA, tabiiy va tushunarli uslubda yozilishi shart — bironta ham
inglizcha gap aralashtirmang.

Javobni FAQAT quyidagi JSON formatida qaytar, boshqa hech narsa yozma:

{{
  "severity": "<NORMAL yoki WARNING yoki CRITICAL>",
  "summary": "<vaziyatning 1-2 gapli qisqa tavsifi — O'ZBEK TILIDA>",
  "trend_analysis": "<tarixiy tendentsiya haqida topilma — O'ZBEK TILIDA>",
  "recommendation": "<operator uchun aniq, amaliy tavsiya — O'ZBEK TILIDA>"
}}

Agar hammasi normal bo'lsa, "severity": "NORMAL" deb yoz va shunga mos
qisqa xulosa ber — xavf yo'q joyda sun'iy xavf o'ylab topma."""


def fetch_recent_reports(limit: int) -> list:
    """vision_reports jadvalidan oxirgi `limit` ta hisobotni o'qiydi."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT ts, payload FROM vision_reports ORDER BY id DESC LIMIT %s",
            (limit,),
        )
        rows = cur.fetchall()
    conn.close()
    rows = list(reversed(rows))   # eng eskisidan eng yangisigacha
    return [{"ts": r[0].isoformat(), "data": r[1]} for r in rows]


def ask_advisor(history: list) -> dict:
    history_json = json.dumps(history, ensure_ascii=False, indent=2)
    prompt = ADVISOR_PROMPT_TEMPLATE.format(history_json=history_json)

    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        headers={
            "ngrok-skip-browser-warning": "true",
            "Content-Type": "application/json",
        },
        json={
            "model": OLLAMA_TEXT_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.2},
        },
        timeout=OLLAMA_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    raw = response.json()["message"]["content"]
    return json.loads(raw)


def save_insight(insight: dict):
    conn = get_connection()
    with conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO advisor_insights (severity, summary, trend_analysis, recommendation)
               VALUES (%s, %s, %s, %s)""",
            (
                insight.get("severity", "UNKNOWN"),
                insight.get("summary", ""),
                insight.get("trend_analysis", ""),
                insight.get("recommendation", ""),
            ),
        )
    conn.close()


def main():
    print(f"AI advisor ishga tushdi. Model: {OLLAMA_TEXT_MODEL!r}. "
          f"Har {ADVISOR_CYCLE_SECONDS}s, oxirgi {ADVISOR_HISTORY_LIMIT} "
          f"hisobotni tahlil qiladi.")

    while True:
        try:
            history = fetch_recent_reports(ADVISOR_HISTORY_LIMIT)

            if len(history) < 2:
                print("Tahlil uchun yetarli tarix yo'q, kutilmoqda...")
            else:
                insight = ask_advisor(history)
                save_insight(insight)

                ts = datetime.now().strftime("%H:%M:%S")
                print(f"\n[{ts}] XULOSA ({insight.get('severity')}):")
                print(f"  {insight.get('summary')}")
                if insight.get("trend_analysis"):
                    print(f"  Tendentsiya: {insight.get('trend_analysis')}")
                if insight.get("recommendation"):
                    print(f"  Tavsiya: {insight.get('recommendation')}")

        except Exception as e:
            print(f"[XATO] Advisor siklida muammo: {e}")

        time.sleep(ADVISOR_CYCLE_SECONDS)


if __name__ == "__main__":
    init_all_tables()
    main()