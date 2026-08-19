# """
# main.py — TIZIMNING ASOSIY QUVURI (pipeline). Bitta terminalda,
# BITTA jarayonda quyidagilarni ishga tushiradi:

#   - capture_pipeline.py -> video yozadi + har 30s JSON -> vision_reports
#   - ai_advisor.py        -> har 120s tarixiy tahlil -> advisor_insights
#   - retention_cleanup.py -> kuniga bir marta avtomatik eski ma'lumotlarni
#                              o'chiradi (RETENTION_DAYS, config.py)

# MUHIM: bu faylda VEB-SERVER (FastAPI/uvicorn) YO'Q. Interfeys
# (dashboard) — external_api.py — ATAYLAB ALOHIDA fayl va ALOHIDA
# jarayon sifatida ishga tushiriladi (masalan boshqa terminalda,
# xohlagan vaqtda). Sabab: bular ikki xil vazifa —
#   - main.py = ma'lumot yig'ish va tahlil qilish (doim ishlab turishi
#     kerak, ko'rish uchun emas)
#   - external_api.py = faqat ko'rish/kuzatish uchun interfeys
#     (kerak bo'lganda ochiladi, yopiladi — asosiy jarayonga ta'sir
#     qilmaydi)

# ISHGA TUSHIRISH (asosiy quvur):
#     py main.py

# INTERFEYSNI KO'RISH UCHUN (ALOHIDA, xohlagan vaqtda, boshqa terminalda):
#     py external_api.py
#     -> keyin brauzerda: http://localhost:5001

# TO'XTATISH: CTRL+C
# """

# import threading
# import time

# from database import init_all_tables
# import capture_pipeline
# import ai_advisor
# import retention_cleanup


# def _run_safely(name: str, target):
#     """Har bir fon jarayonni "himoyalangan" holda ishga tushiradi.
#     Kutilmagan xato bilan yiqilib tushsa, 10 soniyadan keyin qayta
#     ishga tushiradi."""
#     while True:
#         try:
#             target()
#         except Exception as e:
#             print(f"\n[MAIN][XATO] '{name}' jarayoni kutilmagan xato bilan "
#                   f"to'xtadi: {e}")
#             print(f"[MAIN] '{name}' 10 soniyadan keyin qayta ishga "
#                   f"tushiriladi...\n")
#             time.sleep(10)


# def _retention_loop():
#     """Kuniga bir marta (config.RETENTION_CHECK_INTERVAL_SECONDS)
#     eski ma'lumotlarni avtomatik tozalaydi. Task Scheduler sozlashga
#     hojat qoldirmaydi — main.py ishlab turar ekan, bu ham ishlaydi."""
#     from config import RETENTION_CHECK_INTERVAL_SECONDS
#     while True:
#         try:
#             retention_cleanup.run_cleanup()
#         except Exception as e:
#             print(f"[MAIN][XATO] Retention tozalashda muammo: {e}")
#         time.sleep(RETENTION_CHECK_INTERVAL_SECONDS)


# def main():
#     print("=" * 64)
#     print("  SCADA AI Monitoring — ASOSIY QUVUR (pipeline)")
#     print("=" * 64)
#     print()

#     init_all_tables()

#     jobs = [
#         ("capture_pipeline", capture_pipeline.main),
#         ("ai_advisor", ai_advisor.main),
#         ("retention_cleanup", _retention_loop),
#     ]

#     threads = []
#     for name, target in jobs:
#         t = threading.Thread(
#             target=_run_safely,
#             args=(name, target),
#             daemon=True,
#             name=name,
#         )
#         t.start()
#         threads.append(t)
#         print(f"[MAIN] '{name}' ishga tushdi.")

#     print()
#     print("Bu terminal — FAQAT ma'lumot yig'ish/tahlil qilish uchun.")
#     print("Interfeysni ko'rish uchun BOSHQA terminalda:")
#     print("    py external_api.py")
#     print("    -> http://localhost:5001")
#     print()
#     print("To'xtatish: CTRL+C")
#     print("-" * 64)

#     # Asosiy thread shu yerda "tirik" turadi, fon threadlar ishlashda
#     # davom etadi. CTRL+C bosilguncha kutadi.
#     try:
#         while True:
#             time.sleep(3600)
#     except KeyboardInterrupt:
#         print("\n[MAIN] To'xtatilmoqda...")


# if __name__ == "__main__":
#     main()












"""
main.py — TIZIMNING ASOSIY QUVURI (pipeline). Bitta terminalda,
BITTA jarayonda quyidagilarni ishga tushiradi:

  - capture_pipeline.py -> har 45s skrinshot+JSON -> vision_reports
  - ai_advisor.py        -> har 120s tarixiy tahlil -> advisor_insights

MUHIM: AVTOMATIK TOZALASH (retention) O'CHIRILGAN. Ma'lumotlar HECH
QACHON avtomatik o'chirilmaydi, bazada doimiy saqlanadi. Agar
kelajakda qo'lda tozalash kerak bo'lsa, alohida terminalda
`py retention_cleanup.py` ishga tushirish mumkin (bu fayl mavjud,
lekin main.py uni endi avtomatik chaqirmaydi).

MUHIM: bu faylda VEB-SERVER (FastAPI/uvicorn) YO'Q. Interfeys
(dashboard) — external_api.py — ATAYLAB ALOHIDA fayl va ALOHIDA
jarayon sifatida ishga tushiriladi (masalan boshqa terminalda,
xohlagan vaqtda). Sabab: bular ikki xil vazifa —
  - main.py = ma'lumot yig'ish va tahlil qilish (doim ishlab turishi
    kerak, ko'rish uchun emas)
  - external_api.py = faqat ko'rish/kuzatish uchun interfeys
    (kerak bo'lganda ochiladi, yopiladi — asosiy jarayonga ta'sir
    qilmaydi)

ISHGA TUSHIRISH (asosiy quvur):
    py main.py

INTERFEYSNI KO'RISH UCHUN (ALOHIDA, xohlagan vaqtda, boshqa terminalda):
    py external_api.py
    -> keyin brauzerda: http://localhost:5001

TO'XTATISH: CTRL+C
"""

import threading
import time

from database import init_all_tables
import capture_pipeline
import ai_advisor


def _run_safely(name: str, target):
    """Har bir fon jarayonni "himoyalangan" holda ishga tushiradi.
    Kutilmagan xato bilan yiqilib tushsa, 10 soniyadan keyin qayta
    ishga tushiradi."""
    while True:
        try:
            target()
        except Exception as e:
            print(f"\n[MAIN][XATO] '{name}' jarayoni kutilmagan xato bilan "
                  f"to'xtadi: {e}")
            print(f"[MAIN] '{name}' 10 soniyadan keyin qayta ishga "
                  f"tushiriladi...\n")
            time.sleep(10)


def main():
    print("=" * 64)
    print("  SCADA AI Monitoring — ASOSIY QUVUR (pipeline)")
    print("=" * 64)
    print()

    init_all_tables()

    jobs = [
        ("capture_pipeline", capture_pipeline.main),
        ("ai_advisor", ai_advisor.main),
    ]

    threads = []
    for name, target in jobs:
        t = threading.Thread(
            target=_run_safely,
            args=(name, target),
            daemon=True,
            name=name,
        )
        t.start()
        threads.append(t)
        print(f"[MAIN] '{name}' ishga tushdi.")

    print()
    print("Bu terminal — FAQAT ma'lumot yig'ish/tahlil qilish uchun.")
    print("Interfeysni ko'rish uchun BOSHQA terminalda:")
    print("    py external_api.py")
    print("    -> http://localhost:5001")
    print()
    print("To'xtatish: CTRL+C")
    print("-" * 64)

    # Asosiy thread shu yerda "tirik" turadi, fon threadlar ishlashda
    # davom etadi. CTRL+C bosilguncha kutadi.
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("\n[MAIN] To'xtatilmoqda...")


if __name__ == "__main__":
    main()