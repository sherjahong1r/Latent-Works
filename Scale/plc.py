"""
plc.py — PLC boshqaruv mantiqini simulyatsiya qiladi.
Haqiqiy loyihada bu logika PLC ichida (Structured Text/Ladder) yoziladi
va millisekund darajasida mustaqil ishlaydi. Bu yerda o'sha mantiqni
Python funksiyasi sifatida qayta yaratamiz, shunda AI/SCADA qismini
tez sinab ko'rish mumkin.
"""

from config import LIMITS


def run_plc_logic(readings: dict, prev_state: dict | None = None) -> dict:
    """
    readings: sensors.py dan kelgan qiymatlar lug'ati
    prev_state: oldingi tsikldagi aktuator holatlari (gisterezis uchun)
    Qaytaradi: aktuator holatlari + alarm ro'yxati
    """
    prev_state = prev_state or {}
    temp = readings["temperature"]
    press = readings["pressure"]
    ph = readings["ph"]
    vib = readings["vibration"]

    fan_on = prev_state.get("fan_on", False)
    valve_open = prev_state.get("relief_valve_open", False)
    pump_on = prev_state.get("neutralizer_pump_on", False)
    agitator_on = prev_state.get("agitator_on", True)
    trip = False

    alarms = []

    # --- Sovutish ventilyatori (gisterezis bilan) ---
    if temp > LIMITS["temperature"]["warn"]:
        fan_on = True
    elif temp < LIMITS["temperature"]["warn"] - 5:
        fan_on = False

    # --- Bosim tushirish klapani ---
    if press > LIMITS["pressure"]["warn"]:
        valve_open = True
    elif press < LIMITS["pressure"]["warn"] - 2:
        valve_open = False

    # --- Neytrallovchi nasos ---
    pump_on = ph < LIMITS["ph_low"]["warn"] or ph > LIMITS["ph_high"]["warn"]

    # --- Ogohlantirishlar ---
    if temp > LIMITS["temperature"]["warn"]:
        alarms.append(("WARNING", f"Yuqori harorat: {temp}°C"))
    if press > LIMITS["pressure"]["warn"]:
        alarms.append(("WARNING", f"Yuqori bosim: {press} bar"))
    if pump_on:
        alarms.append(("WARNING", f"pH chegaradan chiqdi: {ph}"))
    if vib > LIMITS["vibration"]["warn"]:
        alarms.append(("WARNING", f"Yuqori tebranish: {vib} mm/s"))

    # --- Avariyaviy to'xtatish (TRIP) ---
    if (temp > LIMITS["temperature"]["trip"] or
            press > LIMITS["pressure"]["trip"] or
            ph < LIMITS["ph_low"]["trip"] or
            ph > LIMITS["ph_high"]["trip"] or
            vib > LIMITS["vibration"]["trip"]):
        trip = True
        agitator_on = False
        fan_on = True
        valve_open = True
        pump_on = True
        alarms.append(("TRIP", "AVARIYAVIY TO'XTATISH ishga tushdi"))

    return {
        "fan_on": fan_on,
        "relief_valve_open": valve_open,
        "neutralizer_pump_on": pump_on,
        "agitator_on": agitator_on,
        "trip_emergency": trip,
        "alarms": alarms,
    }
