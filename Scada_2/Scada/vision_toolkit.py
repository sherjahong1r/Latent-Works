# """
# vision_toolkit.py — skrinshot olish va AI (vision LLM) orqali JSON
# qilish funksiyalari. Mustaqil sikli yo'q — capture_pipeline.py buni
# chaqiradi.
# """

# import base64
# import io
# import json
# import time

# import requests
# from PIL import Image

# from config import (
#     CAPTURE_MODE,
#     SCADA_URL,
#     SCADA_WINDOW_TITLE,
#     KNOWN_SENSOR_LABELS,
#     OLLAMA_BASE_URL,
#     VISION_MODEL,
#     MAX_RETRIES,
#     RETRY_DELAY_SECONDS,
#     IMAGE_MAX_WIDTH,
#     IMAGE_JPEG_QUALITY,
#     OLLAMA_TIMEOUT_SECONDS,
# )

# BASE_PROMPT = """Bu — sanoat SCADA/HMI tizimining ekran suratidir (skrinshot).
# Vazifang: rasmda ko'ringan BARCHA o'lchov qiymatlarini, barcha
# uskuna/aktuator holatlarini va barcha alarm/ogohlantirish xabarlarini
# quyidagi JSON formatida chiqarib ber:

# {
#   "readings": {"<ekranda ko'ringan nom>": <son yoki matn>, ...},
#   "equipment_states": {"<uskuna nomi>": "<ON/OFF/OPEN/CLOSED va h.k.>", ...},
#   "alarms": ["<ekranda ko'ringan har bir alarm matni>", ...],
#   "low_confidence_fields": ["<aniq emas deb hisoblagan kalitlar>", ...],
#   "screen_title": "<ekran sarlavhasi, agar ko'ringan bo'lsa>"
# }

# Muhim qoidalar:
# - Faqat rasmda HAQIQATDA ko'ringan narsalarni yoz, o'zingdan hech narsa qo'shma
# - Nomlarni ekranda yozilgan holicha qoldir, tarjima qilma
# - Bo'lim rasmda umuman bo'lmasa, mos maydonni bo'sh qoldir
# - Faqat JSON qaytar, boshqa hech qanday izoh yozma

# === ANALOG STRELKALI ASBOBLAR UCHUN QOIDA ===
# Raqamli yozuv bo'lsa — shunga tayan. Faqat strelka bo'lsa — taxmin qil
# va "low_confidence_fields"ga qo'sh.

# === 7-SEGMENT DISPLEYLAR UCHUN QOIDA ===
# Noaniq raqam bo'lsa — eng ehtimolli variantni yoz va
# "low_confidence_fields"ga qo'sh.

# === RANGLI INDIKATORLAR UCHUN QOIDA ===
# Chiroq holatini "equipment_states"da aniq so'z bilan ifodala (ON/OFF/
# RUNNING/STOPPED). Noaniq bo'lsa "UNKNOWN"."""


# def _build_prompt() -> str:
#     if not KNOWN_SENSOR_LABELS:
#         return BASE_PROMPT
#     mapping_lines = "\n".join(
#         f'- "{label}" ko\'rinsa -> kalit nomi sifatida "{key}" ishlat'
#         for label, key in KNOWN_SENSOR_LABELS.items()
#     )
#     return BASE_PROMPT + "\n\n=== MA'LUM KALIT NOMLARI ===\n" + mapping_lines


# PROMPT = _build_prompt()


# def take_screenshot_from_url(path: str = "shot.png"):
#     from playwright.sync_api import sync_playwright

#     with sync_playwright() as p:
#         browser = p.chromium.launch()
#         page = browser.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=2)
#         page.goto(SCADA_URL, timeout=45000, wait_until="domcontentloaded")
#         try:
#             page.wait_for_load_state("networkidle", timeout=15000)
#         except Exception:
#             pass
#         page.wait_for_timeout(9000)
#         page.screenshot(path=path, full_page=True)
#         browser.close()
#     return path


# def take_screenshot_from_window(path: str = "shot.png"):
#     import win32gui
#     import win32ui
#     from ctypes import windll

#     hwnd_result = {"hwnd": None}

#     def _callback(hwnd, _extra):
#         title = win32gui.GetWindowText(hwnd)
#         if SCADA_WINDOW_TITLE.lower() in title.lower() and win32gui.IsWindowVisible(hwnd):
#             hwnd_result["hwnd"] = hwnd

#     win32gui.EnumWindows(_callback, None)
#     hwnd = hwnd_result["hwnd"]
#     if hwnd is None:
#         raise RuntimeError(f"'{SCADA_WINDOW_TITLE}' oynasi topilmadi.")

#     left, top, right, bottom = win32gui.GetWindowRect(hwnd)
#     width, height = right - left, bottom - top
#     hwnd_dc = win32gui.GetWindowDC(hwnd)
#     mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
#     save_dc = mfc_dc.CreateCompatibleDC()
#     save_bitmap = win32ui.CreateBitmap()
#     save_bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
#     save_dc.SelectObject(save_bitmap)
#     windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 2)
#     bmpinfo = save_bitmap.GetInfo()
#     bmpstr = save_bitmap.GetBitmapBits(True)
#     img = Image.frombuffer("RGB", (bmpinfo["bmWidth"], bmpinfo["bmHeight"]), bmpstr, "raw", "BGRX", 0, 1)
#     win32gui.DeleteObject(save_bitmap.GetHandle())
#     save_dc.DeleteDC()
#     mfc_dc.DeleteDC()
#     win32gui.ReleaseDC(hwnd, hwnd_dc)
#     img.save(path)
#     return path


# def take_screenshot_from_screen(path: str = "shot.png"):
#     import mss
#     with mss.mss() as sct:
#         sct.shot(mon=1, output=path)
#     return path


# def take_screenshot(path: str = "shot.png"):
#     if CAPTURE_MODE == "url":
#         return take_screenshot_from_url(path)
#     elif CAPTURE_MODE == "window":
#         return take_screenshot_from_window(path)
#     elif CAPTURE_MODE == "screen":
#         return take_screenshot_from_screen(path)
#     raise ValueError(f"Noma'lum CAPTURE_MODE: {CAPTURE_MODE}")


# def _compress_image_for_ai(image_path: str) -> str:
#     """Rasmni kichraytiradi + JPEG'ga siqadi -> tezlik uchun. Base64
#     (str) qaytaradi."""
#     with Image.open(image_path) as img:
#         img = img.convert("RGB")
#         if img.width > IMAGE_MAX_WIDTH:
#             ratio = IMAGE_MAX_WIDTH / img.width
#             img = img.resize((IMAGE_MAX_WIDTH, int(img.height * ratio)), Image.LANCZOS)
#         buffer = io.BytesIO()
#         img.save(buffer, format="JPEG", quality=IMAGE_JPEG_QUALITY, optimize=True)
#         return base64.b64encode(buffer.getvalue()).decode("utf-8")


# def read_dashboard_with_ai(image_path: str, model: str = VISION_MODEL) -> dict:
#     b64_image = _compress_image_for_ai(image_path)
#     last_error = None

#     for attempt in range(1, MAX_RETRIES + 1):
#         try:
#             response = requests.post(
#                 f"{OLLAMA_BASE_URL}/api/chat",
#                 headers={"ngrok-skip-browser-warning": "true", "Content-Type": "application/json"},
#                 json={
#                     "model": model,
#                     "messages": [{"role": "user", "content": PROMPT, "images": [b64_image]}],
#                     "stream": False,
#                     "format": "json",
#                     "options": {"temperature": 0},
#                 },
#                 timeout=OLLAMA_TIMEOUT_SECONDS,
#             )
#             response.raise_for_status()
#             raw = response.json()["message"]["content"]
#             return json.loads(raw)
#         except (requests.RequestException, KeyError, json.JSONDecodeError) as e:
#             last_error = e
#             if attempt < MAX_RETRIES:
#                 print(f"[OGOHLANTIRISH] {attempt}-urinish muvaffaqiyatsiz ({e}). "
#                       f"{RETRY_DELAY_SECONDS}s kutib, qayta urinaman ({attempt + 1}/{MAX_RETRIES})...")
#                 time.sleep(RETRY_DELAY_SECONDS)
#             else:
#                 print(f"[XATO] {MAX_RETRIES} marta urinildi, hammasi muvaffaqiyatsiz.")

#     raise last_error













"""
vision_toolkit.py — skrinshot olish va AI (vision LLM) orqali JSON
qilish funksiyalari. Mustaqil sikli yo'q — capture_pipeline.py buni
chaqiradi.
"""

import base64
import io
import json
import time

from PIL import Image

import llm_client
from config import (
    CAPTURE_MODE,
    SCADA_URL,
    SCADA_WINDOW_TITLE,
    KNOWN_SENSOR_LABELS,
    VISION_MODEL,
    VISION_MAX_TOKENS,
    IMAGE_MAX_WIDTH,
    IMAGE_JPEG_QUALITY,
)

BASE_PROMPT = """Bu — sanoat SCADA/HMI tizimining ekran suratidir (skrinshot).
Vazifang: rasmda ko'ringan BARCHA o'lchov qiymatlarini, barcha
uskuna/aktuator holatlarini va barcha alarm/ogohlantirish xabarlarini
quyidagi JSON formatida chiqarib ber:

{
  "readings": {"<ekranda ko'ringan nom>": <son yoki matn>, ...},
  "equipment_states": {"<uskuna nomi>": "<ON/OFF/OPEN/CLOSED va h.k.>", ...},
  "alarms": ["<ekranda ko'ringan har bir alarm matni>", ...],
  "low_confidence_fields": ["<aniq emas deb hisoblagan kalitlar>", ...],
  "screen_title": "<ekran sarlavhasi, agar ko'ringan bo'lsa>"
}

MUHIM QOIDALAR — HAQIQATGA TO'LIQ SODIQLIK:
- FAQAT rasmda HAQIQATDA ko'ringan narsalarni yoz. O'zingdan HECH
  QANDAY qiymat, holat yoki tafsilot O'YLAB TOPMA yoki QO'SHMA —
  hatto mantiqan "shunday bo'lishi kerak" deb tuyulsa ham.
- TO'LIQLIK MUHIM: ekranda ko'ringan BARCHA raqamli ko'rsatkichni,
  BARCHA uskuna/nasos/klapan holatini yoz — birortasini ham
  "keraksiz" deb o'tkazib yuborma. Ekranda nechta alohida
  ko'rsatkich/qiymat ko'rinsa, JSON'da ham shuncha bo'lishi kerak.
- Nomlarni ekranda yozilgan holicha qoldir, tarjima qilma
- Bo'lim rasmda umuman bo'lmasa, mos maydonni bo'sh qoldir
- Faqat JSON qaytar, boshqa hech qanday izoh yozma

=== RAQAMLI QIYMATLAR FORMATI (TEZLIK UCHUN) ===
"readings" ichidagi raqamli qiymatlarni FAQAT SOF SON sifatida yoz —
o'lchov birligi (gal, ft, gpm, %, va h.k.) YOZMA, vergul ham QO'SHMA.
Masalan: "8,800.0 gal" -> 8800.0 (EMAS: "8,800.0 gal"); "75%" -> 75.

=== ANALOG STRELKALI ASBOBLAR UCHUN QOIDA ===
Raqamli yozuv bo'lsa — shunga tayan. Faqat strelka bo'lsa — taxmin qil
va "low_confidence_fields"ga qo'sh.

=== 7-SEGMENT DISPLEYLAR UCHUN QOIDA ===
Noaniq raqam bo'lsa — eng ehtimolli variantni yoz va
"low_confidence_fields"ga qo'sh.

=== RANGLI INDIKATORLAR UCHUN QOIDA ===
Chiroq holatini "equipment_states"da aniq so'z bilan ifodala (ON/OFF/
RUNNING/STOPPED). Noaniq bo'lsa "UNKNOWN" deb yoz va
"low_confidence_fields"ga qo'sh — taxmin qilib to'g'ri/noto'g'ri
javob berishdan ko'ra, halol "noaniq" deyish YAXSHIROQ."""


def _build_prompt() -> str:
    if not KNOWN_SENSOR_LABELS:
        return BASE_PROMPT
    mapping_lines = "\n".join(
        f'- "{label}" ko\'rinsa -> kalit nomi sifatida "{key}" ishlat'
        for label, key in KNOWN_SENSOR_LABELS.items()
    )
    return BASE_PROMPT + "\n\n=== MA'LUM KALIT NOMLARI ===\n" + mapping_lines


PROMPT = _build_prompt()


def take_screenshot_from_url(path: str = "shot.png"):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=2)
        page.goto(SCADA_URL, timeout=45000, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        page.wait_for_timeout(9000)
        page.screenshot(path=path, full_page=True)
        browser.close()
    return path


def take_screenshot_from_window(path: str = "shot.png"):
    import win32gui
    import win32ui
    from ctypes import windll

    hwnd_result = {"hwnd": None}

    def _callback(hwnd, _extra):
        title = win32gui.GetWindowText(hwnd)
        if SCADA_WINDOW_TITLE.lower() in title.lower() and win32gui.IsWindowVisible(hwnd):
            hwnd_result["hwnd"] = hwnd

    win32gui.EnumWindows(_callback, None)
    hwnd = hwnd_result["hwnd"]
    if hwnd is None:
        raise RuntimeError(f"'{SCADA_WINDOW_TITLE}' oynasi topilmadi.")

    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width, height = right - left, bottom - top
    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()
    save_bitmap = win32ui.CreateBitmap()
    save_bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
    save_dc.SelectObject(save_bitmap)
    windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 2)
    bmpinfo = save_bitmap.GetInfo()
    bmpstr = save_bitmap.GetBitmapBits(True)
    img = Image.frombuffer("RGB", (bmpinfo["bmWidth"], bmpinfo["bmHeight"]), bmpstr, "raw", "BGRX", 0, 1)
    win32gui.DeleteObject(save_bitmap.GetHandle())
    save_dc.DeleteDC()
    mfc_dc.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwnd_dc)
    img.save(path)
    return path


def take_screenshot_from_screen(path: str = "shot.png"):
    import mss
    with mss.mss() as sct:
        sct.shot(mon=1, output=path)
    return path


def take_screenshot(path: str = "shot.png"):
    if CAPTURE_MODE == "url":
        return take_screenshot_from_url(path)
    elif CAPTURE_MODE == "window":
        return take_screenshot_from_window(path)
    elif CAPTURE_MODE == "screen":
        return take_screenshot_from_screen(path)
    raise ValueError(f"Noma'lum CAPTURE_MODE: {CAPTURE_MODE}")


def _compress_image_for_ai(image_path: str) -> str:
    """Rasmni kichraytiradi + JPEG'ga siqadi -> tezlik uchun. Base64
    (str) qaytaradi."""
    with Image.open(image_path) as img:
        img = img.convert("RGB")
        if img.width > IMAGE_MAX_WIDTH:
            ratio = IMAGE_MAX_WIDTH / img.width
            img = img.resize((IMAGE_MAX_WIDTH, int(img.height * ratio)), Image.LANCZOS)
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=IMAGE_JPEG_QUALITY, optimize=True)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")


def read_dashboard_with_ai(image_path: str, model: str = VISION_MODEL) -> dict:
    """Skrinshotni AI vision modelga yuboradi, JSON qaytaradi.
    Provider (Ollama/vLLM) tanlash va qayta urinish mantig'i
    llm_client.py ichida — bu funksiya faqat rasmni tayyorlaydi va
    umumiy klientni chaqiradi."""
    b64_image = _compress_image_for_ai(image_path)
    return llm_client.chat_completion(
        model=model, prompt=PROMPT, image_b64=b64_image, json_mode=True,
        max_tokens=VISION_MAX_TOKENS, label="VISION"
    )