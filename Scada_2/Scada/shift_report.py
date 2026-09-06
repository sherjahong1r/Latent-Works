# """
# shift_report.py — har SHIFT_REPORT_INTERVAL_HOURS soatda (default 12)
# avtomatik smena hisoboti tayyorlaydi: shu davrdagi AI xulosalarini
# jamlab, LLM orqali qisqa, tushunarli hisobot yozadi.

# Ishga tushirish (yakka o'zi): py shift_report.py
# Yoki barchasi bitta jarayonda: py main.py (ENABLE_SHIFT_REPORT=True bo'lsa)
# """

# import json
# import time
# from datetime import datetime, timedelta, timezone

# import requests

# from database import (
#     init_all_tables,
#     get_insights_between,
#     get_last_shift_report_end,
#     save_shift_report,
# )
# from config import (
#     OLLAMA_BASE_URL,
#     OLLAMA_TEXT_MODEL,
#     OLLAMA_TIMEOUT_SECONDS,
#     SHIFT_REPORT_INTERVAL_HOURS,
# )

# SHIFT_PROMPT_TEMPLATE = """Sen sanoat zavodining smena hisobotini tayyorlovchi muhandissan.

# Quyida {period_start} dan {period_end} gacha bo'lgan davrda AI
# maslahatchi yozgan barcha xulosalar ro'yxati berilgan (vaqt bo'yicha
# tartiblangan):

# {insights_json}

# VAZIFANG: shu davr uchun QISQA, TUSHUNARLI smena hisoboti yoz —
# O'ZBEK TILIDA. Quyidagilarni o'z ichiga olsin:
# - Umumiy holat qanday kechdi (asosan normalmi, muammolar bo'ldimi)
# - Eng muhim voqealar/ogohlantirishlar (agar bo'lsa)
# - Operatorlar uchun keyingi smenaga tavsiyalar (agar kerak bo'lsa)

# Javobni FAQAT quyidagi JSON formatida qaytar:

# {{
#   "report": "<butun hisobot matni, bir necha qatorli, O'ZBEK TILIDA>"
# }}

# Agar davr davomida hech qanday muammo bo'lmagan bo'lsa, shuni ham
# qisqa va aniq yoz — bo'sh joyni sun'iy muammo bilan to'ldirma."""


# def build_shift_report(period_start: datetime, period_end: datetime) -> str:
#     insights = get_insights_between(period_start, period_end)

#     if not insights:
#         return "Bu smena davomida AI maslahatchi tomonidan hech qanday xulosa yozilmadi (yetarli ma'lumot bo'lmagan)."

#     insights_for_prompt = [
#         {
#             "ts": i["ts"].isoformat(),
#             "severity": i["severity"],
#             "summary": i["summary"],
#             "recommendation": i["recommendation"],
#         }
#         for i in insights
#     ]

#     prompt = SHIFT_PROMPT_TEMPLATE.format(
#         period_start=period_start.strftime("%Y-%m-%d %H:%M"),
#         period_end=period_end.strftime("%Y-%m-%d %H:%M"),
#         insights_json=json.dumps(insights_for_prompt, ensure_ascii=False, indent=2),
#     )

#     response = requests.post(
#         f"{OLLAMA_BASE_URL}/api/chat",
#         headers={"ngrok-skip-browser-warning": "true", "Content-Type": "application/json"},
#         json={
#             "model": OLLAMA_TEXT_MODEL,
#             "messages": [{"role": "user", "content": prompt}],
#             "stream": False,
#             "format": "json",
#             "options": {"temperature": 0.2},
#         },
#         timeout=OLLAMA_TIMEOUT_SECONDS,
#     )
#     response.raise_for_status()
#     raw = response.json()["message"]["content"]
#     result = json.loads(raw)
#     return result.get("report", "Hisobot matni olinmadi.")


# def main():
#     print(f"shift_report.py ishga tushdi. Har {SHIFT_REPORT_INTERVAL_HOURS} soatda "
#           f"avtomatik smena hisoboti tayyorlaydi.\n")

#     while True:
#         try:
#             last_end = get_last_shift_report_end()
#             period_end = datetime.now(timezone.utc)
#             period_start = last_end if last_end else period_end - timedelta(hours=SHIFT_REPORT_INTERVAL_HOURS)

#             report_text = build_shift_report(period_start, period_end)
#             save_shift_report(period_start, period_end, report_text)

#             ts = datetime.now().strftime("%H:%M:%S")
#             print(f"[SHIFT {ts}] Yangi smena hisoboti saqlandi "
#                   f"({period_start.strftime('%H:%M')} - {period_end.strftime('%H:%M')}).")
#             print(f"  {report_text[:200]}...\n")

#         except Exception as e:
#             print(f"[SHIFT][XATO] Hisobot tayyorlashda muammo: {e}")

#         time.sleep(SHIFT_REPORT_INTERVAL_HOURS * 3600)


# if __name__ == "__main__":
#     init_all_tables()
#     main()






"""
shift_report.py — har SHIFT_REPORT_INTERVAL_HOURS soatda (default 12)
avtomatik smena hisoboti tayyorlaydi: shu davrdagi AI xulosalarini
jamlab, LLM orqali qisqa, tushunarli hisobot yozadi.

Ishga tushirish (yakka o'zi): py shift_report.py
Yoki barchasi bitta jarayonda: py main.py (ENABLE_SHIFT_REPORT=True bo'lsa)
"""

import json
import time
from datetime import datetime, timedelta

import llm_client
from database import (
    init_all_tables,
    get_insights_between,
    get_last_shift_report_end,
    save_shift_report,
)
from config import (
    OLLAMA_TEXT_MODEL,
    SHIFT_REPORT_MAX_TOKENS,
    SHIFT_REPORT_INTERVAL_HOURS,
)

SHIFT_PROMPT_TEMPLATE = """Sen sanoat zavodining smena hisobotini tayyorlovchi muhandissan.

Quyida {period_start} dan {period_end} gacha bo'lgan davrda AI
maslahatchi yozgan barcha xulosalar ro'yxati berilgan (vaqt bo'yicha
tartiblangan):

{insights_json}

VAZIFANG: shu davr uchun QISQA, TUSHUNARLI smena hisoboti yoz —
O'ZBEK TILIDA. Quyidagilarni o'z ichiga olsin:
- Umumiy holat qanday kechdi (asosan normalmi, muammolar bo'ldimi)
- Eng muhim voqealar/ogohlantirishlar (agar bo'lsa)
- Operatorlar uchun keyingi smenaga tavsiyalar (agar kerak bo'lsa)

MUHIM QOIDA — FAQAT YUQORIDAGI RO'YXATGA TAYAN (QAT'IY):
- Hisobotda FAQAT yuqoridagi "summary" va "recommendation" maydonlarida
  aniq YOZILGAN narsalarni jamlab yoz. O'zingdan HECH QANDAY qo'shimcha
  texnik tafsilot, sabab, xatolik turi yoki holatni (masalan tarmoq/
  ulanish holati, jihoz nomi, sensor turi) O'YLAB TOPMA — agar bu
  ro'yxatda aniq zikr etilmagan bo'lsa.
- Bu — rasmiy hisobot, shuning uchun aniqlik haqiqiylikdan muhimroq:
  noaniq narsani "ehtimol" yoki umumiy so'z bilan yoz, aniq (lekin
  noto'g'ri bo'lishi mumkin) tafsilot bilan TO'LDIRMA.

Javobni FAQAT quyidagi JSON formatida qaytar:

{{
  "report": "<butun hisobot matni, bir necha qatorli, O'ZBEK TILIDA>"
}}

Agar davr davomida hech qanday muammo bo'lmagan bo'lsa, shuni ham
qisqa va aniq yoz — bo'sh joyni sun'iy muammo bilan to'ldirma."""


def build_shift_report(period_start: datetime, period_end: datetime) -> str:
    insights = get_insights_between(period_start, period_end)

    if not insights:
        return "Bu smena davomida AI maslahatchi tomonidan hech qanday xulosa yozilmadi (yetarli ma'lumot bo'lmagan)."

    insights_for_prompt = [
        {
            "ts": i["ts"].isoformat(),
            "severity": i["severity"],
            "summary": i["summary"],
            "recommendation": i["recommendation"],
        }
        for i in insights
    ]

    prompt = SHIFT_PROMPT_TEMPLATE.format(
        period_start=period_start.strftime("%Y-%m-%d %H:%M"),
        period_end=period_end.strftime("%Y-%m-%d %H:%M"),
        insights_json=json.dumps(insights_for_prompt, ensure_ascii=False, indent=2),
    )

    result = llm_client.chat_completion(
        model=OLLAMA_TEXT_MODEL, prompt=prompt, json_mode=True,
        max_tokens=SHIFT_REPORT_MAX_TOKENS, label="SHIFT"
    )
    return result.get("report", "Hisobot matni olinmadi.")


def main():
    print(f"shift_report.py ishga tushdi. Har {SHIFT_REPORT_INTERVAL_HOURS} soatda "
          f"avtomatik smena hisoboti tayyorlaydi.\n")

    while True:
        try:
            last_end = get_last_shift_report_end()
            period_end = datetime.now()
            period_start = last_end if last_end else period_end - timedelta(hours=SHIFT_REPORT_INTERVAL_HOURS)

            report_text = build_shift_report(period_start, period_end)
            save_shift_report(period_start, period_end, report_text)

            ts = datetime.now().strftime("%H:%M:%S")
            print(f"[SHIFT {ts}] Yangi smena hisoboti saqlandi "
                  f"({period_start.strftime('%H:%M')} - {period_end.strftime('%H:%M')}).")
            print(f"  {report_text[:200]}...\n")

        except Exception as e:
            print(f"[SHIFT][XATO] Hisobot tayyorlashda muammo: {e}")

        time.sleep(SHIFT_REPORT_INTERVAL_HOURS * 3600)


if __name__ == "__main__":
    init_all_tables()
    main()