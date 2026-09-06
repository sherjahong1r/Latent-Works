"""
anomaly_detector.py — Anomaly Detection qatlami.

HOZIRGI HOLAT: statistik baza (z-score) — o'z ML modelingiz hali
ulanmagan bo'lsa ham ishlaydigan, tezkor "xavfsizlik tarmog'i".

SIZNING ML MODELINGIZNI ULASH UCHUN:
Faqat `compute_anomaly_report()` funksiyasi ICHIDAGI mantiqni
almashtiring (yoki shu funksiyani to'liq qayta yozing) — funksiya
imzosi (kirish: joriy o'qishlar, chiqish: quyidagi struktura) bir xil
qolsa, capture_pipeline.py va ai_advisor.py hech narsani o'zgartirmasdan
ishlayveradi:

    {
        "anomaly_score": 0.0-1.0,
        "flags": [
            {"metric": "...", "z_score": ..., "current": ..., "mean": ..., "std": ...},
            ...
        ]
    }

Masalan, sklearn IsolationForest yoki boshqa modelingizni shu yerga
yuklab, `compute_anomaly_report()` ichida chaqirishingiz mumkin.
"""

import statistics

from config import (
    ANOMALY_LOOKBACK_MINUTES,
    ANOMALY_Z_THRESHOLD,
    ANOMALY_MIN_POINTS,
    ANOMALY_REQUIRE_CONSECUTIVE,
)
from database import get_recent_metric_series, get_recent_metric_names


def _z_score(current: float, history: list[float]) -> tuple[float, float, float]:
    """(z_score, mean, std) qaytaradi. std=0 bo'lsa (barcha qiymatlar
    bir xil), z_score=0 deb hisoblanadi (anomaliya emas)."""
    mean = statistics.fmean(history)
    std = statistics.pstdev(history) if len(history) > 1 else 0.0
    if std == 0:
        return 0.0, mean, std
    return (current - mean) / std, mean, std


def compute_anomaly_report(current_readings: dict | None = None, threshold_multiplier: float = 1.0) -> dict:
    """Bazadagi metric_history asosida joriy holatni statistik tahlil
    qiladi. `current_readings` berilmasa, har bir metrikaning o'zining
    so'nggi tarixiy nuqtasi "joriy" deb olinadi.

    `threshold_multiplier`: operating_mode.py'dan keladi — STARTUP/
    SHUTDOWN/MAINTENANCE paytida chegarani yumshatish (soxta
    ogohlantirishlarni kamaytirish) uchun. Odatiy holatda 1.0
    (o'zgarishsiz).

    MUHIM — BITTA KADR XATOSIDAN HIMOYA (ANOMALY_REQUIRE_CONSECUTIVE):
    bitta g'alati o'qish (vision xatosi yoki tasodifiy sensor sakrashi)
    darhol "anomaliya" deb belgilanmaydi. Buning o'rniga, SO'NGGI
    IKKALA nuqta ham chegaradan chiqqan bo'lsagina — bu "haqiqiy,
    davomiy anomaliya" deb hisoblanadi va Advisor/Predictor/Smena
    hisobotiga signal beriladi. Bu — soxta ogohlantirishlarni
    sezilarli kamaytiradi, chunki bitta xato kadr o'z-o'zidan butun
    ogohlantirish zanjirini ishga tushirmaydi."""
    effective_threshold = ANOMALY_Z_THRESHOLD * threshold_multiplier

    metric_names = get_recent_metric_names(ANOMALY_LOOKBACK_MINUTES)
    flags = []
    max_abs_z = 0.0

    for name in metric_names:
        series = get_recent_metric_series(name, ANOMALY_LOOKBACK_MINUTES)

        min_needed = max(ANOMALY_MIN_POINTS, 3) if ANOMALY_REQUIRE_CONSECUTIVE else ANOMALY_MIN_POINTS
        if len(series) < min_needed:
            continue

        values = [v for _, v in series]
        current = values[-1]

        if ANOMALY_REQUIRE_CONSECUTIVE and len(values) >= 3:
            previous = values[-2]
            baseline_history = values[:-2]  # ikkala so'nggi nuqtadan OLDINGI barqaror tarix

            z_current, mean, std = _z_score(current, baseline_history)
            z_previous, _, _ = _z_score(previous, baseline_history)

            abs_z_current = abs(z_current)
            max_abs_z = max(max_abs_z, abs_z_current)

            is_anomaly = abs_z_current >= effective_threshold and abs(z_previous) >= effective_threshold
        else:
            history = values[:-1] if len(values) > 1 else values
            z_current, mean, std = _z_score(current, history)
            abs_z_current = abs(z_current)
            max_abs_z = max(max_abs_z, abs_z_current)
            is_anomaly = abs_z_current >= effective_threshold

        if is_anomaly:
            flags.append({
                "metric": name,
                "z_score": round(z_current, 2),
                "current": round(current, 3),
                "mean": round(mean, 3),
                "std": round(std, 3),
            })

    # 0..1 oralig'iga normallashtirish (z=threshold -> 0.5, z=2*threshold -> ~1.0)
    anomaly_score = min(1.0, max_abs_z / (effective_threshold * 2)) if max_abs_z else 0.0

    return {
        "anomaly_score": round(anomaly_score, 3),
        "flags": sorted(flags, key=lambda f: abs(f["z_score"]), reverse=True),
        "threshold_used": round(effective_threshold, 2),
    }


def anomaly_report_as_text(report: dict) -> str:
    """LLM promptiga qo'shish uchun qisqa matn ko'rinishi."""
    threshold = report.get("threshold_used", ANOMALY_Z_THRESHOLD)

    if not report["flags"]:
        return f"Statistik anomaliya aniqlanmadi (anomaly_score={report['anomaly_score']}, chegara: ±{threshold})."

    lines = [f"Statistik anomaliya darajasi: {report['anomaly_score']} (0=normal, 1=eng yuqori)."]
    lines.append("Chegaradan chiqqan metrikalar:")
    for f in report["flags"]:
        lines.append(
            f"  - {f['metric']}: joriy={f['current']}, o'rtacha={f['mean']}, "
            f"z-score={f['z_score']} (chegara: ±{threshold})"
        )
    return "\n".join(lines)
