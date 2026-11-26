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
import re
import time
from concurrent.futures import ThreadPoolExecutor

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
    VISION_MODE,
    VISION_GRID,
    VISION_GRID_OVERLAP,
    VISION_TILES,
    VISION_MAX_TILES,
    VISION_LAYOUT_REFRESH_CYCLES,
    VISION_REGIONS,
    VISION_REGION_JPEG_QUALITY,
    VISION_REGION_MAX_TOKENS,
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


# =====================================================================
# ============  BO'LAKLARGA BO'LIB, PARALLEL O'QISH  ==================
# =====================================================================
# Butun ekranni bitta so'rovda o'qish ikki jihatdan yomon:
#   1) rasm 960 px ga kichraytirilganda zich ekrandagi raqamlar buziladi;
#   2) model 60+ qiymatni bitta uzun javobda yozadi — vaqtning katta
#      qismi aynan yozishga ketadi (~23 belgi/s).
# Bo'laklarga bo'lish ikkalasini ham hal qiladi: kesim kichraytirilmaydi
# (raqam ~2 barobar ko'p pikselga ega) va har bir so'rov javobning
# uchdan birini yozadi. Uchalasi PARALLEL ketadi — server buni ko'taradi.
#
# JSON o'rniga satrli ("R|nom|son") format ishlatiladi: u ~30% kamroq
# belgi, demak shuncha tezroq. Natija baribir o'sha dict ko'rinishida
# qaytariladi — quvurning qolgan qismi o'zgarishsiz ishlayveradi.

COMPACT_PROMPT = """Bu sanoat SCADA ekranining {qism}. Unda ko'ringan HAR BIR
raqamli qiymatni va HAR BIR uskuna holatini chiqar.

=== TO'LIQLIK — ENG MUHIM TALAB ===
Rasmni yuqoridan pastga, chapdan o'ngga BLOK-BLOK ko'zdan kechir.
Har bir ramka/panel ichidagi HAMMA qatorni yoz. Bitta panelda 4 ta
qiymat bo'lsa, to'rttasini ham yoz — birortasini "keraksiz" deb
o'tkazib yuborma. Ekranda nechta alohida ko'rsatkich ko'rinsa,
javobda ham shuncha satr bo'lishi kerak. Ro'yxatni yarim yo'lda
to'xtatma.

=== HAQIQATGA SODIQLIK ===
Faqat rasmda HAQIQATDA ko'ringanini yoz. O'zingdan son o'ylab topma.
Aniq o'qiy olmasang, o'sha satrni umuman tashlab ket — taxmin qilma.

=== FORMAT ===
Har bir satr alohida. Boshqa hech qanday matn, izoh yoki sarlavha YOZMA:
R|<nom>|<sof son>|<birlik>
E|<uskuna nomi>|<holat>
A|<alarm matni>
H|<jadval nomi>|<1-ustun sarlavhasi>|<2-ustun sarlavhasi>|...
D|<1-ustun katagi>|<2-ustun katagi>|...

R — alohida raqamli qiymat. Sonni vergulsiz yoz ("8,800.0" -> 8800.0).
    Birlikni ekrandagidek 4-maydonga yoz: ft, gal, gpm, %, psi, °C,
    mg/L, KGal, MGal, rpm, kW va h.k. Birlik ko'rinmasa 4-maydon bo'sh:
    R|Speed|1450|
E — uskuna holati: On/Off/Running/Stopped/Open/Closed/Auto/Manual,
    ekranda qanday yozilgan bo'lsa shunday.
    Agar bir xil turdagi bir nechta uskuna (nasoslar, klapanlar)
    bir-biridan RANGI yoki ko'rinishi bilan FARQ qilsa, ular bir xil
    holatda EMAS — farqni aks ettir. Qaysi rang qaysi holatni
    bildirishiga ishonching bo'lmasa, o'sha uskunani yozma.
A — alarm. Alarm bo'lmasa, A satrini umuman yozma.
H va D — JADVAL. FAQAT ekranda ustun sarlavhalari HAQIQATDA YOZILGAN
    jadval uchun. Avval bitta H satri: ekrandagi BARCHA ustun
    sarlavhalari, birinchi ustundan boshlab (qator nomlari ustuni
    ham). Keyin har bir qator uchun D satri. Nomni har katakda
    QAYTARMA — vaqt tejaladi. D satrida kataklar soni H dagi
    sarlavhalar soniga TENG bo'lsin, tartibi ham bir xil. Katakda son
    bo'lsa — sonni vergulsiz, ekrandagi birligi bilan yoz (9.5 ft,
    40 %, 857); matn bo'lsa (Auto, Running, On) — matnning o'zi.
    Bo'sh katak — "-". Jadvalning BARCHA ustunlari va BARCHA
    qatorlarini yoz.
    Ustun sarlavhalari ekranda YO'Q bo'lsa — sarlavha O'YLAB TOPMA,
    H/D ishlatma: har bir qiymatni R yoki E satri bilan, birligi
    bilan yoz.

=== MISOLLAR (boshqa ekrandan, faqat formatni ko'rsatish uchun) ===
Jadval:
    H|Compressors|Unit|Mode|Status|Pressure bar|Temp °C
    D|C-1|Auto|Running|7.2|64.5
    D|C-2|Manual|Stopped|0|21.0
Bitta nom yonida BIR NECHTA qiymat bo'lsa — HAR BIRI alohida R satri,
o'z birligi bilan:
    "Silo 2    14.5 m    62 %"     ->  R|Silo 2|14.5|m
                                       R|Silo 2|62|%
O'z yozuvi bor qiymat:
    "Line Pressure   4.1 bar"      ->  R|Line Pressure|4.1|bar
Yozuvsiz qiymat (panel ichidagi qator) — panel sarlavhasini nomga ol:
    "Boiler 3" panelida "182 °C"   ->  R|Boiler 3|182|°C
Faqat raqam bilan belgilangan uskunalar — panel nomini qo'sh:
    "Feed Pumps" panelidagi 1, 2   ->  E|Feed Pump 1|On
                                       E|Feed Pump 2|Off   ("E|1|On" EMAS)

=== YOZILMAYDIGAN NARSALAR ===
Navigatsiya menyusi bo'limlari, sahifa nomlari, tugmalar (Login,
Settings, Theme va h.k.), brauzer manzil qatori, grafik o'qlaridagi
shkala raqamlari va sanalar — bular o'lchov ham, uskuna ham EMAS.
Ularni yozma.

=== NOM QO'YISH ===
Nomni EKRANDA YOZILGANIDEK ko'chir — TARJIMA QILMA, qisqartirma,
o'zingdan so'z qo'shma. Shu qoidalar tufayli bitta ekran ikki marta
o'qilganda nomlar BIR XIL chiqadi. Nomsiz qiymatni TASHLAB KETMA —
yuqoridagi usul bilan nomla."""


def _encode_pil(img: Image.Image, quality: int) -> str:
    """PIL rasmni JPEG+base64 qiladi. Kesim KICHRAYTIRILMAYDI — aniqlik
    aynan shundan kelib chiqadi."""
    buffer = io.BytesIO()
    img.convert("RGB").save(buffer, format="JPEG", quality=quality, optimize=True)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def _unwrap_text(raw) -> str:
    """llm_client json_mode=False da javobni {"text": ...} ichiga o'raydi."""
    if isinstance(raw, dict):
        return raw.get("text") or json.dumps(raw, ensure_ascii=False)
    return str(raw)


# "0 gpm", "0.0 KGal", "75" — bular NOM emas, QIYMAT. Model ba'zan
# ustunlarni chalkashtirib, qiymatni nom o'rniga qo'yadi.
_QIYMATSIMON = re.compile(r"^[\d.,\s]+[A-Za-z%°\"']{0,6}$")
# "1", "#3", "2." — bular uskuna nomi emas. Ekran panelida nasoslar
# tagida faqat raqam yozilgan bo'ladi; model goh to'g'ri nom bilan
# ("Raw Water Pump 1"), goh yalang raqam bilan qaytaradi. Yalang
# raqam operatorga ham, AI maslahatchiga ham hech narsa bermaydi.
_RAQAMLI_NOM = re.compile(r"^[\d\s#.\-]+$")


_BOSH_SON = re.compile(r"^-?[\d.,]+")


def _nom_qiymatning_ozimi(nom: str, qiymat: float) -> bool:
    """Nom raqamdan boshlanib, o'sha raqam QIYMATNING O'ZI bo'lsa,
    model ustunlarni chalkashtirgan: "R|19.6 in LOH|19.6".

    Bu tekshiruv birlik ro'yxatiga TAYANMAYDI, shuning uchun istalgan
    dashboardda ishlaydi. Haqiqiy nom zarar ko'rmaydi:
    "24\" Flow gpm" qiymati 1786 — 24 bilan teng emas, demak qoladi."""
    m = _BOSH_SON.match(nom)
    if not m:
        return False
    try:
        bosh = float(m.group(0).rstrip(".,").replace(",", ""))
    except ValueError:
        return False
    if abs(bosh - qiymat) < 1e-9:
        return True
    return qiymat != 0 and abs(bosh - qiymat) / abs(qiymat) < 1e-6


def _raqamlar(v: float) -> str:
    """75.0 -> '75', 51.8 -> '518' — faqat ahamiyatli raqamlar."""
    return re.sub(r"\D", "", f"{v:g}").lstrip("0") or "0"


def _qiymatlarni_birlashtir(eski: dict, yangi: dict) -> int:
    """Bo'lak natijasini umumiy natijaga qo'shadi. Ikki bo'lak bitta
    nomga TURLI son bersa, ulardan biri qiymatni chegarada kesilgan holda
    ko'rgan bo'lishi mumkin: bo'lak chegarasi "51.8" yozuvining
    o'rtasidan o'tsa, qo'shni bo'lak "1.8" ni o'qiydi. Kesilgan son
    to'liqning OXIRI bo'ladi va kamroq raqamga ega — to'liqini qoldiramiz.
    Qaytaradi: nechta ziddiyat hal qilindi."""
    hal = 0
    for k, v in yangi.items():
        if k not in eski or eski[k] == v:
            eski[k] = v
            continue
        a, b = _raqamlar(eski[k]), _raqamlar(v)
        if len(b) > len(a) and b.endswith(a):
            eski[k] = v                      # eskisi kesilgan edi
            hal += 1
        elif len(a) > len(b) and a.endswith(b):
            hal += 1                         # yangisi kesilgan — eskisi qoladi
        else:
            eski[k] = v                      # haqiqiy farq: oxirgi o'qish
    return hal


def _kesilgan_kalitlarni_tashla(d: dict) -> dict:
    """Bo'lak chegarasi yozuvni o'rtasidan kessa, ustma-ust tushgan
    chiziqda yarim nom ko'rinadi: "Basin #3" yonida "asin #3" paydo
    bo'ladi. Qiymati bir xil va nomi ikkinchisining ichiga so'z
    o'rtasidan kirib ketgan kalit — kesilgani, tashlanadi.

    So'z chegarasidagi qo'shimchaga TEGILMAYDI: "Filter #1 in" va
    "Filter #1 in LOH" — ikkalasi ham haqiqiy, chunki ular orasida
    bo'sh joy bor."""
    uzunidan = sorted(d, key=len, reverse=True)
    natija = {}
    for k in uzunidan:
        kesilgan = False
        for t in natija:
            if len(k) >= len(t) or d[k] != natija[t]:
                continue
            # chapdan kesilgan:  "asin #3" <- "Basin #3"
            if t.endswith(k) and t[len(t) - len(k) - 1] != " ":
                kesilgan = True
            # o'ngdan kesilgan:  "Basin #" <- "Basin #3"
            elif t.startswith(k) and t[len(k)] != " ":
                kesilgan = True
            if kesilgan:
                break
        if not kesilgan:
            natija[k] = d[k]
    return natija


# son + ixtiyoriy birlik: "8,800.0 gal", "75%", "1,584.1 mL / min", "67.7 °F"
_SON_KATAK = re.compile(r"^(-?[\d,]*\.?\d+)\s*([A-Za-z%°µ³²/.\s]{0,14})$")
# Jadvaldagi "holat" ustuni: qiymati alohida kalitsiz, uskunaning o'z
# nomiga yoziladi ("Filter 1" = Running) — oddiy E satri bilan bir xil.
_HOLAT_USTUNLARI = {"status", "state", "holat", "condition"}


def _son_birlik(matn: str) -> tuple[float, str] | None:
    """'8,800.0 gal' -> (8800.0, 'gal'); '75%' -> (75.0, '%'). Son
    bo'lmasa None."""
    m = _SON_KATAK.match(matn.strip())
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "")), _birlik_norm(m.group(2))
    except ValueError:
        return None


def _birlik_norm(birlik: str) -> str:
    """'mL / min' va 'mL/min' bitta birlik — nom ham bitta bo'lsin,
    aks holda bitta o'lchov ikki xil time-series ga bo'linadi."""
    b = " ".join(birlik.split())
    return re.sub(r"\s*/\s*", "/", b)


def _son(matn: str) -> float | None:
    sb = _son_birlik(matn)
    return sb[0] if sb else None


def _birlik_bilan(nom: str, birlik: str) -> str:
    """Birlikni nomga qo'shadi: ("Silo 2", "%") -> "Silo 2 %".

    Nega: bitta nom yonida bir nechta qiymat bo'lsa (sath ft da va %
    da), birliksiz ikkalasi BITTA kalitga tushib, bir-birini almashtirib
    turardi — time-series 14 -> 58 -> 14 bo'lib sakrardi."""
    birlik = _birlik_norm(birlik)
    if not birlik or nom.lower().endswith(birlik.lower()):
        return nom
    return f"{nom} {birlik}"


def _qator_nomi(birinchi_sarlavha: str, jadval: str, belgi: str) -> str:
    """Jadval qatorining nomi. Qator belgisi faqat raqam bo'lsa ("1",
    "#3"), ustun sarlavhasini oldiga qo'shamiz: "Filter" + "1"."""
    belgi = belgi.strip()
    if _RAQAMLI_NOM.match(belgi):
        old = birinchi_sarlavha.strip().rstrip(":").strip() or jadval.strip()
        return f"{old} {belgi.lstrip('#').strip()}".strip()
    return belgi


def parse_compact(text: str) -> dict:
    """Model javobini dict ga aylantiradi. Satr turlari:
        R|nom|son|birlik   E|nom|holat   A|matn
        H|jadval|sarlavha1|sarlavha2|...   D|katak1|katak2|...
    Format buzilgan satr jimgina tashlab yuboriladi — bitta xato satr
    butun o'qishni yo'qotmasligi uchun."""
    readings, equipment, alarms = {}, {}, []
    jadval, sarlavhalar = "", []

    def qiymat_qosh(nom, qiymat):
        if _QIYMATSIMON.match(nom) or _nom_qiymatning_ozimi(nom, qiymat):
            return
        readings[nom] = qiymat

    def holat_qosh(nom, holat):
        if not nom or _RAQAMLI_NOM.match(nom):
            return
        # Notanish dashboardlarda model ba'zan tugma yoki yorliqning
        # O'ZINI holat deb qaytaradi: "E|BMS|BMS". Bu shovqin.
        if holat and holat.strip().lower() != nom.strip().lower():
            equipment[nom] = holat

    for line in text.replace("\\n", "\n").splitlines():
        line = line.strip().strip('"').strip()
        # "Influent:" -> "Influent" — yorliq oxiridagi ikki nuqta nomga kirmasin
        parts = [p.strip().rstrip(":").strip() for p in line.split("|")]
        tur = parts[0].upper() if parts else ""

        if tur == "R" and len(parts) >= 3 and parts[1]:
            qiymat = _son(parts[2])
            if qiymat is not None:
                birlik = parts[3] if len(parts) >= 4 else ""
                qiymat_qosh(_birlik_bilan(parts[1], birlik), qiymat)

        elif tur == "E" and len(parts) >= 3:
            holat_qosh(parts[1], parts[2])

        elif tur == "A":
            txt = line[2:].strip()
            if txt:
                alarms.append(txt)

        elif tur == "H" and len(parts) >= 3:
            jadval, sarlavhalar = parts[1], parts[2:]

        elif tur == "D" and sarlavhalar and len(parts) >= 3:
            kataklar = parts[1:]
            ustunlar = sarlavhalar
            # Model ba'zan qator nomlari ustunining sarlavhasini yozmaydi:
            # H|Tanks|Level|%  +  D|Clearwell|9.5|40 — birinchi katak nom.
            if len(kataklar) == len(sarlavhalar) + 1:
                ustunlar = [""] + sarlavhalar
            # Boshqa nomuvofiqlikda ustunlar siljigan bo'lishi mumkin —
            # qiymat noto'g'ri nomga tushadi. Bunday qatorni tashlaymiz.
            elif len(kataklar) != len(sarlavhalar):
                continue
            qator = _qator_nomi(ustunlar[0], jadval, kataklar[0])
            if not qator:
                continue
            qatordagi_nomlar = set()
            for j, (sarlavha, katak) in enumerate(zip(ustunlar[1:], kataklar[1:]), 1):
                sarlavha = sarlavha.rstrip(":").strip()
                if not katak or katak == "-":
                    continue
                sb = _son_birlik(katak)
                if sb is not None:
                    qiymat, birlik = sb
                    # Nom qo'yish tartibi — BARQARORLIK uchun:
                    #  1) katakda ekrandagi birlik bo'lsa — birlikdan:
                    #     "Silo 2 m". Birlik ekranda yozilgan, model uni
                    #     o'ylab topa olmaydi; sarlavhasiz panelda model
                    #     goh "Level", goh "Value" deb sarlavha to'qiydi,
                    #     birlik esa har safar bir xil. R satri ham xuddi
                    #     shu nomni beradi ("R|Silo 2|14.5|m").
                    #  2) shu qatorda bu nom band bo'lsa (bir xil birlikli
                    #     ikki ustun) — sarlavha + birlik;
                    #  3) birlik yo'q — sarlavhadan; u ham yo'q — tartib raqami.
                    if birlik and sarlavha and birlik.lower() in sarlavha.lower():
                        # sarlavhaning o'zi birlikni aytadi: "Inlet °C"
                        nom = f"{qator} {sarlavha}"
                    elif birlik:
                        nom = _birlik_bilan(qator, birlik)
                        if nom in qatordagi_nomlar and sarlavha:
                            nom = _birlik_bilan(f"{qator} {sarlavha}", birlik)
                    else:
                        nom = f"{qator} {sarlavha or f'#{j}'}"
                    qatordagi_nomlar.add(nom)
                    qiymat_qosh(nom.strip(), qiymat)
                elif sarlavha.lower() in _HOLAT_USTUNLARI or not sarlavha:
                    holat_qosh(qator, katak)
                else:
                    holat_qosh(f"{qator} {sarlavha}".strip(), katak)

    return {"readings": readings, "equipment_states": equipment, "alarms": alarms,
            # bo'lakda jadval bo'lgan — moslashuv uni o'rtasidan kesmasligi kerak
            "_jadval": bool(jadval)}


def _read_one_region(args):
    name, box, image_path = args
    with Image.open(image_path) as full:
        crop = full.crop(box)
        b64 = _encode_pil(crop, VISION_REGION_JPEG_QUALITY)
        size = crop.size
    started = time.monotonic()
    raw = llm_client.chat_completion(
        model=VISION_MODEL, prompt=COMPACT_PROMPT.format(qism=f"{name} qismi"),
        image_b64=b64, json_mode=False, max_tokens=VISION_REGION_MAX_TOKENS,
        label=f"VISION-{name}",
    )
    part = parse_compact(_unwrap_text(raw))
    return name, size, time.monotonic() - started, part


def _find_gap(profile, target: int, search: int) -> int:
    """`target` atrofidagi `search` piksel ichidan ENG BO'SH joyni topadi.

    `profile` — har bir ustun (yoki qator) bo'ylab "to'ldirilganlik"
    o'lchovi. Panel ichi to'la, panellar orasi bo'sh bo'ladi — shuning
    uchun eng past nuqta aynan panellar orasidagi oraliqqa to'g'ri keladi.
    """
    lo = max(1, target - search)
    hi = min(len(profile) - 1, target + search)
    if hi <= lo:
        return target
    window = profile[lo:hi]
    return lo + int(window.index(min(window)))


def _content_profiles(img):
    """Rasmning ustun va qator bo'yicha "to'ldirilganlik" profillarini
    qaytaradi. Qo'shni piksellar farqi olinadi: bir xil rangli fon 0 ga
    yaqin, matn va ramkalar yuqori qiymat beradi."""
    import numpy as np
    small = img.convert("L")
    a = np.asarray(small, dtype=np.int16)
    dx = np.abs(np.diff(a, axis=1))
    dy = np.abs(np.diff(a, axis=0))
    col = np.zeros(a.shape[1], dtype=np.float64)
    col[:dx.shape[1]] = dx.sum(axis=0)
    row = np.zeros(a.shape[0], dtype=np.float64)
    row[:dy.shape[0]] = dy.sum(axis=1)
    # silliqlash — bitta ingichka chiziq "bo'sh joy" deb tanlanmasligi uchun
    k = max(3, min(a.shape[1], a.shape[0]) // 100)
    ker = np.ones(k) / k
    col = np.convolve(col, ker, mode="same")
    row = np.convolve(row, ker, mode="same")
    return col.tolist(), row.tolist()


def build_smart_regions(image_path: str) -> list:
    """Ekranni MAZMUNGA QARAB bo'laklarga bo'ladi.

    Ko'r panjara panellarni o'rtasidan kesib o'tadi: qiymat o'z nomidan
    ajralib qoladi yoki ikki bo'lakda ikki xil nom bilan o'qiladi.
    O'lchangan farq (shot_8, bir xil server sharoitida):
        ko'r panjara   -> 133 s, 94.7% aniqlik, 93% barqarorlik
        qo'lda sozlash ->  84 s, 98.2% aniqlik, 100% barqarorlik
    Bu funksiya qo'lda sozlashning foydasini koordinatasiz beradi:
    kesim joyi rasmning o'zidan, panellar orasidagi bo'sh oraliqdan
    topiladi. Shuning uchun ISTALGAN SCADA/HMI ekranida ishlaydi.
    """
    cols, rows = VISION_GRID
    cols, rows = max(1, cols), max(1, rows)
    with Image.open(image_path) as img:
        width, height = img.size
        col_p, row_p = _content_profiles(img)

    # Kesim joylari: teng bo'linish nuqtasi atrofida eng bo'sh joy
    xs = [0]
    for c in range(1, cols):
        t = int(c * width / cols)
        xs.append(_find_gap(col_p, t, int(width / cols * 0.22)))
    xs.append(width)
    ys = [0]
    for r in range(1, rows):
        t = int(r * height / rows)
        ys.append(_find_gap(row_p, t, int(height / rows * 0.22)))
    ys.append(height)

    ow = int(width / cols * VISION_GRID_OVERLAP)
    oh = int(height / rows * VISION_GRID_OVERLAP)
    regions = []
    for r in range(rows):
        for c in range(cols):
            x1 = max(0, xs[c] - (ow if c else 0))
            y1 = max(0, ys[r] - (oh if r else 0))
            x2 = min(width, xs[c + 1] + (ow if c < cols - 1 else 0))
            y2 = min(height, ys[r + 1] + (oh if r < rows - 1 else 0))
            name = f"{r + 1}-qator {c + 1}-ustun" if rows > 1 else f"{c + 1}-ustun"
            regions.append((name, (x1, y1, x2, y2)))
    return regions


def _ink_map(img, max_side: int = 900):
    """Har bir piksel atrofidagi "tafsilot" (matn, ramka) xaritasi,
    tezlik uchun kichraytirilgan holda. Bir tekis fon ~0 beradi."""
    import numpy as np
    k = max(1.0, max(img.size) / max_side)
    small = img.convert("L").resize((max(1, int(img.width / k)), max(1, int(img.height / k))))
    a = np.asarray(small, dtype=np.float32)
    ink = np.zeros_like(a)
    ink[:, 1:] += np.abs(np.diff(a, axis=1))
    ink[1:, :] += np.abs(np.diff(a, axis=0))
    # Siqish shovqini va yengil fon gradientlarini olib tashlaymiz
    ink[ink < 12] = 0
    return ink, k


def _past_oraliqlar(prof, min_kenglik: int) -> list:
    """Profilning past (deyarli bo'sh) qismlari: [(boshi, oxiri), ...].
    "Past" — profil minimumiga yaqin. Sarlavha qatori yoki yon menyu
    butun ekran bo'ylab o'tib, bo'sh joyga ham doimiy qiymat qo'shadi,
    shuning uchun nolga emas, eng past darajaga nisbatan o'lchanadi."""
    import numpy as np
    p5, med = np.percentile(prof, 5), np.median(prof)
    past = (prof - p5) / max(med - p5, 1e-6) <= 0.3
    out, i, n = [], 0, len(prof)
    while i < n:
        if not past[i]:
            i += 1
            continue
        j = i
        while j < n and past[j]:
            j += 1
        if j - i >= min_kenglik and i > 0 and j < n:
            out.append((i, j))
        i = j
    return out


def _best_cut(ink, box, ruxsat_qopol: bool):
    """`box` (kichik xaritada) uchun eng yaxshi kesim: (bahosi, o'q, joyi, toza).

    TOZA kesim — panellar orasidagi keng bo'sh oraliqdan, bo'lakni butun
    bo'yi bo'ylab kesib o'tadi (85 % dan ko'pi bo'sh). Jadval ichida
    bunday oraliq yo'q (qatorlar chegara chiziqlari bilan ajralgan),
    shuning uchun jadval hech qachon sarlavhasidan ajratilmaydi.

    QO'POL kesim — toza oraliq yo'q bo'lsa (masalan quvurlar hamma
    joydan o'tgan sxema), eng kam to'siqli chiziqdan. Faqat `ruxsat_qopol`
    bo'lsa: bo'lak umumiy mazmunning katta qismini egallagan bo'lsa."""
    import numpy as np
    x1, y1, x2, y2 = box
    part = ink[y1:y2, x1:x2]
    total = part.sum()
    if total <= 0:
        return None
    best = None
    for axis in (0, 1):                      # 0: vertikal kesim (x), 1: gorizontal (y)
        prof = part.sum(axis=axis)
        n = len(prof)
        if n < 40:
            continue
        cum = np.cumsum(prof) / total
        for a, b in _past_oraliqlar(prof, max(4, n // 100)):
            # oraliq bo'ylab qatlam: har bir nuqtada oraliqning butun
            # qalinligi bo'yicha qaraladi
            band = part[:, a:b] if axis == 0 else part[a:b, :].T
            # (1) oraliq bo'ylab nechta joyda biror narsa (matn, quvur) bor
            tosiq = (band.max(axis=1) > 30).mean()
            # (2) oraliqni TO'LIQ kesib o'tgan chiziqlar soni. Baland
            # katakli jadvalda matn ostida bo'sh joy bo'ladi, lekin uni
            # katak chegaralari kesib o'tadi; panellar orasidagi haqiqiy
            # oraliqni esa hech narsa (yoki 1-2 quvur) kesib o'tmaydi.
            kesadi = band.min(axis=1) > 12
            chiziqlar = int(np.count_nonzero(np.diff(kesadi.astype(np.int8)) == 1) + kesadi[0])
            if tosiq > 0.15 or chiziqlar >= 3:
                continue
            i = (a + b) // 2
            if not (0.1 < cum[i] < 0.9):
                continue
            cost = abs(cum[i] - 0.5)
            if best is None or cost < best[0]:
                best = (cost, axis, i, True)
    if best or not ruxsat_qopol:
        return best

    # Qo'pol kesim: uzun tomon bo'ylab, o'rtadagi 40 % ichida eng bo'sh joy
    axis = 0 if (x2 - x1) >= (y2 - y1) else 1
    prof = part.sum(axis=axis)
    n = len(prof)
    if n < 40:
        return None
    k = max(3, n // 60)
    smooth = np.convolve(prof, np.ones(k) / k, mode="same")
    lo, hi = int(n * 0.3), int(n * 0.7)
    i = lo + int(np.argmin(smooth[lo:hi]))
    return (1.0, axis, i, False)


def build_balanced_regions(image_path: str, tiles: int | None = None) -> list:
    """Ekranni MAZMUN HAJMIGA qarab `tiles` ta bo'lakka bo'ladi.

    Nega: bo'laklar parallel o'qiladi va umumiy vaqtni ENG SEKIN bo'lak
    belgilaydi; sekinlik esa model yozadigan matn uzunligiga bog'liq.
    Teng geometrik panjarada zich panel (masalan 9x4 jadval) bitta
    bo'lakka tushib qolardi: o'lchangan — 4 bo'lakdan biri 66 s, qolgani
    13-32 s. Bu yerda har safar ENG ZICH bo'lak panellar orasidagi bo'sh
    joydan ikkiga bo'linadi — natijada har bir so'rov taxminan teng ish
    oladi. Koordinata yozilmaydi, istalgan dashboardda ishlaydi."""
    tiles = max(1, tiles or VISION_TILES)
    with Image.open(image_path) as img:
        width, height = img.size
        ink, k = _ink_map(img)
    h, w = ink.shape
    jami = ink.sum() or 1.0
    # har bir bo'lak: [x1, y1, x2, y2, chap, yuqori, o'ng, past] — oxirgi
    # to'rttasi shu tomonda qo'pol kesim bo'lganini bildiradi (kengroq
    # ustma-ustlik kerak: kesim biror yozuvni ikkiga bo'lgan bo'lishi mumkin)
    boxes = [(0, 0, w, h, False, False, False, False)]
    yopiq = set()                            # bo'linmaydigan (yaxlit panel) bo'laklar
    while len(boxes) < tiles:
        nomzod = sorted((b for b in boxes if b not in yopiq),
                        key=lambda b: ink[b[1]:b[3], b[0]:b[2]].sum(), reverse=True)
        if not nomzod:
            break
        box = nomzod[0]
        ulush = ink[box[1]:box[3], box[0]:box[2]].sum() / jami
        cut = _best_cut(ink, box[:4], ruxsat_qopol=ulush > 0.4)
        if cut is None:
            yopiq.add(box)
            continue
        _, axis, i, toza = cut
        x1, y1, x2, y2, cl, ct, cr, cb = box
        q = not toza
        boxes.remove(box)
        if axis == 0:
            boxes += [(x1, y1, x1 + i, y2, cl, ct, q, cb), (x1 + i, y1, x2, y2, q, ct, cr, cb)]
        else:
            boxes += [(x1, y1, x2, y1 + i, cl, ct, cr, q), (x1, y1 + i, x2, y2, cl, q, cr, cb)]

    # O'qish tartibi: yuqoridan pastga, chapdan o'ngga
    boxes.sort(key=lambda b: (b[1] // max(1, h // 6), b[0]))
    toza_x, toza_y = int(width * 0.01), int(height * 0.01)
    qopol_x, qopol_y = int(width * VISION_GRID_OVERLAP), int(height * VISION_GRID_OVERLAP)
    regions = []
    for n, (x1, y1, x2, y2, cl, ct, cr, cb) in enumerate(boxes, 1):
        X1 = max(0, int(x1 * k) - (qopol_x if cl else toza_x))
        Y1 = max(0, int(y1 * k) - (qopol_y if ct else toza_y))
        X2 = min(width, int(x2 * k) + (qopol_x if cr else toza_x))
        Y2 = min(height, int(y2 * k) + (qopol_y if cb else toza_y))
        regions.append((f"bo'lak {n}", (X1, Y1, X2, Y2)))
    return regions


def build_grid_regions(width: int, height: int) -> list:
    """Ekranni AVTOMATIK panjara bo'yicha bo'laklarga bo'ladi.

    Koordinata yozish shart emas — shuning uchun bu usul ISTALGAN SCADA
    yoki HMI ekranida ishlaydi: boshqa zavod, boshqa dizayn, boshqa
    o'lcham bo'lsa ham. Qo'lda yozilgan VISION_REGIONS faqat bitta aniq
    ekranga mos keladi va boshqasiga o'tganda mutlaqo yaroqsiz bo'ladi.

    Bo'laklar biroz ustma-ust kesiladi: chegarada turgan panel ikkiga
    bo'linib, qiymati o'z nomidan ajralib qolmasligi uchun.
    """
    cols, rows = VISION_GRID
    cols = max(1, cols)
    rows = max(1, rows)
    ow = int(width / cols * VISION_GRID_OVERLAP)
    oh = int(height / rows * VISION_GRID_OVERLAP)
    regions = []
    for r in range(rows):
        for c in range(cols):
            x1 = max(0, int(c * width / cols) - (ow if c else 0))
            y1 = max(0, int(r * height / rows) - (oh if r else 0))
            x2 = min(width, int((c + 1) * width / cols) + (ow if c < cols - 1 else 0))
            y2 = min(height, int((r + 1) * height / rows) + (oh if r < rows - 1 else 0))
            name = f"{r + 1}-qator {c + 1}-ustun" if rows > 1 else f"{c + 1}-ustun"
            regions.append((name, (x1, y1, x2, y2)))
    return regions


# Joriy bo'linish. Quvur bitta ekranni qayta-qayta o'qiydi, shuning
# uchun bo'linish har safar noldan qurilmaydi — o'lchangan vaqtlarga
# qarab sekin bo'lak keyingi siklda ikkiga bo'linadi (_moslash).
_LAYOUT = {"size": None, "regions": None, "cycles": 0}


def _resolve_regions(image_path: str) -> list:
    """Qaysi bo'laklar ishlatilishini hal qiladi: qo'lda yozilganlarmi
    yoki avtomatik (mazmunga qarab, o'lchovlar bilan moslashgan)."""
    if VISION_MODE == "regions" and VISION_REGIONS:
        return list(VISION_REGIONS)
    with Image.open(image_path) as img:
        size = img.size
    if (_LAYOUT["regions"] is None or _LAYOUT["size"] != size
            or _LAYOUT["cycles"] >= VISION_LAYOUT_REFRESH_CYCLES):
        # Ekran o'lchami o'zgarsa yoki ko'p sikl o'tsa — operator boshqa
        # sahifaga o'tgan bo'lishi mumkin, bo'linish qaytadan quriladi.
        try:
            regions = build_balanced_regions(image_path)
        except Exception as e:
            # Mazmunga qarab bo'lish ishlamasa (masalan numpy yo'q),
            # oddiy panjaraga qaytamiz — quvur to'xtamasin.
            print(f"   [VISION] Mazmunli bo'lish ishlamadi ({e}), oddiy panjara.")
            regions = build_grid_regions(*size)
        _LAYOUT.update(size=size, regions=regions, cycles=0)
    _LAYOUT["cycles"] += 1
    return list(_LAYOUT["regions"])


def _ikkiga_bol(image_path: str, box: tuple, jadval_bor: bool) -> list | None:
    """Bo'lakni ikkiga bo'ladi. Avval TOZA oraliq (panellar orasi)
    qidiriladi. Topilmasa — qo'pol kesim, lekin FAQAT bo'lakda jadval
    bo'lmasa: jadvalni o'rtasidan kesish qator nomlarini qiymatlardan
    ajratadi (o'lchangan: Filters jadvali kesilganda 60 qiymatdan 41 tasi
    qoldi, "853" o'rniga "8.5" o'qilib, soxta CRITICAL ogohlantirish
    chiqdi). Alohida yozuvli sxemada esa kesilgan qiymat qo'shni bo'lakda
    to'liq ko'rinadi va _qiymatlarni_birlashtir uni tuzatadi."""
    x1, y1, x2, y2 = box
    with Image.open(image_path) as img:
        ink, k = _ink_map(img.crop(box), max_side=600)
    h, w = ink.shape
    cut = _best_cut(ink, (0, 0, w, h), ruxsat_qopol=not jadval_bor)
    if cut is None:
        return None
    _, axis, i, toza = cut
    c = int(i * k)
    ulush = 0.01 if toza else VISION_GRID_OVERLAP
    if axis == 0:
        o = int((x2 - x1) * ulush)
        return [(x1, y1, x1 + c + o, y2), (x1 + c - o, y1, x2, y2)]
    o = int((y2 - y1) * ulush)
    return [(x1, y1, x2, y1 + c + o), (x1, y1 + c - o, x2, y2)]


def _moslash(image_path: str, regions: list, vaqtlar: list, jadvallar: list):
    """Eng sekin bo'lak qolganlaridan ancha sekin bo'lsa, keyingi siklda
    uni ikkiga bo'lamiz. Umumiy vaqtni aynan eng sekin bo'lak belgilaydi.

    Oldindan bilib bo'lmaydi: jadval (H/D format) zich ko'rinsa ham tez
    o'qiladi, alohida yozuvli sxema esa siyrak ko'rinsa ham sekin.
    Shuning uchun o'lchab, keyin bo'linadi."""
    if VISION_MODE == "regions" or len(regions) >= VISION_MAX_TILES or len(vaqtlar) < 2:
        return
    i = max(range(len(vaqtlar)), key=vaqtlar.__getitem__)
    qolgan = sorted(v for j, v in enumerate(vaqtlar) if j != i)
    orta = qolgan[len(qolgan) // 2]
    if vaqtlar[i] < 25 or vaqtlar[i] < 1.6 * orta:
        return
    yarim = _ikkiga_bol(image_path, regions[i][1], jadvallar[i])
    if not yarim:
        return
    yangi = regions[:i] + regions[i + 1:] + [("", b) for b in yarim]
    _LAYOUT["regions"] = [(f"bo'lak {n}", b) for n, (_, b) in enumerate(yangi, 1)]
    print(f"   [VISION] {regions[i][0]} sekin ({vaqtlar[i]:.0f}s, qolganlari ~{orta:.0f}s) — "
          f"keyingi siklda ikkiga bo'linadi ({len(_LAYOUT['regions'])} bo'lak).")


def _read_by_regions(image_path: str) -> dict:
    regions = _resolve_regions(image_path)
    jobs = [(name, box, image_path) for name, box in regions]
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        parts = list(pool.map(_read_one_region, jobs))
    try:
        _moslash(image_path, regions, [took for _, _, took, _ in parts],
                 [p.get("_jadval", False) for _, _, _, p in parts])
    except Exception as e:
        print(f"   [VISION] Bo'linishni moslashda xato ({e}), o'zgarishsiz qoladi.")
    merged = {"readings": {}, "equipment_states": {}, "alarms": [],
              "low_confidence_fields": [], "screen_title": ""}
    kesilgan_son = 0
    for name, size, took, part in parts:
        print(f"   [VISION-{name}] {size[0]}x{size[1]}  {took:.0f}s  "
              f"{len(part['readings'])} qiymat, {len(part['equipment_states'])} uskuna")
        kesilgan_son += _qiymatlarni_birlashtir(merged["readings"], part["readings"])
        merged["equipment_states"].update(part["equipment_states"])
        merged["alarms"].extend(part["alarms"])
    oldin = len(merged["readings"]) + len(merged["equipment_states"])
    merged["readings"] = _kesilgan_kalitlarni_tashla(merged["readings"])
    merged["equipment_states"] = _kesilgan_kalitlarni_tashla(merged["equipment_states"])
    tashlandi = oldin - len(merged["readings"]) - len(merged["equipment_states"])
    print(f"   [VISION] Bo'laklar parallel o'qildi: {time.monotonic()-started:.0f}s jami, "
          f"{len(merged['readings'])} qiymat, {len(merged['equipment_states'])} uskuna"
          + (f", {tashlandi} ta kesilgan nom tashlandi" if tashlandi else "")
          + (f", {kesilgan_son} ta kesilgan son tuzatildi" if kesilgan_son else ""))
    return merged


def read_dashboard_with_ai(image_path: str, model: str = VISION_MODEL) -> dict:
    """Skrinshotni AI vision modelga yuboradi, dict qaytaradi.

    VISION_MODE="grid"    — ekran AVTOMATIK panjara bo'yicha bo'linib,
       bo'laklar parallel o'qiladi. Koordinata yozish shart emas, shuning
       uchun ISTALGAN SCADA/HMI ekranida ishlaydi. Standart rejim.
    VISION_MODE="regions" — qo'lda yozilgan VISION_REGIONS koordinatalari
       (faqat bitta aniq ekran uchun).
    VISION_MODE="full"    — butun ekran bitta JSON so'rovda. Eng sekin va
       eng kam aniq; zaxira variant.

    Qaytadigan dict uchala holatda ham bir xil ko'rinishda — quvurning
    qolgan qismi farqni sezmaydi."""
    if VISION_MODE in ("grid", "regions"):
        return _read_by_regions(image_path)
    b64_image = _compress_image_for_ai(image_path)
    return llm_client.chat_completion(
        model=model, prompt=PROMPT, image_b64=b64_image, json_mode=True,
        max_tokens=VISION_MAX_TOKENS, label="VISION"
    )