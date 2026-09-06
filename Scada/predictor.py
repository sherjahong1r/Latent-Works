# """
# predictor.py — 10/20/30 daqiqalik BASHORAT, MOSLASHUVCHAN interval bilan.

# QANDAY ISHLAYDI:
# 1. Har siklda oxirgi PREDICTION_LOOKBACK_MINUTES daqiqalik metrikalar
#    tarixini oladi.
# 2. Har bir metrika uchun ODDIY CHIZIQLI TREND (linear regression,
#    numpy.polyfit) hisoblab, 10/20/30 daqiqadan keyingi qiymatni
#    bashorat qiladi.
# 3. Bashoratlarni LLM'ga yuboradi — u buni o'zbek tilida tushunarli
#    xulosaga aylantiradi va umumiy xavf darajasini (LOW/MEDIUM/HIGH)
#    belgilaydi.
# 4. Natijani plant_predictions jadvaliga yozadi.
# 5. KEYINGI SIKL QACHON BO'LISHINI hisoblaydi: agar oxirgi nuqtalar
#    orasida katta (volatil) o'zgarish bo'lsa — interval qisqaradi
#    (tezroq qayta tekshiradi, PREDICTION_INTERVAL_MIN_SECONDS gacha).
#    Agar hammasi barqaror bo'lsa — interval cho'ziladi (kamroq
#    band qiladi, PREDICTION_INTERVAL_MAX_SECONDS gacha, ya'ni 15 daqiqa).

# Ishga tushirish (yakka o'zi): py predictor.py
# Yoki barchasi bitta jarayonda: py main.py
# """

# import json
# import time
# from datetime import datetime

# import numpy as np
# import requests

# from database import (
#     init_all_tables,
#     get_recent_metric_names,
#     get_recent_metric_series,
#     save_prediction,
# )
# from config import (
#     OLLAMA_BASE_URL,
#     OLLAMA_TEXT_MODEL,
#     OLLAMA_TIMEOUT_SECONDS,
#     PREDICTION_INTERVAL_MIN_SECONDS,
#     PREDICTION_INTERVAL_MAX_SECONDS,
#     PREDICTION_HORIZONS_MINUTES,
#     PREDICTION_LOOKBACK_MINUTES,
#     PREDICTION_MIN_POINTS,
#     PREDICTION_VOLATILITY_THRESHOLD,
# )

# PREDICTOR_PROMPT_TEMPLATE = """Sen sanoat jarayonini kuzatib, KELAJAKNI bashorat qiluvchi muhandissan.

# Quyida bir nechta metrikaning HOZIRGI qiymati va CHIZIQLI TREND asosida
# hisoblangan {horizons} daqiqadan keyingi bashorat qiymatlari berilgan:

# {predictions_json}

# VAZIFANG:
# 1. Bu raqamli bashoratlarni tahlil qil — qaysi metrika xavfli tomonga
#    ketayotganini top.
# 2. Umumiy xavf darajasini bahola: LOW (xavf yo'q), MEDIUM (kuzatish kerak),
#    yoki HIGH (tezkor chora kerak).
# 3. Operator uchun 1-2 gaplik, tushunarli, O'ZBEK TILIDA xulosa yoz —
#    "agar shu tendentsiya davom etsa, X daqiqadan keyin Y bo'lishi mumkin"
#    ko'rinishida.

# Javobni FAQAT quyidagi JSON formatida qaytar:

# {{
#   "risk_level": "<LOW yoki MEDIUM yoki HIGH>",
#   "summary": "<1-2 gaplik bashorat xulosasi — O'ZBEK TILIDA>"
# }}"""


# def _linear_forecast(series: list[tuple], horizons_minutes: list[int]) -> dict | None:
#     """series: [(ts, value), ...] eskisidan yangisiga qarab tartiblangan.
#     Chiziqli regressiya bilan har bir horizon uchun bashorat qiladi."""
#     if len(series) < PREDICTION_MIN_POINTS:
#         return None

#     t0 = series[0][0]
#     x = np.array([(ts - t0).total_seconds() / 60.0 for ts, _ in series])  # daqiqalarda
#     y = np.array([v for _, v in series])

#     if np.ptp(x) == 0:
#         return None

#     slope, intercept = np.polyfit(x, y, 1)
#     current_x = x[-1]
#     current_value = float(y[-1])

#     forecast = {}
#     for h in horizons_minutes:
#         predicted = slope * (current_x + h) + intercept
#         forecast[f"+{h}min"] = round(float(predicted), 3)

#     return {
#         "current": round(current_value, 3),
#         "slope_per_minute": round(float(slope), 5),
#         "forecast": forecast,
#     }


# def _compute_volatility(series: list[tuple]) -> float:
#     """Oxirgi nuqtalar orasidagi NISBIY o'zgarishning maksimalini
#     qaytaradi (0 = mutlaqo barqaror, katta qiymat = tez o'zgarmoqda)."""
#     if len(series) < 2:
#         return 0.0
#     values = [v for _, v in series]
#     max_rel_change = 0.0
#     for i in range(1, len(values)):
#         prev, cur = values[i - 1], values[i]
#         denom = abs(prev) if abs(prev) > 1e-9 else 1.0
#         rel_change = abs(cur - prev) / denom
#         max_rel_change = max(max_rel_change, rel_change)
#     return max_rel_change


# def run_prediction_cycle() -> int:
#     """Bitta bashorat siklini bajaradi, natijani bazaga yozadi va
#     KEYINGI siklgacha kutish kerak bo'lgan soniyalar sonini qaytaradi."""
#     names = get_recent_metric_names(PREDICTION_LOOKBACK_MINUTES)

#     per_metric_forecast = {}
#     max_volatility = 0.0

#     for name in names:
#         series = get_recent_metric_series(name, PREDICTION_LOOKBACK_MINUTES)
#         if len(series) < PREDICTION_MIN_POINTS:
#             continue

#         forecast = _linear_forecast(series, PREDICTION_HORIZONS_MINUTES)
#         if forecast:
#             per_metric_forecast[name] = forecast

#         volatility = _compute_volatility(series)
#         max_volatility = max(max_volatility, volatility)

#     if not per_metric_forecast:
#         print("[PREDICTOR] Bashorat uchun yetarli tarix yo'q, kutilmoqda...")
#         return PREDICTION_INTERVAL_MAX_SECONDS

#     # LLM'dan xulosa so'raymiz
#     horizons_str = ", ".join(str(h) for h in PREDICTION_HORIZONS_MINUTES)
#     prompt = PREDICTOR_PROMPT_TEMPLATE.format(
#         horizons=horizons_str,
#         predictions_json=json.dumps(per_metric_forecast, ensure_ascii=False, indent=2),
#     )

#     risk_level = "LOW"
#     summary = "Bashorat uchun yetarli ma'lumot, lekin xulosa olinmadi."
#     try:
#         response = requests.post(
#             f"{OLLAMA_BASE_URL}/api/chat",
#             headers={"ngrok-skip-browser-warning": "true", "Content-Type": "application/json"},
#             json={
#                 "model": OLLAMA_TEXT_MODEL,
#                 "messages": [{"role": "user", "content": prompt}],
#                 "stream": False,
#                 "format": "json",
#                 "options": {"temperature": 0.2},
#             },
#             timeout=OLLAMA_TIMEOUT_SECONDS,
#         )
#         response.raise_for_status()
#         raw = response.json()["message"]["content"]
#         result = json.loads(raw)
#         risk_level = result.get("risk_level", "LOW")
#         summary = result.get("summary", summary)
#     except Exception as e:
#         print(f"[PREDICTOR][XATO] LLM xulosasi olinmadi: {e}")

#     save_prediction(
#         interval_seconds=PREDICTION_INTERVAL_MAX_SECONDS,  # keyin yangilanadi, log uchun
#         risk_level=risk_level,
#         summary=summary,
#         details=per_metric_forecast,
#     )

#     ts = datetime.now().strftime("%H:%M:%S")
#     print(f"[PREDICTOR {ts}] Xavf darajasi: {risk_level}")
#     print(f"  {summary}")

#     # Adaptiv interval: volatillik chegaradan yuqori bo'lsa -> tezroq,
#     # aks holda -> maksimal (15 daqiqa) intervalgacha cho'ziladi.
#     if max_volatility <= 0:
#         next_interval = PREDICTION_INTERVAL_MAX_SECONDS
#     else:
#         ratio = min(1.0, max_volatility / PREDICTION_VOLATILITY_THRESHOLD)
#         # ratio=0 -> MAX interval, ratio>=1 -> MIN interval
#         span = PREDICTION_INTERVAL_MAX_SECONDS - PREDICTION_INTERVAL_MIN_SECONDS
#         next_interval = int(PREDICTION_INTERVAL_MAX_SECONDS - ratio * span)
#         next_interval = max(PREDICTION_INTERVAL_MIN_SECONDS, min(PREDICTION_INTERVAL_MAX_SECONDS, next_interval))

#     print(f"  (Volatillik: {max_volatility:.4f}, keyingi tekshiruv: {next_interval}s ichida)\n")
#     return next_interval


# def main():
#     print(f"predictor.py ishga tushdi. Interval {PREDICTION_INTERVAL_MIN_SECONDS}s - "
#           f"{PREDICTION_INTERVAL_MAX_SECONDS}s orasida moslashuvchan (volatillikka qarab).\n")

#     while True:
#         try:
#             next_interval = run_prediction_cycle()
#         except Exception as e:
#             print(f"[PREDICTOR][XATO] Sikl davomida muammo: {e}")
#             next_interval = PREDICTION_INTERVAL_MAX_SECONDS

#         time.sleep(next_interval)


# if __name__ == "__main__":
#     init_all_tables()
#     main()








"""
predictor.py — 10/20/30 daqiqalik BASHORAT, MOSLASHUVCHAN interval bilan.

QANDAY ISHLAYDI:
1. Har siklda oxirgi PREDICTION_LOOKBACK_MINUTES daqiqalik metrikalar
   tarixini oladi.
2. Har bir metrika uchun ODDIY CHIZIQLI TREND (linear regression,
   numpy.polyfit) hisoblab, 10/20/30 daqiqadan keyingi qiymatni
   bashorat qiladi.
3. Bashoratlarni LLM'ga yuboradi — u buni o'zbek tilida tushunarli
   xulosaga aylantiradi va umumiy xavf darajasini (LOW/MEDIUM/HIGH)
   belgilaydi.
4. Natijani plant_predictions jadvaliga yozadi.
5. KEYINGI SIKL QACHON BO'LISHINI hisoblaydi: agar oxirgi nuqtalar
   orasida katta (volatil) o'zgarish bo'lsa — interval qisqaradi
   (tezroq qayta tekshiradi, PREDICTION_INTERVAL_MIN_SECONDS gacha).
   Agar hammasi barqaror bo'lsa — interval cho'ziladi (kamroq
   band qiladi, PREDICTION_INTERVAL_MAX_SECONDS gacha, ya'ni 15 daqiqa).

Ishga tushirish (yakka o'zi): py predictor.py
Yoki barchasi bitta jarayonda: py main.py
"""

import json
import time
from datetime import datetime

import numpy as np

import llm_client
from database import (
    init_all_tables,
    get_recent_metric_names,
    get_recent_metric_series,
    save_prediction,
)
from config import (
    OLLAMA_TEXT_MODEL,
    TEXT_MAX_TOKENS,
    PREDICTION_INTERVAL_MIN_SECONDS,
    PREDICTION_INTERVAL_MAX_SECONDS,
    PREDICTION_HORIZONS_MINUTES,
    PREDICTION_LOOKBACK_MINUTES,
    PREDICTION_MIN_POINTS,
    PREDICTION_VOLATILITY_THRESHOLD,
)

PREDICTOR_PROMPT_TEMPLATE = """Sen sanoat jarayonini kuzatib, KELAJAKNI bashorat qiluvchi muhandissan.

Quyida bir nechta metrikaning HOZIRGI qiymati va CHIZIQLI TREND asosida
hisoblangan {horizons} daqiqadan keyingi bashorat qiymatlari berilgan:

{predictions_json}

VAZIFANG:
1. Bu raqamli bashoratlarni tahlil qil — qaysi metrika xavfli tomonga
   ketayotganini top.
2. Umumiy xavf darajasini bahola: LOW (xavf yo'q), MEDIUM (kuzatish kerak),
   yoki HIGH (tezkor chora kerak).
3. Operator uchun 1-2 gaplik, tushunarli, O'ZBEK TILIDA xulosa yoz —
   "agar shu tendentsiya davom etsa, X daqiqadan keyin Y bo'lishi mumkin"
   ko'rinishida.

MUHIM: FAQAT yuqorida berilgan raqamli bashorat qiymatlariga tayan.
Yuqorida yo'q hech qanday sabab, texnik nosozlik turi yoki voqeani
o'zingdan qo'shma — faqat sonlar asosida xulosa chiqar.

Javobni FAQAT quyidagi JSON formatida qaytar:

{{
  "risk_level": "<LOW yoki MEDIUM yoki HIGH>",
  "summary": "<1-2 gaplik bashorat xulosasi — O'ZBEK TILIDA>"
}}"""


def _linear_forecast(series: list[tuple], horizons_minutes: list[int]) -> dict | None:
    """series: [(ts, value), ...] eskisidan yangisiga qarab tartiblangan.
    Chiziqli regressiya bilan har bir horizon uchun bashorat qiladi."""
    if len(series) < PREDICTION_MIN_POINTS:
        return None

    t0 = series[0][0]
    x = np.array([(ts - t0).total_seconds() / 60.0 for ts, _ in series])  # daqiqalarda
    y = np.array([v for _, v in series])

    if np.ptp(x) == 0:
        return None

    slope, intercept = np.polyfit(x, y, 1)
    current_x = x[-1]
    current_value = float(y[-1])

    forecast = {}
    for h in horizons_minutes:
        predicted = slope * (current_x + h) + intercept
        forecast[f"+{h}min"] = round(float(predicted), 3)

    return {
        "current": round(current_value, 3),
        "slope_per_minute": round(float(slope), 5),
        "forecast": forecast,
    }


def _compute_volatility(series: list[tuple]) -> float:
    """Oxirgi nuqtalar orasidagi NISBIY o'zgarishning maksimalini
    qaytaradi (0 = mutlaqo barqaror, katta qiymat = tez o'zgarmoqda)."""
    if len(series) < 2:
        return 0.0
    values = [v for _, v in series]
    max_rel_change = 0.0
    for i in range(1, len(values)):
        prev, cur = values[i - 1], values[i]
        denom = abs(prev) if abs(prev) > 1e-9 else 1.0
        rel_change = abs(cur - prev) / denom
        max_rel_change = max(max_rel_change, rel_change)
    return max_rel_change


def run_prediction_cycle() -> int:
    """Bitta bashorat siklini bajaradi, natijani bazaga yozadi va
    KEYINGI siklgacha kutish kerak bo'lgan soniyalar sonini qaytaradi."""
    names = get_recent_metric_names(PREDICTION_LOOKBACK_MINUTES)

    per_metric_forecast = {}
    max_volatility = 0.0

    for name in names:
        series = get_recent_metric_series(name, PREDICTION_LOOKBACK_MINUTES)
        if len(series) < PREDICTION_MIN_POINTS:
            continue

        forecast = _linear_forecast(series, PREDICTION_HORIZONS_MINUTES)
        if forecast:
            per_metric_forecast[name] = forecast

        volatility = _compute_volatility(series)
        max_volatility = max(max_volatility, volatility)

    if not per_metric_forecast:
        print("[PREDICTOR] Bashorat uchun yetarli tarix yo'q, kutilmoqda...")
        return PREDICTION_INTERVAL_MAX_SECONDS

    # LLM'dan xulosa so'raymiz
    horizons_str = ", ".join(str(h) for h in PREDICTION_HORIZONS_MINUTES)
    prompt = PREDICTOR_PROMPT_TEMPLATE.format(
        horizons=horizons_str,
        predictions_json=json.dumps(per_metric_forecast, ensure_ascii=False, indent=2),
    )

    risk_level = "LOW"
    summary = "Bashorat uchun yetarli ma'lumot, lekin xulosa olinmadi."
    try:
        result = llm_client.chat_completion(
            model=OLLAMA_TEXT_MODEL, prompt=prompt, json_mode=True,
            max_tokens=TEXT_MAX_TOKENS, label="PREDICTOR"
        )
        risk_level = result.get("risk_level", "LOW")
        summary = result.get("summary", summary)
    except Exception as e:
        print(f"[PREDICTOR][XATO] LLM xulosasi olinmadi: {e}")

    save_prediction(
        interval_seconds=PREDICTION_INTERVAL_MAX_SECONDS,  # keyin yangilanadi, log uchun
        risk_level=risk_level,
        summary=summary,
        details=per_metric_forecast,
    )

    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[PREDICTOR {ts}] Xavf darajasi: {risk_level}")
    print(f"  {summary}")

    # Adaptiv interval: volatillik chegaradan yuqori bo'lsa -> tezroq,
    # aks holda -> maksimal (15 daqiqa) intervalgacha cho'ziladi.
    if max_volatility <= 0:
        next_interval = PREDICTION_INTERVAL_MAX_SECONDS
    else:
        ratio = min(1.0, max_volatility / PREDICTION_VOLATILITY_THRESHOLD)
        # ratio=0 -> MAX interval, ratio>=1 -> MIN interval
        span = PREDICTION_INTERVAL_MAX_SECONDS - PREDICTION_INTERVAL_MIN_SECONDS
        next_interval = int(PREDICTION_INTERVAL_MAX_SECONDS - ratio * span)
        next_interval = max(PREDICTION_INTERVAL_MIN_SECONDS, min(PREDICTION_INTERVAL_MAX_SECONDS, next_interval))

    print(f"  (Volatillik: {max_volatility:.4f}, keyingi tekshiruv: {next_interval}s ichida)\n")
    return next_interval


def main():
    print(f"predictor.py ishga tushdi. Interval {PREDICTION_INTERVAL_MIN_SECONDS}s - "
          f"{PREDICTION_INTERVAL_MAX_SECONDS}s orasida moslashuvchan (volatillikka qarab).\n")

    while True:
        try:
            next_interval = run_prediction_cycle()
        except Exception as e:
            print(f"[PREDICTOR][XATO] Sikl davomida muammo: {e}")
            next_interval = PREDICTION_INTERVAL_MAX_SECONDS

        time.sleep(next_interval)


if __name__ == "__main__":
    init_all_tables()
    main()