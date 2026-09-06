"""
capture_pipeline.py — bitta doim ochiq brauzer sahifasidan har
SCREENSHOT_INTERVAL_SECONDS (45s) da skrinshot olib, AI orqali JSON
qilib, to'g'ridan-to'g'ri bazaga (vision_reports + metric_history)
yozadi. Video YO'Q.

MUHIM YANGILIK #1 — ANIQ VAQT: har bir skrinshot uchun uni OLGAN
paytdagi aniq vaqt (`captured_at`) saqlanadi. Bu — AI tahlili
tugagan vaqtdan FARQ QILISHI mumkin (tahlil bir necha soniya yoki
qayta urinishlar bilan bir necha daqiqa davom etishi mumkin). Bazaga
yoziladigan `ts` endi "skrinshot qachon olingan" degani, "tahlil
qachon tugagan" emas — bu SCADA holatini haqiqiy vaqtga to'g'ri
bog'laydi.

MUHIM YANGILIK #2 — SINXRON ADVISOR: har bir skrinshot tahlili
muvaffaqiyatli bazaga yozilgach, DARHOL (shu bitta fon threadda,
ketma-ket) `ai_advisor.run_cycle()` chaqiriladi. Natijada JSON
(xom ma'lumot) va AI xulosasi BIR VAQTDA, bitta sikl ichida tayyor
bo'ladi — endi Advisor o'zining alohida 120 soniyalik timer'ida
emas, balki har 45 soniyalik skrinshot bilan sinxron ishlaydi.

DIQQAT: bu — har 45 soniyada IKKITA AI so'rovi (vision + matn model)
degani, avvalgi (120s'da bittasi) o'rniga. Agar Ollama serveringiz
past unumdorlikka ega bo'lsa, bu ko'proq yuklama va timeout xavfini
oshirishi mumkin.

ORTIQCHA YUKLANISHDAN HIMOYA: agar AI band bo'lsa, navbatda faqat ENG
SO'NGGI skrinshot qoladi — eskirganlari tashlab yuboriladi.
"""

import json
import os
import queue
import threading
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from config import SCADA_URL, SCREENSHOT_INTERVAL_SECONDS, SCREENSHOT_TEMP_DIR, VISION_MODEL
from database import save_vision_report
from vision_toolkit import read_dashboard_with_ai
import ai_advisor

_latest_queue: "queue.Queue[tuple[str, datetime]]" = queue.Queue(maxsize=1)

# Advisor endi ALOHIDA fon threadda ishlaydi — bu darhol qaytadi, worker
# esa bir zumda navbatdagi skrinshotni olishga o'tadi. Lock bir vaqtda
# faqat BITTA Advisor sikli ishlashini kafolatlaydi.
_advisor_lock = threading.Lock()


def _run_advisor_in_background():
    if not _advisor_lock.acquire(blocking=False):
        print("[ADVISOR] Oldingi tahlil hali tugamagan, bu safar o'tkazib yuborildi.")
        return
    try:
        ai_advisor.run_cycle()
    except Exception as e:
        print(f"[ADVISOR][XATO] {e}")
    finally:
        _advisor_lock.release()


def _submit_latest(path: str, captured_at: datetime):
    try:
        old_path, _old_ts = _latest_queue.get_nowait()
        try:
            os.remove(old_path)
        except OSError:
            pass
    except queue.Empty:
        pass
    _latest_queue.put_nowait((path, captured_at))


def _ai_worker_loop():
    while True:
        shot_path, captured_at = _latest_queue.get()
        ts_label = captured_at.strftime("%H:%M:%S")
        try:
            data = read_dashboard_with_ai(shot_path, model=VISION_MODEL)
            print(f"[JSON {ts_label}] Tahlil natijasi (skrinshot olingan vaqt):")
            print(json.dumps(data, ensure_ascii=False, indent=2))

            report_id = save_vision_report(data, model=VISION_MODEL, captured_at=captured_at)
            print(f"[JSON {ts_label}] Bazaga yozildi (id={report_id}).")

            # MUHIM: Advisor endi FON threadda ishga tushiriladi — bu
            # qator darhol qaytadi, worker keyingi skrinshotga o'tadi.
            threading.Thread(
                target=_run_advisor_in_background, daemon=True, name="advisor-async"
            ).start()

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
    print(f"Har {SCREENSHOT_INTERVAL_SECONDS}s da: skrinshot -> AI (vision) -> baza -> "
          f"AI Advisor (matn, sinxron) -> baza.\n")

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
                captured_at = datetime.now()  # aniq skrinshot olingan vaqt
                page.screenshot(path=shot_path)
                _submit_latest(shot_path, captured_at)
            except Exception as e:
                print(f"[CAPTURE][XATO] Skrinshot olishda muammo: {e}")
                raise


if __name__ == "__main__":
    from database import init_all_tables
    init_all_tables()
    main()
