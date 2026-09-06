# """
# vision_toolkit.py — (avvalgi ai_vision_reporter.py) skrinshot olish va
# AI (vision LLM) orqali JSON qilish funksiyalari.

# MUHIM O'ZGARISH: bu fayl endi MUSTAQIL SIKLGA (main()/while True) EGA
# EMAS. Sabab: avval bu fayl video_recorder.py'dan mustaqil ravishda,
# o'zi alohida brauzer ochib, alohida 30 soniyalik siklda ishlar edi —
# bu video_recorder.py bilan deyarli bir xil ishni ikki marta, ikkita
# brauzerda takrorlagani uchun ORTIQCHA edi.

# Endi bu fayl faqat "asbob qutisi": skrinshot olish funksiyalari va
# `read_dashboard_with_ai()` — buni faqat capture_pipeline.py (yagona
# video+skrinshot oqimi) chaqiradi.

# Agar kelajakda video'siz, faqat skrinshot kerak bo'lsa (masalan
# CAPTURE_MODE="window" bilan, video ishlamaydigan holatda), shu
# funksiyalarni boshqa skriptdan ham chaqirish mumkin.
# """

# import json
# import time

# import requests

# from config import (
#     CAPTURE_MODE,
#     SCADA_URL,
#     SCADA_WINDOW_TITLE,
#     KNOWN_SENSOR_LABELS,
#     OLLAMA_BASE_URL,
#     VISION_MODEL,
#     MAX_RETRIES,
#     RETRY_DELAY_SECONDS,
# )

# BASE_PROMPT = """Bu — sanoat SCADA/HMI tizimining ekran suratidir (skrinshot).
# Vazifang: rasmda ko'ringan BARCHA o'lchov qiymatlarini (raqamli ko'rsatkichlar:
# harorat, bosim, sath, tezlik va h.k. — nima bo'lsa ham), barcha uskuna/aktuator
# holatlarini (ON/OFF, ochiq/yopiq va h.k.) va barcha alarm/ogohlantirish
# xabarlarini quyidagi JSON formatida chiqarib ber:

# {
#   "readings": {
#     "<ekranda ko'ringan nom, aynan o'zi>": <son yoki matn qiymat>,
#     ...
#   },
#   "equipment_states": {
#     "<uskuna nomi>": "<holati, masalan ON/OFF/OPEN/CLOSED>",
#     ...
#   },
#   "alarms": ["<ekranda ko'ringan har bir alarm/xabar matni>", ...],
#   "low_confidence_fields": ["<qiymati aniq emas deb hisoblagan kalitlar>", ...],
#   "screen_title": "<ekranning sarlavhasi yoki nomi, agar ko'ringan bo'lsa>"
# }

# Muhim qoidalar:
# - Faqat rasmda HAQIQATDA ko'ringan narsalarni yoz, o'zingdan hech narsa qo'shma
# - Nomlarni ekranda yozilgan holicha (o'sha tilda) qoldir, tarjima qilma
# - Agar biror bo'lim rasmda umuman bo'lmasa, mos maydonni bo'sh ({} yoki []) qoldir
# - Faqat JSON qaytar, boshqa hech qanday izoh yoki matn yozma

# === ANALOG STRELKALI ASBOBLAR (dial/gauge) UCHUN QOIDA ===
# Agar bir xil qiymat uchun HAM raqamli/matnli yozuv, HAM analog strelkali
# asbob (doiraviy o'lchagich) mavjud bo'lsa — FAQAT raqamli/matnli yozuvga
# tayan, strelkaga qarab hisoblama.
# Agar FAQAT analog strelkali asbob bo'lib, hech qanday raqam yozilmagan
# bo'lsa — strelka holatiga qarab eng yaqin qiymatni taxmin qil, lekin
# shu kalit nomini albatta "low_confidence_fields" ro'yxatiga ham qo'sh.

# === 7-SEGMENT / RAQAMLI LED DISPLEYLAR UCHUN QOIDA ===
# Bunday displeylarda raqamlar bir-biriga o'xshab ko'rinishi mumkin. Agar
# raqam noaniq/xira bo'lsa, eng ehtimolli variantni yoz, lekin shu
# kalitni ham "low_confidence_fields" ro'yxatiga qo'sh.

# === RANGLI INDIKATOR/HOLAT CHIROQLARI UCHUN QOIDA ===
# Qizil/yashil (yoki boshqa rangli) yonib turgan chiroqlarni "equipment_states"
# ichida aniq holat so'zi bilan ifodala. Ikkala rang ham o'chgan yoki
# noaniq bo'lsa, "UNKNOWN" deb yoz."""


# def _build_prompt() -> str:
#     if not KNOWN_SENSOR_LABELS:
#         return BASE_PROMPT

#     mapping_lines = "\n".join(
#         f'- "{label}" ko\'rinsa -> kalit nomi sifatida "{key}" ishlat'
#         for label, key in KNOWN_SENSOR_LABELS.items()
#     )
#     return (
#         BASE_PROMPT
#         + "\n\n=== MA'LUM KALIT NOMLARI (ULARGA QAT'IY AMAL QIL) ===\n"
#         + mapping_lines
#     )


# PROMPT = _build_prompt()


# def take_screenshot_from_url(path: str = "dashboard_screenshot.png"):
#     """CAPTURE_MODE='url' uchun — mustaqil (video'siz) skrinshot kerak
#     bo'lganda ishlatiladi. Video oqimida esa page.screenshot() to'g'ridan-
#     to'g'ri capture_pipeline.py ichida, mavjud sahifadan olinadi."""
#     from playwright.sync_api import sync_playwright

#     with sync_playwright() as p:
#         browser = p.chromium.launch()
#         page = browser.new_page(
#             viewport={"width": 1920, "height": 1080},
#             device_scale_factor=2,
#         )
#         page.goto(SCADA_URL, timeout=45000, wait_until="domcontentloaded")
#         try:
#             page.wait_for_load_state("networkidle", timeout=15000)
#         except Exception:
#             pass
#         page.wait_for_timeout(9000)
#         page.screenshot(path=path, full_page=True)
#         browser.close()
#     return path


# def take_screenshot_from_window(path: str = "dashboard_screenshot.png"):
#     import win32gui
#     import win32ui
#     from ctypes import windll
#     from PIL import Image

#     hwnd_result = {"hwnd": None}

#     def _callback(hwnd, _extra):
#         title = win32gui.GetWindowText(hwnd)
#         if SCADA_WINDOW_TITLE.lower() in title.lower() and win32gui.IsWindowVisible(hwnd):
#             hwnd_result["hwnd"] = hwnd

#     win32gui.EnumWindows(_callback, None)
#     hwnd = hwnd_result["hwnd"]

#     if hwnd is None:
#         raise RuntimeError(
#             f"Sarlavhasida '{SCADA_WINDOW_TITLE}' bo'lgan oyna topilmadi."
#         )

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
#     img = Image.frombuffer(
#         "RGB", (bmpinfo["bmWidth"], bmpinfo["bmHeight"]),
#         bmpstr, "raw", "BGRX", 0, 1,
#     )

#     win32gui.DeleteObject(save_bitmap.GetHandle())
#     save_dc.DeleteDC()
#     mfc_dc.DeleteDC()
#     win32gui.ReleaseDC(hwnd, hwnd_dc)

#     img.save(path)
#     return path


# def take_screenshot_from_screen(path: str = "dashboard_screenshot.png"):
#     import mss
#     with mss.mss() as sct:
#         sct.shot(mon=1, output=path)
#     return path


# def take_screenshot(path: str = "dashboard_screenshot.png"):
#     if CAPTURE_MODE == "url":
#         return take_screenshot_from_url(path)
#     elif CAPTURE_MODE == "window":
#         return take_screenshot_from_window(path)
#     elif CAPTURE_MODE == "screen":
#         return take_screenshot_from_screen(path)
#     else:
#         raise ValueError(f"Noma'lum CAPTURE_MODE: {CAPTURE_MODE}")


# def read_dashboard_with_ai(image_path: str, model: str = VISION_MODEL) -> dict:
#     """Skrinshot faylini Ollama vision modelga yuboradi, JSON qaytaradi.
#     Vaqtincha muammo bo'lsa, MAX_RETRIES marta qayta urinadi."""
#     import base64

#     with open(image_path, "rb") as f:
#         b64_image = base64.b64encode(f.read()).decode("utf-8")

#     last_error = None
#     for attempt in range(1, MAX_RETRIES + 1):
#         try:
#             response = requests.post(
#                 f"{OLLAMA_BASE_URL}/api/chat",
#                 headers={
#                     "ngrok-skip-browser-warning": "true",
#                     "Content-Type": "application/json",
#                 },
#                 json={
#                     "model": model,
#                     "messages": [
#                         {"role": "user", "content": PROMPT, "images": [b64_image]}
#                     ],
#                     "stream": False,
#                     "format": "json",
#                     "options": {"temperature": 0},
#                 },
#                 timeout=180,
#             )
#             response.raise_for_status()
#             raw = response.json()["message"]["content"]
#             return json.loads(raw)

#         except (requests.RequestException, KeyError, json.JSONDecodeError) as e:
#             last_error = e
#             if attempt < MAX_RETRIES:
#                 print(
#                     f"[OGOHLANTIRISH] {attempt}-urinish muvaffaqiyatsiz "
#                     f"({e}). {RETRY_DELAY_SECONDS} soniyadan keyin qayta "
#                     f"urinaman ({attempt + 1}/{MAX_RETRIES})..."
#                 )
#                 time.sleep(RETRY_DELAY_SECONDS)
#             else:
#                 print(f"[XATO] {MAX_RETRIES} marta urinildi, hammasi muvaffaqiyatsiz.")

#     raise last_error











"""
vision_toolkit.py — (avvalgi ai_vision_reporter.py) skrinshot olish va
AI (vision LLM) orqali JSON qilish funksiyalari.

MUHIM O'ZGARISH: bu fayl endi MUSTAQIL SIKLGA (main()/while True) EGA
EMAS. Sabab: avval bu fayl video_recorder.py'dan mustaqil ravishda,
o'zi alohida brauzer ochib, alohida 30 soniyalik siklda ishlar edi —
bu video_recorder.py bilan deyarli bir xil ishni ikki marta, ikkita
brauzerda takrorlagani uchun ORTIQCHA edi.

Endi bu fayl faqat "asbob qutisi": skrinshot olish funksiyalari va
`read_dashboard_with_ai()` — buni faqat capture_pipeline.py (yagona
video+skrinshot oqimi) chaqiradi.

Agar kelajakda video'siz, faqat skrinshot kerak bo'lsa (masalan
CAPTURE_MODE="window" bilan, video ishlamaydigan holatda), shu
funksiyalarni boshqa skriptdan ham chaqirish mumkin.
"""

import json
import time

import requests

from config import (
    CAPTURE_MODE,
    SCADA_URL,
    SCADA_WINDOW_TITLE,
    KNOWN_SENSOR_LABELS,
    OLLAMA_BASE_URL,
    VISION_MODEL,
    MAX_RETRIES,
    RETRY_DELAY_SECONDS,
    IMAGE_MAX_WIDTH,
    IMAGE_JPEG_QUALITY,
    OLLAMA_TIMEOUT_SECONDS,
)

BASE_PROMPT = """Bu — sanoat SCADA/HMI tizimining ekran suratidir (skrinshot).
Vazifang: rasmda ko'ringan BARCHA o'lchov qiymatlarini (raqamli ko'rsatkichlar:
harorat, bosim, sath, tezlik va h.k. — nima bo'lsa ham), barcha uskuna/aktuator
holatlarini (ON/OFF, ochiq/yopiq va h.k.) va barcha alarm/ogohlantirish
xabarlarini quyidagi JSON formatida chiqarib ber:

{
  "readings": {
    "<ekranda ko'ringan nom, aynan o'zi>": <son yoki matn qiymat>,
    ...
  },
  "equipment_states": {
    "<uskuna nomi>": "<holati, masalan ON/OFF/OPEN/CLOSED>",
    ...
  },
  "alarms": ["<ekranda ko'ringan har bir alarm/xabar matni>", ...],
  "low_confidence_fields": ["<qiymati aniq emas deb hisoblagan kalitlar>", ...],
  "screen_title": "<ekranning sarlavhasi yoki nomi, agar ko'ringan bo'lsa>"
}

Muhim qoidalar:
- Faqat rasmda HAQIQATDA ko'ringan narsalarni yoz, o'zingdan hech narsa qo'shma
- Nomlarni ekranda yozilgan holicha (o'sha tilda) qoldir, tarjima qilma
- Agar biror bo'lim rasmda umuman bo'lmasa, mos maydonni bo'sh ({} yoki []) qoldir
- Faqat JSON qaytar, boshqa hech qanday izoh yoki matn yozma

=== ANALOG STRELKALI ASBOBLAR (dial/gauge) UCHUN QOIDA ===
Agar bir xil qiymat uchun HAM raqamli/matnli yozuv, HAM analog strelkali
asbob (doiraviy o'lchagich) mavjud bo'lsa — FAQAT raqamli/matnli yozuvga
tayan, strelkaga qarab hisoblama.
Agar FAQAT analog strelkali asbob bo'lib, hech qanday raqam yozilmagan
bo'lsa — strelka holatiga qarab eng yaqin qiymatni taxmin qil, lekin
shu kalit nomini albatta "low_confidence_fields" ro'yxatiga ham qo'sh.

=== 7-SEGMENT / RAQAMLI LED DISPLEYLAR UCHUN QOIDA ===
Bunday displeylarda raqamlar bir-biriga o'xshab ko'rinishi mumkin. Agar
raqam noaniq/xira bo'lsa, eng ehtimolli variantni yoz, lekin shu
kalitni ham "low_confidence_fields" ro'yxatiga qo'sh.

=== RANGLI INDIKATOR/HOLAT CHIROQLARI UCHUN QOIDA ===
Qizil/yashil (yoki boshqa rangli) yonib turgan chiroqlarni "equipment_states"
ichida aniq holat so'zi bilan ifodala. Ikkala rang ham o'chgan yoki
noaniq bo'lsa, "UNKNOWN" deb yoz."""


def _build_prompt() -> str:
    if not KNOWN_SENSOR_LABELS:
        return BASE_PROMPT

    mapping_lines = "\n".join(
        f'- "{label}" ko\'rinsa -> kalit nomi sifatida "{key}" ishlat'
        for label, key in KNOWN_SENSOR_LABELS.items()
    )
    return (
        BASE_PROMPT
        + "\n\n=== MA'LUM KALIT NOMLARI (ULARGA QAT'IY AMAL QIL) ===\n"
        + mapping_lines
    )


PROMPT = _build_prompt()


def take_screenshot_from_url(path: str = "dashboard_screenshot.png"):
    """CAPTURE_MODE='url' uchun — mustaqil (video'siz) skrinshot kerak
    bo'lganda ishlatiladi. Video oqimida esa page.screenshot() to'g'ridan-
    to'g'ri capture_pipeline.py ichida, mavjud sahifadan olinadi."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=2,
        )
        page.goto(SCADA_URL, timeout=45000, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        page.wait_for_timeout(9000)
        page.screenshot(path=path, full_page=True)
        browser.close()
    return path


def take_screenshot_from_window(path: str = "dashboard_screenshot.png"):
    import win32gui
    import win32ui
    from ctypes import windll
    from PIL import Image

    hwnd_result = {"hwnd": None}

    def _callback(hwnd, _extra):
        title = win32gui.GetWindowText(hwnd)
        if SCADA_WINDOW_TITLE.lower() in title.lower() and win32gui.IsWindowVisible(hwnd):
            hwnd_result["hwnd"] = hwnd

    win32gui.EnumWindows(_callback, None)
    hwnd = hwnd_result["hwnd"]

    if hwnd is None:
        raise RuntimeError(
            f"Sarlavhasida '{SCADA_WINDOW_TITLE}' bo'lgan oyna topilmadi."
        )

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
    img = Image.frombuffer(
        "RGB", (bmpinfo["bmWidth"], bmpinfo["bmHeight"]),
        bmpstr, "raw", "BGRX", 0, 1,
    )

    win32gui.DeleteObject(save_bitmap.GetHandle())
    save_dc.DeleteDC()
    mfc_dc.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwnd_dc)

    img.save(path)
    return path


def take_screenshot_from_screen(path: str = "dashboard_screenshot.png"):
    import mss
    with mss.mss() as sct:
        sct.shot(mon=1, output=path)
    return path


def take_screenshot(path: str = "dashboard_screenshot.png"):
    if CAPTURE_MODE == "url":
        return take_screenshot_from_url(path)
    elif CAPTURE_MODE == "window":
        return take_screenshot_from_window(path)
    elif CAPTURE_MODE == "screen":
        return take_screenshot_from_screen(path)
    else:
        raise ValueError(f"Noma'lum CAPTURE_MODE: {CAPTURE_MODE}")


def _compress_image_for_ai(image_path: str) -> str:
    """Skrinshotni AI'ga yuborishdan oldin kichraytiradi va JPEG'ga
    siqadi -> tezlik uchun. Katta PNG (masalan 1920x1080, bir necha MB)
    o'rniga kichikroq, siqilgan JPEG yuboriladi -> vision model buni
    ANCHA tezroq qayta ishlaydi, timeout xavfi kamayadi. Matn/raqamlar
    hali ham o'qiladigan aniqlikda qoladi (IMAGE_MAX_WIDTH/QUALITY
    config.py'da sozlanadi).

    Base64 (str) qaytaradi — to'g'ridan-to'g'ri API so'roviga qo'yish
    uchun tayyor holatda."""
    import base64
    import io
    from PIL import Image

    with Image.open(image_path) as img:
        img = img.convert("RGB")

        if img.width > IMAGE_MAX_WIDTH:
            ratio = IMAGE_MAX_WIDTH / img.width
            new_size = (IMAGE_MAX_WIDTH, int(img.height * ratio))
            img = img.resize(new_size, Image.LANCZOS)

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=IMAGE_JPEG_QUALITY, optimize=True)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")


def read_dashboard_with_ai(image_path: str, model: str = VISION_MODEL) -> dict:
    """Skrinshot faylini Ollama vision modelga yuboradi, JSON qaytaradi.
    Yuborishdan oldin rasm siqiladi (tezlik uchun). Vaqtincha muammo
    bo'lsa, MAX_RETRIES marta qayta urinadi."""
    b64_image = _compress_image_for_ai(image_path)

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                headers={
                    "ngrok-skip-browser-warning": "true",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "user", "content": PROMPT, "images": [b64_image]}
                    ],
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0},
                },
                timeout=OLLAMA_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            raw = response.json()["message"]["content"]
            return json.loads(raw)

        except (requests.RequestException, KeyError, json.JSONDecodeError) as e:
            last_error = e
            if attempt < MAX_RETRIES:
                print(
                    f"[OGOHLANTIRISH] {attempt}-urinish muvaffaqiyatsiz "
                    f"({e}). {RETRY_DELAY_SECONDS} soniyadan keyin qayta "
                    f"urinaman ({attempt + 1}/{MAX_RETRIES})..."
                )
                time.sleep(RETRY_DELAY_SECONDS)
            else:
                print(f"[XATO] {MAX_RETRIES} marta urinildi, hammasi muvaffaqiyatsiz.")

    raise last_error