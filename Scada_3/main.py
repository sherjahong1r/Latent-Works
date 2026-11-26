"""
main.py — TIZIMNING ASOSIY QUVURI (pipeline). Bitta terminalda,
BITTA jarayonda quyidagilarni ishga tushiradi:

  - capture_pipeline.py -> har 45s: skrinshot -> JSON -> vision_reports +
                            metric_history -> DARHOL shu yerda ai_advisor.run_cycle()
                            ham chaqiriladi (JSON va xulosa BIR VAQTDA chiqadi)
  - predictor.py          -> 1-15 daqiqa (moslashuvchan) 10/20/30 daqiqalik bashorat -> plant_predictions
  - shift_report.py       -> (agar ENABLE_SHIFT_REPORT=True) har SHIFT_REPORT_INTERVAL_HOURS soatda -> shift_reports

MUHIM: ai_advisor.py ENDI ALOHIDA THREAD SIFATIDA ISHGA TUSHIRILMAYDI —
u capture_pipeline.py ichida, har skrinshot tahlilidan keyin SINXRON
chaqiriladi (`ai_advisor.run_cycle()`). Agar uni eski, mustaqil
120 soniyalik timer rejimida sinamoqchi bo'lsangiz, alohida
`py ai_advisor.py` orqali ishga tushirishingiz mumkin (main.py bilan
BIRGA emas — ikkalasi bir vaqtda ishlasa, advisor ikki marta
chaqiriladigan bo'lib qoladi).

MUHIM: bu faylda VEB-SERVER YO'Q. Interfeys — external_api.py — ALOHIDA
jarayon sifatida, xohlagan vaqtda ishga tushiriladi:

    py main.py             # asosiy quvur (doim ishlab turishi kerak)
    py external_api.py     # interfeys (ixtiyoriy, boshqa terminalda)

PRODUCTION uchun interfeysni quyidagicha ham ishga tushirish mumkin:
    uvicorn external_api:app --host 0.0.0.0 --port 5001

TO'XTATISH: CTRL+C
"""

import threading
import time

from database import init_all_tables
import capture_pipeline
import predictor
import shift_report
from config import ENABLE_SHIFT_REPORT


def _run_safely(name: str, target):
    while True:
        try:
            target()
        except Exception as e:
            print(f"\n[MAIN][XATO] '{name}' jarayoni kutilmagan xato bilan to'xtadi: {e}")
            print(f"[MAIN] '{name}' 10 soniyadan keyin qayta ishga tushiriladi...\n")
            time.sleep(10)


def start_background_threads():
    jobs = [
        ("capture_pipeline", capture_pipeline.main),
        ("predictor", predictor.main),
    ]
    if ENABLE_SHIFT_REPORT:
        jobs.append(("shift_report", shift_report.main))

    threads = []
    for name, target in jobs:
        t = threading.Thread(target=_run_safely, args=(name, target), daemon=True, name=name)
        t.start()
        threads.append(t)
        print(f"[MAIN] '{name}' ishga tushdi.")
    return threads


def main():
    print("=" * 64)
    print("  SCADA AI Monitoring — ASOSIY QUVUR (pipeline)")
    print("=" * 64)
    print()

    init_all_tables()
    start_background_threads()

    print()
    print("Bu terminal — FAQAT ma'lumot yig'ish/tahlil/bashorat uchun.")
    print("Interfeysni ko'rish uchun BOSHQA terminalda:")
    print("    py external_api.py")
    print("    -> http://localhost:5001")
    print()
    print("To'xtatish: CTRL+C")
    print("-" * 64)

    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("\n[MAIN] To'xtatilmoqda...")


if __name__ == "__main__":
    main()
