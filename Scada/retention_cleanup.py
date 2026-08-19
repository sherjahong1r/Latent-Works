# """
# retention_cleanup.py — bazadagi va diskdagi ESKI ma'lumotlarni o'chiradi.
# RETENTION_DAYS (config.py, default 30 kun) dan eski bo'lgan hamma narsa
# o'chiriladi — natijada har doim faqat OXIRGI 1 OYLIK ma'lumot saqlanadi.

# O'CHIRILADIGAN NARSALAR:
#   - vision_reports jadvalidagi eski qatorlar (JSON hisobotlar)
#   - advisor_insights jadvalidagi eski qatorlar
#   - video_segments jadvalidagi eski qatorlar VA ularga tegishli .webm
#     video fayllar (diskdan ham)
#   - videos/ papkasida qolib ketgan eski .png skrinshotlar (zaxira
#     tozalash — capture_pipeline.py odatda ularni darhol o'chiradi)

# ISHLATISH:

#   1) BIR MARTA (tavsiya etiladi — Windows Task Scheduler orqali
#      kuniga yoki oyiga bir marta avtomatik chaqiring):
#          py retention_cleanup.py

#   2) main.py ichida — bu skript avtomatik, kuniga bir marta fon
#      threadda ishlaydi (main.py qarang), alohida ishga tushirishga
#      hojat yo'q agar main.py orqali butun tizim ishlayotgan bo'lsa.

#   3) Doimiy jarayon sifatida (agar main.py ishlatmasangiz):
#          py retention_cleanup.py --loop
# """

# import sys
# import time
# from datetime import datetime, timedelta
# from pathlib import Path

# from config import (
#     RETENTION_DAYS,
#     RETENTION_CHECK_INTERVAL_SECONDS,
#     VIDEO_OUTPUT_DIR,
# )
# from database import get_connection


# def _cutoff() -> datetime:
#     return datetime.now() - timedelta(days=RETENTION_DAYS)


# def cleanup_vision_reports(cutoff: datetime) -> int:
#     conn = get_connection()
#     with conn, conn.cursor() as cur:
#         cur.execute("DELETE FROM vision_reports WHERE ts < %s", (cutoff,))
#         deleted = cur.rowcount
#     conn.close()
#     return deleted


# def cleanup_advisor_insights(cutoff: datetime) -> int:
#     conn = get_connection()
#     with conn, conn.cursor() as cur:
#         cur.execute("DELETE FROM advisor_insights WHERE ts < %s", (cutoff,))
#         deleted = cur.rowcount
#     conn.close()
#     return deleted


# def cleanup_video_segments(cutoff: datetime) -> tuple[int, int]:
#     conn = get_connection()
#     with conn.cursor() as cur:
#         cur.execute(
#             "SELECT id, filepath FROM video_segments WHERE started_at < %s",
#             (cutoff,),
#         )
#         rows = cur.fetchall()
#     conn.close()

#     deleted_files = 0
#     deleted_rows = 0

#     for segment_id, filepath in rows:
#         if filepath:
#             try:
#                 p = Path(filepath)
#                 if p.exists():
#                     p.unlink()
#                     deleted_files += 1
#             except OSError as e:
#                 print(f"[XATO] Video fayl o'chirilmadi ({filepath}): {e}")

#         conn = get_connection()
#         with conn, conn.cursor() as cur:
#             # vision_reports.video_segment_id FOREIGN KEY bo'lgani uchun
#             # avval bog'liq JSON hisobotlarni tozalaymiz (agar hali
#             # o'chirilmagan bo'lsa), keyin segmentni o'chiramiz.
#             cur.execute("DELETE FROM vision_reports WHERE video_segment_id = %s", (segment_id,))
#             cur.execute("DELETE FROM video_segments WHERE id = %s", (segment_id,))
#         conn.close()
#         deleted_rows += 1

#     return deleted_rows, deleted_files


# def cleanup_leftover_screenshots(cutoff: datetime) -> int:
#     output_dir = Path(VIDEO_OUTPUT_DIR)
#     if not output_dir.exists():
#         return 0

#     deleted = 0
#     cutoff_ts = cutoff.timestamp()
#     for png_file in output_dir.glob("segment*_shot*.png"):
#         try:
#             if png_file.stat().st_mtime < cutoff_ts:
#                 png_file.unlink()
#                 deleted += 1
#         except OSError as e:
#             print(f"[XATO] Skrinshot o'chirilmadi ({png_file}): {e}")
#     return deleted


# def run_cleanup():
#     cutoff = _cutoff()
#     ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#     print(f"[{ts}] Tozalash boshlandi. Chegara: {RETENTION_DAYS} kun "
#           f"({cutoff.strftime('%Y-%m-%d %H:%M')} dan OLDINGI ma'lumotlar o'chiriladi).")

#     n1 = cleanup_vision_reports(cutoff)
#     print(f"  vision_reports   : {n1} qator o'chirildi")

#     n2 = cleanup_advisor_insights(cutoff)
#     print(f"  advisor_insights : {n2} qator o'chirildi")

#     n3_rows, n3_files = cleanup_video_segments(cutoff)
#     print(f"  video_segments   : {n3_rows} qator, {n3_files} video fayl o'chirildi")

#     n4 = cleanup_leftover_screenshots(cutoff)
#     print(f"  qoldiq skrinshotlar: {n4} ta fayl o'chirildi")

#     print("Tozalash tugadi.\n")


# def main():
#     if "--loop" in sys.argv:
#         days = RETENTION_CHECK_INTERVAL_SECONDS / 86400
#         print(f"retention_cleanup.py DOIMIY rejimda ishga tushdi. Har "
#               f"{days:.1f} kunda bir marta tekshiradi, {RETENTION_DAYS} "
#               f"kundan eski ma'lumotlarni o'chiradi.\n")
#         while True:
#             try:
#                 run_cleanup()
#             except Exception as e:
#                 print(f"[XATO] Tozalash siklida muammo: {e}")
#             time.sleep(RETENTION_CHECK_INTERVAL_SECONDS)
#     else:
#         run_cleanup()


# if __name__ == "__main__":
#     main()















"""
retention_cleanup.py — bazadagi ESKI ma'lumotlarni o'chiradi.
RETENTION_DAYS (config.py, default 30 kun) dan eski bo'lgan hamma
narsa o'chiriladi — natijada har doim faqat OXIRGI 1 OYLIK ma'lumot
saqlanadi.

MUHIM O'ZGARISH: video yozish olib tashlanganligi sabab, endi faqat
IKKITA jadval tozalanadi:
  - vision_reports    (xom JSON hisobotlar)
  - advisor_insights  (AI xulosalari)

ISHLATISH:
  1) BIR MARTA (tavsiya etiladi — Windows Task Scheduler orqali
     kuniga yoki oyiga bir marta avtomatik chaqiring):
         py retention_cleanup.py

  2) main.py ichida — bu skript avtomatik, kuniga bir marta fon
     threadda ishlaydi, alohida ishga tushirishga hojat yo'q.

  3) Doimiy jarayon sifatida (agar main.py ishlatmasangiz):
         py retention_cleanup.py --loop
"""

import sys
import time
from datetime import datetime, timedelta

from config import RETENTION_DAYS, RETENTION_CHECK_INTERVAL_SECONDS
from database import get_connection


def _cutoff() -> datetime:
    return datetime.now() - timedelta(days=RETENTION_DAYS)


def cleanup_vision_reports(cutoff: datetime) -> int:
    conn = get_connection()
    with conn, conn.cursor() as cur:
        cur.execute("DELETE FROM vision_reports WHERE ts < %s", (cutoff,))
        deleted = cur.rowcount
    conn.close()
    return deleted


def cleanup_advisor_insights(cutoff: datetime) -> int:
    conn = get_connection()
    with conn, conn.cursor() as cur:
        cur.execute("DELETE FROM advisor_insights WHERE ts < %s", (cutoff,))
        deleted = cur.rowcount
    conn.close()
    return deleted


def run_cleanup():
    cutoff = _cutoff()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] Tozalash boshlandi. Chegara: {RETENTION_DAYS} kun "
          f"({cutoff.strftime('%Y-%m-%d %H:%M')} dan OLDINGI ma'lumotlar o'chiriladi).")

    n1 = cleanup_vision_reports(cutoff)
    print(f"  vision_reports   : {n1} qator o'chirildi")

    n2 = cleanup_advisor_insights(cutoff)
    print(f"  advisor_insights : {n2} qator o'chirildi")

    print("Tozalash tugadi.\n")


def main():
    if "--loop" in sys.argv:
        days = RETENTION_CHECK_INTERVAL_SECONDS / 86400
        print(f"retention_cleanup.py DOIMIY rejimda ishga tushdi. Har "
              f"{days:.1f} kunda bir marta tekshiradi, {RETENTION_DAYS} "
              f"kundan eski ma'lumotlarni o'chiradi.\n")
        while True:
            try:
                run_cleanup()
            except Exception as e:
                print(f"[XATO] Tozalash siklida muammo: {e}")
            time.sleep(RETENTION_CHECK_INTERVAL_SECONDS)
    else:
        run_cleanup()


if __name__ == "__main__":
    main()