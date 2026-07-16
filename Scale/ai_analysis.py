"""
ai_analysis.py — oddiy statistik AI tahlil qatlami.
Haqiqiy loyihada bu yerda scikit-learn (Isolation Forest) yoki
LLM-asosidagi "operator assistant" bo'lishi mumkin. Bu yerda tez
ishlaydigan va tushunarli z-score usuli qo'llanilgan:

z = (qiymat - o'rtacha) / standart_og'ish

|z| > 3 bo'lsa — statistik jihatdan g'ayrioddiy hodisa (anomaliya).
"""

import statistics
from database import fetch_history_for_sensor, insert_ai_insight

SENSORS_TO_WATCH = [
    "temperature", "pressure", "heat_output", "vibration", "ph"
]

Z_THRESHOLD = 3.0


def analyze(conn):
    """Har bir kuzatilayotgan datchik uchun anomaliya bor-yo'qligini tekshiradi."""
    findings = []
    for sensor in SENSORS_TO_WATCH:
        history = fetch_history_for_sensor(conn, sensor, limit=100)
        if len(history) < 20:
            continue  # statistikaga yetarli ma'lumot yo'q

        mean = statistics.mean(history)
        stdev = statistics.pstdev(history) or 0.0001
        latest = history[-1]
        z = (latest - mean) / stdev

        if abs(z) > Z_THRESHOLD:
            finding = f"{sensor}: anomaliya aniqlandi (qiymat={latest}, o'rtacha={round(mean,2)}, z={round(z,2)})"
            insert_ai_insight(conn, sensor, finding, round(z, 2))
            findings.append(finding)

    return findings


if __name__ == "__main__":
    from database import get_connection
    c = get_connection()
    print(analyze(c))
