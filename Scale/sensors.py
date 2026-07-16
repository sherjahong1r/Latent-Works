"""
sensors.py — real datchiklarning o'rnini bosuvchi simulyator.
Haqiqiy loyihada bu modul o'rniga Modbus/OPC UA orqali PLC'dan kiruvchi
qiymatlarni o'qiydigan kod turadi (masalan pymodbus kutubxonasi bilan).

11 ta datchik: harorat, bosim, issiqlik chiqishi, tezlik, pH, sarf,
sath, tebranish, namlik, kuchlanish, tok.
"""

import random
import math
import time


class SensorSimulator:
    def __init__(self):
        self._t = 0.0
        # Har bir datchikning boshlang'ich (normal) qiymati
        self.base = {
            "temperature": 65.0,   # °C
            "pressure": 8.0,       # bar
            "heat_output": 120.0,  # kW - reaksiya issiqligi
            "speed": 1450.0,       # rpm - aralashtirgich tezligi
            "ph": 7.0,
            "flow_rate": 12.0,     # m3/soat
            "level_pct": 60.0,     # % - reaktor to'ldirilganligi
            "vibration": 2.0,      # mm/s
            "humidity": 45.0,      # %
            "voltage": 380.0,      # V
            "current_a": 25.0,     # A
        }
        self._anomaly_countdown = 0

    def maybe_trigger_anomaly(self):
        """Vaqti-vaqti bilan (test uchun) sun'iy anomaliya yaratadi."""
        if random.random() < 0.01 and self._anomaly_countdown == 0:
            self._anomaly_countdown = random.randint(5, 15)

    def read_all(self) -> dict:
        """Barcha datchik qiymatlarini o'qiydi (simulyatsiya qiladi)."""
        self._t += 1
        self.maybe_trigger_anomaly()

        anomaly_boost = 1.0
        if self._anomaly_countdown > 0:
            anomaly_boost = 1.6   # haroratni/bosimni sun'iy oshiradi
            self._anomaly_countdown -= 1

        wave = math.sin(self._t / 20.0)

        values = {
            "temperature": self.base["temperature"] + wave * 8 * anomaly_boost + random.uniform(-1, 1),
            "pressure": self.base["pressure"] + wave * 2 * anomaly_boost + random.uniform(-0.3, 0.3),
            "heat_output": self.base["heat_output"] + wave * 15 * anomaly_boost + random.uniform(-3, 3),
            "speed": self.base["speed"] + random.uniform(-15, 15),
            "ph": self.base["ph"] + wave * 0.8 * anomaly_boost + random.uniform(-0.1, 0.1),
            "flow_rate": self.base["flow_rate"] + random.uniform(-1, 1),
            "level_pct": max(0, min(100, self.base["level_pct"] + wave * 5 + random.uniform(-1, 1))),
            "vibration": max(0, self.base["vibration"] + abs(wave) * 3 * anomaly_boost + random.uniform(-0.3, 0.3)),
            "humidity": self.base["humidity"] + random.uniform(-2, 2),
            "voltage": self.base["voltage"] + random.uniform(-4, 4),
            "current_a": self.base["current_a"] + random.uniform(-1.5, 1.5),
        }
        return {k: round(v, 2) for k, v in values.items()}


if __name__ == "__main__":
    sim = SensorSimulator()
    for _ in range(5):
        print(sim.read_all())
        time.sleep(0.5)
