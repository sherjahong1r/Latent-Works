# """
# config.py — real loyiha uchun MARKAZIY sozlamalar fayli.
# Real SCADA'ga moslashda odatda faqat shu faylni tahrirlash kifoya.
# """

# import os
# from dotenv import load_dotenv

# load_dotenv()

# # ── Ma'lumotlar bazasi ────────────────────────────────────────────────
# DB_CONFIG = {
#     "host": os.environ.get("DB_HOST", "localhost"),
#     "port": int(os.environ.get("DB_PORT", 5433)),
#     "dbname": os.environ.get("DB_NAME", "chem_scada"),
#     "user": os.environ.get("DB_USER", "postgres"),
#     "password": os.environ.get("DB_PASSWORD", "jahongir"),
# }

# # ── SCADA ekraniga qanday ulanish ───────────────────────────────────────
# # "url"    -> SCADA veb-brauzerda ochiladi (Playwright orqali).
# # "window" -> SCADA alohida Windows dasturi (veb-emas).
# # "screen" -> Butun ekranni suratga oladi (zaxira variant).
# CAPTURE_MODE = "url"

# SCADA_URL = os.environ.get(
#     "SCADA_URL",
#     "https://demo.inductiveautomation.com/data/perspective/client/water-treatment-demo/overview",
# )
# SCADA_WINDOW_TITLE = "Automatic Washing"   # CAPTURE_MODE="window" uchun

# # ── Ma'lum ko'rsatkich nomlari (aniqlik uchun, ixtiyoriy) ──────────────
# KNOWN_SENSOR_LABELS = {
#     # "Ekrandagi aniq yozuv": "kerakli_kalit_nomi",
# }

# # ── Ollama — VISION model (skrinshotni o'qish uchun) ────────────────────
# OLLAMA_BASE_URL = os.environ.get(
#     "OLLAMA_BASE_URL", "https://JORIY-NGROK-MANZILINGIZNI-BU-YERGA-YOZING.ngrok-free.app"
# )
# VISION_MODEL = os.environ.get("VISION_MODEL", "qwen3-vl:8b")
# OLLAMA_MODEL = VISION_MODEL   # eski nom bilan moslik uchun

# # ── Ollama — MATN (LLM) model — xulosa/bashorat/hisobot yozish uchun ────
# OLLAMA_TEXT_MODEL = os.environ.get("OLLAMA_TEXT_MODEL", "qwen3:14b")

# # BARCHA Ollama so'rovlari (vision + matn) shu bitta timeout'dan
# # foydalanadi — turli fayllar turli timeout ishlatib, bir-biriga zid
# # natija berishining oldini olish uchun.
# OLLAMA_TIMEOUT_SECONDS = 240

# # ── Rasm siqish (TEZLIK uchun) ────────────────────────────────────────
# IMAGE_MAX_WIDTH = 1280
# IMAGE_JPEG_QUALITY = 82

# MAX_RETRIES = 3
# RETRY_DELAY_SECONDS = 15

# # ── Skrinshot + JSON oqimi ────────────────────────────────────────────
# SCREENSHOT_TEMP_DIR = "temp_screenshots"
# SCREENSHOT_INTERVAL_SECONDS = 45

# # ── AI Advisor (xulosachi LLM) sozlamalari ───────────────────────────────
# ADVISOR_CYCLE_SECONDS = 120
# ADVISOR_HISTORY_LIMIT = 30

# # ── Anomaly Detection (statistik baza — ML plug-in nuqtasi bilan) ───────
# # Bu — ML modelingiz hali ulanmagan holatda ishlaydigan ARZON, tezkor
# # "xavfsizlik tarmog'i": har bir raqamli metrikaning oxirgi qiymati
# # o'zining tarixiy o'rtachasidan necha "standart og'ish" (z-score)
# # uzoqda ekanini hisoblaydi. anomaly_detector.py'dagi
# # `compute_anomaly_report()` funksiyasini o'z ML modelingiz bilan
# # almashtirish mumkin — pipeline qolgan qismi o'zgarishsiz ishlayveradi.
# ANOMALY_LOOKBACK_MINUTES = 30
# ANOMALY_Z_THRESHOLD = 3.0        # shundan yuqori |z| — anomaliya deb belgilanadi
# ANOMALY_MIN_POINTS = 5           # hisoblash uchun kerakli minimal nuqtalar soni

# # ── Bashorat (prediction) — adaptiv interval ─────────────────────────────
# # Interval har doim PREDICTION_INTERVAL_MIN va MAX orasida, o'zgarish
# # tezligiga (volatillikka) qarab avtomatik tanlanadi:
# #   - Holat tez o'zgarayotgan bo'lsa -> intervalga yaqinroq MIN (tezroq)
# #   - Holat barqaror bo'lsa          -> intervalga yaqinroq MAX (kamroq)
# PREDICTION_INTERVAL_MIN_SECONDS = 60          # 1 daqiqa
# PREDICTION_INTERVAL_MAX_SECONDS = 15 * 60     # 15 daqiqa
# PREDICTION_HORIZONS_MINUTES = [10, 20, 30]
# PREDICTION_LOOKBACK_MINUTES = 30
# PREDICTION_MIN_POINTS = 5
# # Nisbiy o'zgarish (oxirgi nuqtalar orasidagi farq / o'rtacha qiymat)
# # shu chegaradan oshsa — "tez o'zgaryapti" deb hisoblanadi, interval
# # tezlashadi.
# PREDICTION_VOLATILITY_THRESHOLD = 0.03

# # ── P&ID / process topology (skelet, ixtiyoriy) ──────────────────────────
# # process_topology.py faylida TOPOLOGY lug'atini to'ldirsangiz, bu
# # ma'lumot avtomatik ravishda AI Advisor va Predictor promptlariga
# # qo'shiladi — shunda AI uskunalar orasidagi bog'liqlikni "biladi".
# # Bo'sh qoldirilsa, bu funksiya sokin o'tkazib yuboriladi.
# USE_PROCESS_TOPOLOGY = True

# # ── Smena hisoboti ────────────────────────────────────────────────────
# ENABLE_SHIFT_REPORT = True
# SHIFT_REPORT_INTERVAL_HOURS = 12

# # ── Retention (avtomatik tozalash O'CHIRILGAN — ma'lumot cheksiz saqlanadi) ─
# RETENTION_DAYS = 30
# RETENTION_CHECK_INTERVAL_SECONDS = 24 * 60 * 60

# # ── Interfeys — ro'yxatlarda nechta OXIRGI yozuv ko'rsatilsin ──────────
# DASHBOARD_LIST_LIMIT = 10

# # ── Vaqt zonasi (FAQAT interfeysda TO'G'RI vaqt ko'rsatish uchun) ──────
# # Bazadagi barcha vaqtlar endi UTC (TIMESTAMPTZ) sifatida saqlanadi —
# # interfeys esa buni har doim shu vaqt zonasida ko'rsatadi, serverning
# # o'zi qaysi zonada ishlab turganidan (Windows mahalliy vaqti, bulutli
# # server UTC vaqti va h.k.) qat'i nazar. Bu — oldin "vaqt noto'g'ri
# # ko'rsatilyapti" muammosining asosiy sababini (TIMESTAMP ustunlar
# # vaqt zonasisiz saqlangani) tuzatadi.
# APP_TIMEZONE = "Asia/Tashkent"

# # ── Operating Mode (STARTUP / NORMAL / SHUTDOWN / MAINTENANCE) ─────────
# # So'nggi shuncha ta vision_reports orasidagi ENG BIRINCHI va ENG
# # OXIRGI equipment_states'ni solishtirib, necha foiz uskuna holati
# # o'zgarganini hisoblaydi (ai_advisor.py har siklda chaqiradi).
# OPERATING_MODE_LOOKBACK_REPORTS = 6      # ~45s * 6 = ~4.5 daqiqalik oyna
# OPERATING_MODE_CHANGE_RATIO = 0.3        # 30%+ uskuna o'zgarsa -> STARTUP/SHUTDOWN
# # NORMAL bo'lmagan rejimlarda anomaliya chegarasi shuncha marta
# # YUMSHATILADI (kattaroq qiymat = kamroq soxta ogohlantirish)
# OPERATING_MODE_ANOMALY_RELAXATION = 1.8













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
CAPTURE_MODE = "url"

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
VISION_MAX_TOKENS = int(os.environ.get("VISION_MAX_TOKENS", 1500))
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
IMAGE_MAX_WIDTH = int(os.environ.get("IMAGE_MAX_WIDTH", 1280))
IMAGE_JPEG_QUALITY = int(os.environ.get("IMAGE_JPEG_QUALITY", 82))

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 15

# ── Skrinshot + JSON oqimi ────────────────────────────────────────────
SCREENSHOT_TEMP_DIR = "temp_screenshots"
SCREENSHOT_INTERVAL_SECONDS = 45

# ── AI Advisor (xulosachi LLM) sozlamalari ───────────────────────────────
ADVISOR_CYCLE_SECONDS = 120
ADVISOR_HISTORY_LIMIT = 30

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