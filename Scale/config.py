"""
Loyiha sozlamalari.
Haqiqiy muhitda bu qiymatlarni .env fayl yoki environment variable orqali olish tavsiya etiladi.
"""

DB_CONFIG = {
    "host": "localhost",
    "port": 5433,        # <-- BU YERDA 5432 EMAS, 5433 BO'LISHI KERAK
    "dbname": "chem_scada",
    "user": "postgres",
    "password": "jahongir",
}

# PLC ogohlantirish va avariya chegaralari (operator SCADA orqali o'zgartirishi mumkin)
LIMITS = {
    "temperature": {"warn": 90.0, "trip": 100.0},
    "pressure":    {"warn": 18.0, "trip": 20.0},
    "ph_low":      {"warn": 5.5,  "trip": 4.0},
    "ph_high":     {"warn": 8.5,  "trip": 10.0},
    "vibration":   {"warn": 6.0,  "trip": 9.0},
}

SIMULATION_INTERVAL_SEC = 2      # har necha soniyada bitta o'lchov
AI_ANALYSIS_EVERY_N_CYCLES = 15  # ichki z-score tahlili har 15 sikldan keyin ishga tushadi

# --- AI hisobot moduli (ai_reporter.py) sozlamalari ---
import os
from dotenv import load_dotenv

load_dotenv()  # .env fayldan o'qiydi (agar mavjud bo'lsa)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
AI_MODEL = "claude-sonnet-4-6"

AI_REPORT_INTERVAL_SEC = 30      # AI hisobotini har necha soniyada tuzish/jo'natish

# Tashqi API manzili — bu yerga o'zingizning qabul qiluvchi serveringiz URL'ini yozing.
# Hozircha namuna sifatida httpbin.org ishlatilgan (u yuborilgan JSON'ni qaytarib ko'rsatadi,
# real qabul qiluvchi server emas — faqat sinov uchun).
EXTERNAL_API_ENDPOINT = os.getenv("EXTERNAL_API_ENDPOINT", "https://httpbin.org/post")
