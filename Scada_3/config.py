"""
config.py — real loyiha uchun MARKAZIY sozlamalar fayli.
Real SCADA'ga moslashda odatda faqat shu faylni tahrirlash kifoya.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Ma'lumotlar bazasi ────────────────────────────────────────────────
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", 5433)),
    "dbname": os.environ.get("DB_NAME", "chem_scada"),
    "user": os.environ.get("DB_USER", "postgres"),
    "password": os.environ.get("DB_PASSWORD", "jahongir"),
}

# ── SCADA ekraniga qanday ulanish ───────────────────────────────────────
# "url"    -> SCADA veb-brauzerda ochiladi (Playwright orqali).
# "window" -> SCADA alohida Windows dasturi (veb-emas).
# "screen" -> Butun ekranni suratga oladi (zaxira variant).
# "camera" -> Boshqa monitordagi dashboard kamera orqali suratga olinadi.
CAPTURE_MODE = os.environ.get("CAPTURE_MODE", "url").strip().lower()

# ── Kamera (CAPTURE_MODE="camera") ──────────────────────────────────────
# Kamera raqami: 0 — odatda noutbukning o'z kamerasi, 1 — tashqi USB kamera.
CAMERA_INDEX = int(os.environ.get("CAMERA_INDEX", 1))
# 0 bo'lsa kamera qo'llaydigan eng katta o'lcham tanlanadi (tavsiya).
CAMERA_WIDTH = int(os.environ.get("CAMERA_WIDTH", 0))
CAMERA_HEIGHT = int(os.environ.get("CAMERA_HEIGHT", 0))
# Ekranning 4 burchagi shu faylda saqlanadi (`py camera_calibrate.py`).
CAMERA_CALIBRATION_FILE = os.environ.get("CAMERA_CALIBRATION_FILE", "camera_calibration.json")
# Kamera buferidagi eski kadrlarni tashlash uchun nechta kadr o'tkaziladi.
CAMERA_WARMUP_FRAMES = int(os.environ.get("CAMERA_WARMUP_FRAMES", 4))

SCADA_URL = os.environ.get(
    "SCADA_URL",
    "https://demo.inductiveautomation.com/data/perspective/client/water-treatment-demo/overview",
)
SCADA_WINDOW_TITLE = "Automatic Washing"   # CAPTURE_MODE="window" uchun

# ── Ma'lum ko'rsatkich nomlari (aniqlik uchun, ixtiyoriy) ──────────────
KNOWN_SENSOR_LABELS = {
    # "Ekrandagi aniq yozuv": "kerakli_kalit_nomi",
}

# ── Ollama — VISION model (skrinshotni o'qish uchun) ────────────────────
OLLAMA_BASE_URL = os.environ.get(
    "OLLAMA_BASE_URL", "https://JORIY-NGROK-MANZILINGIZNI-BU-YERGA-YOZING.ngrok-free.app"
).strip()
VISION_MODEL = os.environ.get("VISION_MODEL", "qwen3-vl:8b").strip()
OLLAMA_MODEL = VISION_MODEL   # eski nom bilan moslik uchun

# ── Ollama — MATN (LLM) model — xulosa/bashorat/hisobot yozish uchun ────
OLLAMA_TEXT_MODEL = os.environ.get("OLLAMA_TEXT_MODEL", "qwen3:14b").strip()

# BARCHA Ollama so'rovlari (vision + matn) shu bitta timeout'dan
# foydalanadi — turli fayllar turli timeout ishlatib, bir-biriga zid
# natija berishining oldini olish uchun.
OLLAMA_TIMEOUT_SECONDS = 240

# ── LLM provider tanlash ──────────────────────────────────────────────
# "ollama" — standart Ollama server (/api/chat formatida so'rov).
# "vllm"   — OpenAI-compatible vLLM server (/v1/chat/completions,
#            Authorization: Bearer <VLLM_API_KEY> header bilan).
# OLLAMA_BASE_URL, VISION_MODEL, OLLAMA_TEXT_MODEL sozlamalari HAR
# IKKALA holatda ham ishlatiladi (nom "OLLAMA_" bilan boshlansa ham) —
# faqat so'rov formati llm_client.py'da provider'ga qarab tanlanadi.
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "ollama").strip().lower()

# vLLM uchun API kalit (LLM_PROVIDER="vllm" bo'lganda ishlatiladi).
# Ollama rejimida bo'sh qoldirilishi mumkin.
VLLM_API_KEY = os.environ.get("VLLM_API_KEY", "").strip()

# ── TEZLIK sozlamalari ────────────────────────────────────────────────
# 1500 kam edi: to'liq ekranning javobi ~2900 belgi (~800+ token) va
# chegaraga urилганда JSON o'rtasidan kesilib, butun bir blok (masalan
# filtr sathlari) yo'qolardi.
VISION_MAX_TOKENS = int(os.environ.get("VISION_MAX_TOKENS", 3000))
TEXT_MAX_TOKENS = int(os.environ.get("TEXT_MAX_TOKENS", 600))
SHIFT_REPORT_MAX_TOKENS = int(os.environ.get("SHIFT_REPORT_MAX_TOKENS", 1500))

# Ba'zi vLLM sozlamalarida "response_format" (guided decoding) SEKIN
# ishlashi mumkin — .env'da VLLM_JSON_MODE=false qilib sinab ko'rish mumkin.
VLLM_JSON_MODE = os.environ.get("VLLM_JSON_MODE", "true").strip().lower() != "false"

# ── ANOMALIYA ISHONCHLILIGI ──────────────────────────────────────────
# MUHIM: bitta g'alati kadr (vision xatosi yoki tasodifiy sensor
# sakrashi) butun ogohlantirish zanjirini (Advisor/Predictor/Smena
# hisoboti) ishga tushirmasligi uchun — anomaliya faqat KETMA-KET
# ikkita o'qish ham chegaradan chiqqanda "haqiqiy" deb hisoblanadi.
ANOMALY_REQUIRE_CONSECUTIVE = True

# ── Rasm siqish (TEZLIK uchun) ────────────────────────────────────────
# DIQQAT: bu qiymatlarni pasaytirish TEZLIK bermaydi, faqat ANIQLIKNI
# yo'q qiladi. O'lchov (2026-09-23, shot_8, 57 ta qo'lda tasdiqlangan
# qiymat, gemma4-31b):
#     640 px / q60  ->  93 s,  8/57 to'g'ri (14%),  67% uydirma
#     960 px / q80  -> 122 s, 50/57 to'g'ri (88%),   1% uydirma
#    1920 px / q90  -> 120 s, 50/57 to'g'ri (88%),  11% uydirma
# Vaqt rasm hajmiga deyarli bog'liq emas — u modelning javob YOZISH
# tezligiga bog'liq. Shuning uchun kichraytirishdan foyda yo'q.
IMAGE_MAX_WIDTH = int(os.environ.get("IMAGE_MAX_WIDTH", 960))
IMAGE_JPEG_QUALITY = int(os.environ.get("IMAGE_JPEG_QUALITY", 80))

# ── Vision o'qish rejimi ──────────────────────────────────────────────
# "regions" — ekran bo'laklarga bo'linib, har biri ASL o'lchamida,
#             PARALLEL o'qiladi, natija birlashtiriladi.
# "full"    — butun ekran bitta so'rovda (bo'laklar sozlanmagan bo'lsa
#             yoki boshqa SCADA ekraniga o'tilganda zaxira variant).
#
# Nega "regions" — o'sha o'lchovda (shot_8):
#     to'liq + JSON        -> 121 s, 88% to'g'ri, 22 uskuna, 1 uydirma
#     bo'lak + parallel    ->  61 s, 93% to'g'ri, 36 uskuna, 0 uydirma
# Ikki sabab: (1) kesim kichraytirilmagani uchun har bir raqam ~2 barobar
# ko'p pikselga ega; (2) har bir so'rov javobning uchdan birini yozadi,
# uchalasi bir vaqtda ketadi — server parallel so'rovni ko'taradi.
# "grid"    — ekran AVTOMATIK panjara bo'yicha bo'linadi. Koordinata
#             yozish shart emas, ISTALGAN SCADA ekranida ishlaydi.
#             Standart va tavsiya etiladigan rejim.
# "regions" — qo'lda yozilgan VISION_REGIONS koordinatalari. Faqat aniq
#             bir ekran uchun qo'shimcha aniqlik kerak bo'lsa.
# "full"    — butun ekran bitta so'rovda (eng sekin, eng kam aniq).
VISION_MODE = os.environ.get("VISION_MODE", "grid").strip().lower()

# Panjara o'lchami: (ustunlar, qatorlar). Kesimlar KICHRAYTIRILMAYDI —
# har bir raqam asl piksellarida qoladi, aniqlik shundan kelib chiqadi.
# 2x2 — 1920x1080 ekran uchun sinovdan o'tgan muvozanat: har bo'lak
# 960x540, to'rtta so'rov parallel ketadi. Kattaroq panjara bo'laklarni
# maydalaydi, lekin parallel so'rovlar soni ortib server navbatga qo'ya
# boshlaydi (5 ta bo'lakda vaqt 43 s dan 85 s ga chiqqani o'lchangan).
VISION_GRID = (
    int(os.environ.get("VISION_GRID_COLS", 2)),
    int(os.environ.get("VISION_GRID_ROWS", 2)),
)
# Bo'laklar chetma-chet emas, biroz USTMA-UST kesiladi — chegarada turgan
# panel ikkiga bo'linib, qiymati nomidan ajralib qolmasligi uchun.
# Takror o'qilgan qiymat birlashtirishda ustiga yoziladi, zarari yo'q.
VISION_GRID_OVERLAP = float(os.environ.get("VISION_GRID_OVERLAP", 0.06))

# "grid" rejimida ekran nechta bo'lakka bo'linadi. Bo'linish teng
# geometrik emas, MAZMUN HAJMIGA qarab: har safar eng zich bo'lak
# panellar orasidagi bo'sh joydan ikkiga bo'linadi, shuning uchun har
# bir parallel so'rov taxminan teng ish oladi.
VISION_TILES = int(os.environ.get("VISION_TILES", 4))
# Har siklda bo'laklar vaqti o'lchanadi: eng sekini qolganlaridan 1.6
# barobar sekin bo'lsa, keyingi siklda u ikkiga bo'linadi — shu
# chegaragacha. Juda ko'p parallel so'rov serverni navbatga qo'yadi.
VISION_MAX_TILES = int(os.environ.get("VISION_MAX_TILES", 6))
# Shuncha sikldan keyin bo'linish noldan quriladi (operator boshqa
# sahifaga o'tgan bo'lishi mumkin).
VISION_LAYOUT_REFRESH_CYCLES = int(os.environ.get("VISION_LAYOUT_REFRESH_CYCLES", 40))

# Bo'laklar: (nom, (x1, y1, x2, y2)) — ASL skrinshot piksellarida.
# Chegaralar biroz USTMA-UST: chetdagi ko'rsatkich kesilib qolmasligi
# uchun. Takror o'qilgan qiymat birlashtirishda ustiga yozilади, zarari yo'q.
#
# BOSHQA SCADA EKRANIGA O'TSANGIZ: bu ro'yxatni o'sha ekranning
# bloklariga qarab qayta yozing, yoki VISION_MODE="full" qiling.
# Ustma-ustlik ATAYLAB kichik: ilgari "o'ng" x=1180 dan boshlanardi va
# Backwash panelini "o'rta" bilan IKKI MARTA o'qirdi -- bitta qiymat ikki
# xil nom bilan bazaga tushardi. Ustiga u y=820 da kesilib, pastdagi
# Clearwell Tank butunlay tushib qolardi.
# To'rtta bo'lak. Nega uchta emas: "o'rta" (filtrlar) eng zich va eng
# sekin bo'lak edi (60 s) -- umumiy vaqtni aynan u belgilardi, chunki
# bo'laklar parallel ketadi va eng sekini kutiladi. Uni ikkiga bo'lish
# ham vaqtni qisqartiradi, ham har bir so'rovning vazifasini yengillatib
# TO'LIQLIKNI oshiradi (bitta so'rov 40 ta qiymat o'rniga 20 tasini
# yozadi va ro'yxatni yarim yo'lda tashlab ketmaydi).
# Kesim y=652 da: filtrlarning 2- va 3-qatori orasidan o'tadi, hech bir
# panel ikkiga bo'linmaydi.
VISION_REGIONS = [
    ("chap",         (245,  60,  850, 1080)),
    ("filtr-yuqori", (830,  60, 1460,  658)),
    ("filtr-past",   (830, 646, 1460, 1080)),
    # "o'ng" ham ikkiga bo'lindi: u baland va tor (480x1020) bo'lib,
    # ichida 14 qiymat va 10 uskuna bor edi -- model ba'zan ro'yxatni
    # oxirigacha yozmay, tanklarning ft/gal qatorlarini tushirib
    # qoldirardi (jonli yurishda nom barqarorligi 92% ga tushgan).
    # Kesim y=592 da: tanklar paneli tugab, High Service Pumps
    # boshlanishidan oldin.
    ("o'ng-yuqori", (1440,  60, 1920,  592)),
    ("o'ng-past",   (1440, 580, 1920, 1080)),
]
VISION_REGION_JPEG_QUALITY = int(os.environ.get("VISION_REGION_JPEG_QUALITY", 88))
VISION_REGION_MAX_TOKENS = int(os.environ.get("VISION_REGION_MAX_TOKENS", 2500))

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 15

# ── Skrinshot + JSON oqimi ────────────────────────────────────────────
SCREENSHOT_TEMP_DIR = "temp_screenshots"
SCREENSHOT_INTERVAL_SECONDS = 45

# ── AI Advisor (xulosachi LLM) sozlamalari ───────────────────────────────
ADVISOR_CYCLE_SECONDS = 120
ADVISOR_HISTORY_LIMIT = 30
# AI xulosasi har nechta o'qishda bir marta. Xulosa o'qish bilan BIR
# VAQTDA serverga tushadi va ikkalasini ham sekinlashtiradi (o'lchangan:
# har siklda chaqirilganda xulosa 50 s -> 70 s gacha o'sib borgan).
# Zavod holati 1-2 daqiqada keskin o'zgarmaydi; 2 — muvozanat.
ADVISOR_EVERY_N_READINGS = int(os.environ.get("ADVISOR_EVERY_N_READINGS", 2))

# Tendensiya (o'smoqda/kamaymoqda) faqat shuncha nuqta va daqiqadan
# keyin belgilanadi — qisqa qatorda shovqin trend bo'lib ko'rinadi.
TREND_MIN_POINTS = int(os.environ.get("TREND_MIN_POINTS", 6))
TREND_MIN_MINUTES = float(os.environ.get("TREND_MIN_MINUTES", 5))

# ── Anomaly Detection (statistik baza — ML plug-in nuqtasi bilan) ───────
# Bu — ML modelingiz hali ulanmagan holatda ishlaydigan ARZON, tezkor
# "xavfsizlik tarmog'i": har bir raqamli metrikaning oxirgi qiymati
# o'zining tarixiy o'rtachasidan necha "standart og'ish" (z-score)
# uzoqda ekanini hisoblaydi. anomaly_detector.py'dagi
# `compute_anomaly_report()` funksiyasini o'z ML modelingiz bilan
# almashtirish mumkin — pipeline qolgan qismi o'zgarishsiz ishlayveradi.
ANOMALY_LOOKBACK_MINUTES = 30
ANOMALY_Z_THRESHOLD = 3.0        # shundan yuqori |z| — anomaliya deb belgilanadi
ANOMALY_MIN_POINTS = 5           # hisoblash uchun kerakli minimal nuqtalar soni

# ── Bashorat (prediction) — adaptiv interval ─────────────────────────────
# Interval har doim PREDICTION_INTERVAL_MIN va MAX orasida, o'zgarish
# tezligiga (volatillikka) qarab avtomatik tanlanadi:
#   - Holat tez o'zgarayotgan bo'lsa -> intervalga yaqinroq MIN (tezroq)
#   - Holat barqaror bo'lsa          -> intervalga yaqinroq MAX (kamroq)
PREDICTION_INTERVAL_MIN_SECONDS = 60          # 1 daqiqa
PREDICTION_INTERVAL_MAX_SECONDS = 15 * 60     # 15 daqiqa
PREDICTION_HORIZONS_MINUTES = [10, 20, 30]
PREDICTION_LOOKBACK_MINUTES = 30
PREDICTION_MIN_POINTS = 5
# Nisbiy o'zgarish (oxirgi nuqtalar orasidagi farq / o'rtacha qiymat)
# shu chegaradan oshsa — "tez o'zgaryapti" deb hisoblanadi, interval
# tezlashadi.
PREDICTION_VOLATILITY_THRESHOLD = 0.03

# Trendning ishonchlilik chegarasi (R^2, 0..1). Bundan past bo'lsa,
# "trend" aslida shovqin — bashorat kuzatilgan oraliqdan uzoqqa
# chiqarilmaydi. Nega kerak: chegarasiz chiziqli ekstrapolyatsiya
# "Turbidity 30 daqiqadan keyin MANFIY bo'ladi" va "Finished Flow 0 dan
# 12562 ga chiqadi" kabi jismonan mumkin bo'lmagan HIGH ogohlantirish
# bergan (2026-09-24 da kuzatilgan haqiqiy holat).
PREDICTION_MIN_FIT_R2 = float(os.environ.get("PREDICTION_MIN_FIT_R2", 0.5))

# ── P&ID / process topology (skelet, ixtiyoriy) ──────────────────────────
# process_topology.py faylida TOPOLOGY lug'atini to'ldirsangiz, bu
# ma'lumot avtomatik ravishda AI Advisor va Predictor promptlariga
# qo'shiladi — shunda AI uskunalar orasidagi bog'liqlikni "biladi".
# Bo'sh qoldirilsa, bu funksiya sokin o'tkazib yuboriladi.
USE_PROCESS_TOPOLOGY = True

# ── Smena hisoboti ────────────────────────────────────────────────────
ENABLE_SHIFT_REPORT = True
SHIFT_REPORT_INTERVAL_HOURS = 12

# ── Retention (avtomatik tozalash O'CHIRILGAN — ma'lumot cheksiz saqlanadi) ─
RETENTION_DAYS = 30
RETENTION_CHECK_INTERVAL_SECONDS = 24 * 60 * 60