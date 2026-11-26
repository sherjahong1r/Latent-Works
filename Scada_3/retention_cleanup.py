# """
# retention_cleanup.py — bazadagi ESKI ma'lumotlarni o'chiradi (QO'LDA
# ishga tushiriladi — main.py buni AVTOMATIK chaqirmaydi, ma'lumotlar
# default holatda cheksiz saqlanadi).

# ISHLATISH:
#     py retention_cleanup.py            # bir marta
#     py retention_cleanup.py --loop     # doimiy (har kuni tekshiradi)
# """

# import sys
# import time
# from datetime import datetime, timedelta

# from config import RETENTION_DAYS, RETENTION_CHECK_INTERVAL_SECONDS
# from database import get_connection


# def _cutoff() -> datetime:
#     return datetime.now() - timedelta(days=RETENTION_DAYS)


# def _delete_from(table: str, cutoff: datetime) -> int:
#     conn = get_connection()
#     with conn, conn.cursor() as cur:
#         cur.execute(f"DELETE FROM {table} WHERE ts < %s", (cutoff,))
#         deleted = cur.rowcount
#     conn.close()
#     return deleted


# def run_cleanup():
#     cutoff = _cutoff()
#     ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#     print(f"[{ts}] Tozalash boshlandi. Chegara: {RETENTION_DAYS} kun.")

#     for table in ["metric_history", "vision_reports", "advisor_insights",
#                   "plant_predictions", "shift_reports"]:
#         n = _delete_from(table, cutoff)
#         print(f"  {table:<20}: {n} qator o'chirildi")

#     print("Tozalash tugadi.\n")


# def main():
#     if "--loop" in sys.argv:
#         days = RETENTION_CHECK_INTERVAL_SECONDS / 86400
#         print(f"retention_cleanup.py DOIMIY rejimda. Har {days:.1f} kunda tekshiradi.\n")
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
