# """
# config.py — real loyiha uchun MARKAZIY sozlamalar fayli.

# MUHIM PRINSIP: barcha boshqa fayllar sozlamalarni SHU FAYLDAN oladi.
# Real SCADA'ga moslashda odatda faqat shu faylni tahrirlash kifoya.
# """

# import os
# from dotenv import load_dotenv

# load_dotenv()

# # ── Ma'lumotlar bazasi ────────────────────────────────────────────────
# DB_CONFIG = {
#     "host": "localhost",
#     "port": 5433,
#     "dbname": "chem_scada",
#     "user": "postgres",
#     "password": "jahongir",
# }

# # ── SCADA ekraniga qanday ulanish ───────────────────────────────────────
# CAPTURE_MODE = "url"   # "url", "window" yoki "screen"

# SCADA_URL = "https://demo.inductiveautomation.com/data/perspective/client/water-treatment-demo/overview"
# SCADA_WINDOW_TITLE = "Automatic Washing"   # CAPTURE_MODE="window" uchun

# # ── Ma'lum ko'rsatkich nomlari (aniqlik uchun, ixtiyoriy) ──────────────
# KNOWN_SENSOR_LABELS = {
#     # "Ekrandagi aniq yozuv": "kerakli_kalit_nomi",
# }

# # ── Ollama — VISION model (skrinshotni o'qish uchun) ────────────────────
# #
# # MUHIM: ngrok bepul tarif har safar qayta ishga tushirilganda YANGI
# # tasodifiy manzil beradi. "Read timed out" / "404" chiqsa — bu yerni
# # JORIY ngrok manziliga yangilang (yoki .env fayliga yozing).
# OLLAMA_BASE_URL = os.environ.get(
#     "OLLAMA_BASE_URL", "https://b3be-62-164-155-48.ngrok-free.app"
# )
# # https://exorcist-percent-applicant.ngrok-free.dev

# VISION_MODEL = os.environ.get("VISION_MODEL", "qwen3-vl:8b")
# OLLAMA_MODEL = VISION_MODEL   # eski nom bilan moslik uchun

# # ── Ollama — MATN (LLM) model — xulosa/ogohlantirish yozish uchun ───────
# # Bu VISION modeldan MUSTAQIL, ALOHIDA model — faqat ai_advisor.py
# # shundan foydalanadi (rasm o'qimaydi, faqat tarixiy JSON'larni matn
# # sifatida tahlil qiladi va tavsiya yozadi). qwen3:14b — vision modeldan
# # yengilroq va tezroq, matn tahlili uchun yetarli sifatli.
# #
# # ESLATMA: agar Ollama serveringiz (ngrok orqasidagi GPU) kichik VRAM'ga
# # ega bo'lsa, ikkita xil model (VISION_MODEL + bu) bir vaqtda ishlatilsa,
# # Ollama ularni almashtirib turishga majbur bo'lib, sekinlashishi va
# # timeout berishi mumkin. Agar shunday muammo kuzatilsa, buni yana
# # VISION_MODEL bilan bir xil qilib qo'yish (pastdagi eski qatorni
# # qaytarish) mumkin.
# OLLAMA_TEXT_MODEL = os.environ.get("OLLAMA_TEXT_MODEL", "qwen3:14b")

# # ── Bitta oqim: har N soniyada skrinshot -> JSON -> baza ────────────────
# # MUHIM: video yozish OLIB TASHLANDI — endi faqat skrinshot + JSON oqimi
# # bor. Brauzer sahifasi doim OCHIQ turadi, undan davriy ravishda
# # skrinshot olinadi.
# SCREENSHOT_TEMP_DIR = "temp_screenshots"  # vaqtinchalik skrinshotlar (tahlildan keyin o'chiriladi)
# SCREENSHOT_INTERVAL_SECONDS = 45          # necha soniyada bir marta skrinshot+JSON

# MAX_RETRIES = 3             # Ollama vaqtincha javob bermasa, necha marta urinish
# RETRY_DELAY_SECONDS = 15    # urinishlar orasidagi kutish vaqti

# # ── Rasm siqish (TEZLIK uchun) ────────────────────────────────────────
# # AI'ga yuborishdan oldin skrinshot shu enga toraytiriladi va JPEG
# # formatiga siqiladi. Bu vision modelga yuboriladigan ma'lumot hajmini
# # sezilarli kamaytiradi -> tahlil TEZROQ tugaydi, timeout xavfi kamayadi.
# # Matn/raqamlar hali ham o'qiladigan darajada aniq qoladi.
# IMAGE_MAX_WIDTH = 1280       # shundan kengroq rasm shu enga toraytiriladi
# IMAGE_JPEG_QUALITY = 82      # 0-100 (yuqoriroq = sifatliroq, lekin sekinroq)

# # Ollama'ga so'rov uchun maksimal kutish vaqti (soniya). Agar model
# # doimiy ravishda shu vaqtda javob bera olmasa, buni oshirish emas,
# # balki server tomonidagi (GPU/VRAM) tezlikni yaxshilash yoki rasm
# # hajmini yanada kamaytirish to'g'riroq yechim.
# OLLAMA_TIMEOUT_SECONDS = 120

# # ── AI Advisor (xulosachi LLM) sozlamalari ───────────────────────────────
# ADVISOR_CYCLE_SECONDS = 120   # har necha soniyada bir marta tahlil qiladi
# ADVISOR_HISTORY_LIMIT = 30    # tahlil uchun oxirgi nechta hisobotni oladi

# # ── Retention / tozalash sozlamalari ─────────────────────────────────────
# # ESLATMA: avtomatik tozalash O'CHIRILGAN (main.py'da endi ishga
# # tushirilmaydi) — ma'lumotlar HECH QACHON avtomatik o'chirilmaydi,
# # doimiy saqlanadi. Quyidagi sozlamalar faqat agar kelajakda
# # `py retention_cleanup.py` ni QO'LDA ishga tushirsangiz ishlatiladi.
# RETENTION_DAYS = 30
# RETENTION_CHECK_INTERVAL_SECONDS = 24 * 60 * 60











"""
config.py — real loyiha uchun MARKAZIY sozlamalar fayli.

MUHIM PRINSIP: barcha boshqa fayllar sozlamalarni SHU FAYLDAN oladi.
Real SCADA'ga moslashda odatda faqat shu faylni tahrirlash kifoya.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Ma'lumotlar bazasi ────────────────────────────────────────────────
DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "dbname": "chem_scada",
    "user": "postgres",
    "password": "jahongir",
}

# ── SCADA ekraniga qanday ulanish ───────────────────────────────────────
CAPTURE_MODE = "url"   # "url", "window" yoki "screen"

SCADA_URL = "https://demo.inductiveautomation.com/data/perspective/client/water-treatment-demo/overview"
SCADA_WINDOW_TITLE = "Automatic Washing"   # CAPTURE_MODE="window" uchun

# ── Ma'lum ko'rsatkich nomlari (aniqlik uchun, ixtiyoriy) ──────────────
KNOWN_SENSOR_LABELS = {
    # "Ekrandagi aniq yozuv": "kerakli_kalit_nomi",
}

# ── Ollama — VISION model (skrinshotni o'qish uchun) ────────────────────
#
# MUHIM: ngrok bepul tarif har safar qayta ishga tushirilganda YANGI
# tasodifiy manzil beradi. "Read timed out" / "404" chiqsa — bu yerni
# JORIY ngrok manziliga yangilang (yoki .env fayliga yozing).
OLLAMA_BASE_URL = os.environ.get(
    "OLLAMA_BASE_URL", "https://exorcist-percent-applicant.ngrok-free.dev"
)

VISION_MODEL = os.environ.get("VISION_MODEL", "qwen3-vl:8b")
OLLAMA_MODEL = VISION_MODEL   # eski nom bilan moslik uchun

# ── Ollama — MATN (LLM) model — xulosa/ogohlantirish yozish uchun ───────
# Bu VISION modeldan MUSTAQIL, ALOHIDA model — faqat ai_advisor.py
# shundan foydalanadi (rasm o'qimaydi, faqat tarixiy JSON'larni matn
# sifatida tahlil qiladi va tavsiya yozadi). qwen3:14b — vision modeldan
# yengilroq va tezroq, matn tahlili uchun yetarli sifatli.
#
# ESLATMA: agar Ollama serveringiz (ngrok orqasidagi GPU) kichik VRAM'ga
# ega bo'lsa, ikkita xil model (VISION_MODEL + bu) bir vaqtda ishlatilsa,
# Ollama ularni almashtirib turishga majbur bo'lib, sekinlashishi va
# timeout berishi mumkin. Agar shunday muammo kuzatilsa, buni yana
# VISION_MODEL bilan bir xil qilib qo'yish (pastdagi eski qatorni
# qaytarish) mumkin.
OLLAMA_TEXT_MODEL = os.environ.get("OLLAMA_TEXT_MODEL", "qwen3:14b")

# ── Bitta oqim: har N soniyada skrinshot -> JSON -> baza ────────────────
# MUHIM: video yozish OLIB TASHLANDI — endi faqat skrinshot + JSON oqimi
# bor. Brauzer sahifasi doim OCHIQ turadi, undan davriy ravishda
# skrinshot olinadi.
SCREENSHOT_TEMP_DIR = "temp_screenshots"  # vaqtinchalik skrinshotlar (tahlildan keyin o'chiriladi)
SCREENSHOT_INTERVAL_SECONDS = 45          # necha soniyada bir marta skrinshot+JSON

MAX_RETRIES = 3             # Ollama vaqtincha javob bermasa, necha marta urinish
RETRY_DELAY_SECONDS = 15    # urinishlar orasidagi kutish vaqti

# ── Rasm siqish (TEZLIK uchun) ────────────────────────────────────────
# AI'ga yuborishdan oldin skrinshot shu enga toraytiriladi va JPEG
# formatiga siqiladi. Bu vision modelga yuboriladigan ma'lumot hajmini
# sezilarli kamaytiradi -> tahlil TEZROQ tugaydi, timeout xavfi kamayadi.
# Matn/raqamlar hali ham o'qiladigan darajada aniq qoladi.
IMAGE_MAX_WIDTH = 1280       # shundan kengroq rasm shu enga toraytiriladi
IMAGE_JPEG_QUALITY = 82      # 0-100 (yuqoriroq = sifatliroq, lekin sekinroq)

# Ollama'ga so'rov uchun maksimal kutish vaqti (soniya). BARCHA fayllar
# (vision_toolkit.py — skrinshot tahlili, ai_advisor.py — xulosa yozish)
# shu BITTA qiymatdan foydalanadi — ikkalasi ham BIR XIL server bilan
# ishlaganda, mos kelmagan timeout'lar bir xilini "muvaffaqiyatli",
# ikkinchisini esa "timeout" qilib ko'rsatib, chalkash natija berishi
# mumkin edi (aynan shu muammo yuz bergan edi).
#
# 240s (4 daqiqa) — ikkita TURLI model (VISION_MODEL va OLLAMA_TEXT_MODEL)
# ishlatilganda, server ular orasida almashishi (model reload) uchun
# ham yetarli vaqt beradi. Agar bu ham kamlik qilsa, buni oshirish
# emas, balki VISION_MODEL va OLLAMA_TEXT_MODEL'ni BIR XIL qilib
# qo'yish (server hech qachon model almashtirmaydi) to'g'riroq yechim.
OLLAMA_TIMEOUT_SECONDS = 240

# ── AI Advisor (xulosachi LLM) sozlamalari ───────────────────────────────
ADVISOR_CYCLE_SECONDS = 120   # har necha soniyada bir marta tahlil qiladi
ADVISOR_HISTORY_LIMIT = 30    # tahlil uchun oxirgi nechta hisobotni oladi

# ── Retention / tozalash sozlamalari ─────────────────────────────────────
# ESLATMA: avtomatik tozalash O'CHIRILGAN (main.py'da endi ishga
# tushirilmaydi) — ma'lumotlar HECH QACHON avtomatik o'chirilmaydi,
# doimiy saqlanadi. Quyidagi sozlamalar faqat agar kelajakda
# `py retention_cleanup.py` ni QO'LDA ishga tushirsangiz ishlatiladi.
RETENTION_DAYS = 30
RETENTION_CHECK_INTERVAL_SECONDS = 24 * 60 * 60







# Run qilish uchun:
#  py main.py   codni ishga tushiradi va doimiy ishlaydi (video yozish yo'q, faqat skrinshot + JSON oqimi)
#  http://localhost:5001/docs#/   api manzilini brauzerda ko'rish uchun

#  py external_api.py   alohida interfeysni ishga tushiradi 
# http://localhost:5001/   interfeysni brauzerda ko'rish uchun















