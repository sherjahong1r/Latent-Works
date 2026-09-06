# """
# capture_pipeline.py — (avvalgi video_recorder.py, endi YAGONA oqim)

# Bitta brauzer sahifasi ochiladi va:
#   1) Uzluksiz VIDEO qilib yoziladi (5 daqiqalik segmentlar, .webm) ->
#      video_segments jadvaliga saqlanadi.
#   2) XUDDI SHU sahifadan (ikkinchi brauzer OCHILMAYDI), har
#      SCREENSHOT_INTERVAL_SECONDS (30s) da bir marta skrinshot olinadi,
#      vision LLM orqali JSON qilinadi va TO'G'RIDAN-TO'G'RI (ichki HTTP
#      so'rovsiz) vision_reports jadvaliga yoziladi.

# Bu — avvalgi arxitekturadagi IKKITA parallel oqimni (ai_vision_reporter.py
# + video_recorder.py, ikkalasi ham o'z brauzerini ochib, deyarli bir xil
# ishni takrorlagan) BITTAGA birlashtiradi: bitta brauzer, bitta ma'lumot
# manbai, bitta jadval.

# ARXITEKTURA ESLATMASI: Playwright'ning sync API'si skrinshot olishni
# (page.screenshot()) shu threadning O'ZIDA, tez (sinxron) bajaradi.
# Lekin AI'ga yuborish + JSON qilish + bazaga yozish — bir necha soniya
# cho'zilishi mumkin, shuning uchun bu qism FON THREADGA (ThreadPoolExecutor)
# topshiriladi — video yozish HECH QACHON bloklanmaydi.

# Ishga tushirish (yakka o'zi, sinov uchun): py capture_pipeline.py
# Yoki barchasi bitta jarayonda: py main.py
# """

# import json
# import os
# import time
# from concurrent.futures import ThreadPoolExecutor
# from datetime import datetime
# from pathlib import Path

# from playwright.sync_api import sync_playwright

# from config import (
#     SCADA_URL,
#     VIDEO_OUTPUT_DIR,
#     VIDEO_SEGMENT_SECONDS,
#     SCREENSHOT_INTERVAL_SECONDS,
#     VISION_MODEL,
# )
# from database import get_connection, save_vision_report
# from vision_toolkit import read_dashboard_with_ai

# _ai_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="capture-ai")


# def log_segment_start(started_at: datetime) -> int:
#     conn = get_connection()
#     with conn, conn.cursor() as cur:
#         cur.execute(
#             "INSERT INTO video_segments (started_at) VALUES (%s) RETURNING id",
#             (started_at,),
#         )
#         segment_id = cur.fetchone()[0]
#     conn.close()
#     return segment_id


# def log_segment_end(segment_id: int, ended_at: datetime, filepath: str):
#     conn = get_connection()
#     with conn, conn.cursor() as cur:
#         cur.execute(
#             "UPDATE video_segments SET ended_at = %s, filepath = %s WHERE id = %s",
#             (ended_at, filepath, segment_id),
#         )
#     conn.close()


# def _analyze_and_save(screenshot_path: str, segment_id: int):
#     """FON THREADDA ishlaydi. Skrinshotni AI'ga yuboradi, natijani
#     TO'G'RIDAN-TO'G'RI bazaga yozadi (ichki HTTP so'rovsiz — bitta
#     process ichida bo'lgani uchun bunga hojat yo'q)."""
#     try:
#         data = read_dashboard_with_ai(screenshot_path, model=VISION_MODEL)
#         ts = datetime.now().strftime("%H:%M:%S")
#         print(f"[JSON {ts}] Segment #{segment_id} skrinshotidan tahlil:")
#         print(json.dumps(data, ensure_ascii=False, indent=2))

#         save_vision_report(data, model=VISION_MODEL, video_segment_id=segment_id)
#         print(f"[JSON {ts}] Bazaga yozildi (segment #{segment_id}).")
#     except Exception as e:
#         print(f"[JSON][XATO] Tahlil qilishda muammo: {e}")
#     finally:
#         try:
#             os.remove(screenshot_path)
#         except OSError:
#             pass


# def record_one_segment(output_dir: Path, segment_seconds: int, screenshot_seconds: int):
#     started_at = datetime.now()
#     segment_id = log_segment_start(started_at)

#     with sync_playwright() as p:
#         browser = p.chromium.launch()
#         context = browser.new_context(
#             viewport={"width": 1920, "height": 1080},
#             record_video_dir=str(output_dir),
#             record_video_size={"width": 1920, "height": 1080},
#         )
#         page = context.new_page()
#         page.goto(SCADA_URL, timeout=45000, wait_until="domcontentloaded")

#         print(f"[VIDEO {started_at.strftime('%H:%M:%S')}] Segment #{segment_id} "
#               f"boshlandi ({segment_seconds}s davom etadi, har "
#               f"{screenshot_seconds}s da JSON ham chiqariladi)...")

#         elapsed = 0
#         shot_counter = 0
#         while elapsed < segment_seconds:
#             step = min(screenshot_seconds, segment_seconds - elapsed)
#             time.sleep(step)
#             elapsed += step

#             shot_counter += 1
#             shot_path = str(output_dir / f"segment{segment_id}_shot{shot_counter}.png")
#             try:
#                 page.screenshot(path=shot_path)
#             except Exception as e:
#                 print(f"[JSON][XATO] Skrinshot olishda muammo: {e}")
#                 continue

#             _ai_executor.submit(_analyze_and_save, shot_path, segment_id)

#         video_path_obj = page.video
#         context.close()
#         browser.close()
#         final_path = video_path_obj.path() if video_path_obj else None

#     ended_at = datetime.now()
#     log_segment_end(segment_id, ended_at, str(final_path) if final_path else "")
#     print(f"[VIDEO {ended_at.strftime('%H:%M:%S')}] Segment #{segment_id} "
#           f"tugadi: {final_path}")
#     return final_path


# def main():
#     output_dir = Path(VIDEO_OUTPUT_DIR)
#     output_dir.mkdir(exist_ok=True)

#     print(f"capture_pipeline.py ishga tushdi. Manba: {SCADA_URL}")
#     print(f"  - VIDEO: har segment {VIDEO_SEGMENT_SECONDS}s, "
#           f"fayllar '{output_dir}/' papkasiga (video_segments jadvali).")
#     print(f"  - JSON:  har {SCREENSHOT_INTERVAL_SECONDS}s da skrinshot, "
#           f"model={VISION_MODEL!r} -> vision_reports jadvali.\n")

#     while True:
#         try:
#             record_one_segment(output_dir, VIDEO_SEGMENT_SECONDS, SCREENSHOT_INTERVAL_SECONDS)
#         except Exception as e:
#             print(f"[VIDEO][XATO] Segmentda muammo: {e}")
#             time.sleep(10)


# if __name__ == "__main__":
#     from database import init_all_tables
#     init_all_tables()
#     main()














"""
capture_pipeline.py — VIDEO YO'Q. Faqat: bitta doim ochiq brauzer
sahifasidan har SCREENSHOT_INTERVAL_SECONDS (45s) da skrinshot olib,
AI orqali JSON qilib, to'g'ridan-to'g'ri vision_reports jadvaliga
yozadi.

ORTIQCHA YUKLANISHDAN HIMOYA ("faqat eng so'nggisini tahlil qil"):
Agar AI tahlili (Ollama) 45 soniyadan sekinroq javob bersa, keyingi
skrinshotlar CHEKSIZ NAVBATGA TIQILIB QOLMAYDI. Buning o'rniga:
  - Navbatda HAR DOIM faqat BITTA (eng so'nggi) skrinshot saqlanadi.
  - Agar AI band ekan, yangi skrinshot kelsa — navbatdagi ESKI
    (hali ishlov berilmagan) skrinshot TASHLAB YUBORILADI (o'chiriladi),
    o'rniga yangisi qo'yiladi.
  - AI bo'shashi bilan — navbatda turgan ENG SO'NGGI skrinshotni
    tahlil qiladi va natijani odatdagidek vaqt bilan bazaga yozadi.
Natijada AI hech qachon "eskirgan" holatlarni ketma-ket tahlil qilib
o'tirmaydi — u doim eng dolzarb (real vaqtga eng yaqin) holatni ko'radi.

Ishga tushirish (yakka o'zi, sinov uchun): py capture_pipeline.py
Yoki barchasi bitta jarayonda: py main.py
"""

import json
import os
import queue
import threading
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from config import (
    SCADA_URL,
    SCREENSHOT_INTERVAL_SECONDS,
    SCREENSHOT_TEMP_DIR,
    VISION_MODEL,
)
from database import save_vision_report
from vision_toolkit import read_dashboard_with_ai

# maxsize=1 — navbatda FAQAT bitta (eng so'nggi) skrinshot turishi mumkin.
_latest_queue: "queue.Queue[str]" = queue.Queue(maxsize=1)


def _submit_latest(path: str):
    """Yangi skrinshotni navbatga qo'yadi. Agar navbatda hali ishlov
    berilmagan ESKI skrinshot bo'lsa — uni diskdan o'chirib, o'rniga
    yangisini qo'yadi (eskirgan navbat hech qachon to'planib qolmaydi)."""
    try:
        old_path = _latest_queue.get_nowait()
        try:
            os.remove(old_path)
        except OSError:
            pass
    except queue.Empty:
        pass
    _latest_queue.put_nowait(path)


def _ai_worker_loop():
    """Fon threadda uzluksiz ishlaydi: navbatdan (har doim eng
    so'nggisini) skrinshotni oladi, AI tahlilini qiladi, bazaga yozadi.
    Tahlil tugagach, agar navbatda yana yangiroq skrinshot kutayotgan
    bo'lsa, darhol o'shani oladi."""
    while True:
        shot_path = _latest_queue.get()  # yangisi kelguncha shu yerda kutadi
        try:
            data = read_dashboard_with_ai(shot_path, model=VISION_MODEL)
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"[JSON {ts}] Tahlil natijasi:")
            print(json.dumps(data, ensure_ascii=False, indent=2))

            save_vision_report(data, model=VISION_MODEL)
            print(f"[JSON {ts}] Bazaga yozildi.")
        except Exception as e:
            print(f"[JSON][XATO] Tahlil qilishda muammo: {e}")
        finally:
            try:
                os.remove(shot_path)
            except OSError:
                pass


def main():
    temp_dir = Path(SCREENSHOT_TEMP_DIR)
    temp_dir.mkdir(exist_ok=True)

    print(f"capture_pipeline.py ishga tushdi. Manba: {SCADA_URL}")
    print(f"Har {SCREENSHOT_INTERVAL_SECONDS}s da skrinshot -> AI -> "
          f"vision_reports jadvali. (Video yozish o'chirilgan.)\n")

    worker = threading.Thread(target=_ai_worker_loop, daemon=True, name="ai-worker")
    worker.start()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.goto(SCADA_URL, timeout=45000, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        print("Brauzer sahifasi ochildi va doimiy ochiq turadi.\n")

        shot_counter = 0
        while True:
            time.sleep(SCREENSHOT_INTERVAL_SECONDS)
            shot_counter += 1
            shot_path = str(temp_dir / f"shot_{shot_counter}.png")
            try:
                page.screenshot(path=shot_path)
                _submit_latest(shot_path)
            except Exception as e:
                print(f"[CAPTURE][XATO] Skrinshot olishda muammo: {e}")
                # Sahifa/brauzer buzilgan bo'lishi mumkin — bu xatoni
                # tashqariga chiqarib, main.py orqali butun pipeline
                # qayta ishga tushirilishiga ruxsat beramiz.
                raise


if __name__ == "__main__":
    from database import init_all_tables
    init_all_tables()
    main()