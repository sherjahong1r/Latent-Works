"""
main.py — barcha qatlamlarni ishga tushiradigan asosiy sikl.

Zanjir: Datchik -> PLC -> PostgreSQL (Historian) -> AI -> MES -> ERP

Ishga tushirishdan oldin:
  1. PostgreSQL o'rnatilgan va ishga tushirilgan bo'lishi kerak
  2. config.py dagi DB_CONFIG to'g'ri sozlangan bo'lishi kerak
  3. `createdb chem_scada` buyrug'i bilan baza yaratilgan bo'lishi kerak
  4. Birinchi marta ishga tushirishda jadvallar avtomatik yaratiladi

Ishga tushirish: python main.py
Alohida terminalda SCADA dashboard uchun: python scada_dashboard.py
"""

import time
import uuid

from config import SIMULATION_INTERVAL_SEC, AI_ANALYSIS_EVERY_N_CYCLES
from sensors import SensorSimulator
from plc import run_plc_logic
from database import (
    get_connection, init_db, insert_reading,
    insert_actuator_state, insert_alarm,
)
from ai_analysis import analyze
from mes import MESTracker
from erp import calculate_costs


def main():
    print("Bazani tekshirish va jadvallarni yaratish...")
    init_db()

    conn = get_connection()
    sim = SensorSimulator()
    mes = MESTracker(conn)

    batch_no = f"BATCH-{uuid.uuid4().hex[:6].upper()}"
    mes.start_batch(batch_no)
    print(f"Yangi partiya boshlandi: {batch_no}")

    actuator_state = {}
    cycle = 0

    try:
        while True:
            cycle += 1

            # 1) Datchik
            readings = sim.read_all()
            insert_reading(conn, readings)

            # 2) PLC
            plc_result = run_plc_logic(readings, actuator_state)
            actuator_state = plc_result
            insert_actuator_state(conn, plc_result)

            for severity, message in plc_result["alarms"]:
                insert_alarm(conn, severity, message)
                print(f"[{severity}] {message}")

            # 3) MES — har sikl "yaxshi birlik" deb hisoblanadi, agar avariya bo'lmasa
            mes.update(
                trip_emergency=plc_result["trip_emergency"],
                cycle_seconds=SIMULATION_INTERVAL_SEC,
                good_unit_produced=not plc_result["trip_emergency"],
            )

            # 4) AI — har N siklda bir marta
            if cycle % AI_ANALYSIS_EVERY_N_CYCLES == 0:
                findings = analyze(conn)
                if findings:
                    print("AI xulosalari:", findings)

            # 5) ERP — har 30 siklda bir marta xarajatni hisoblaydi
            if cycle % 30 == 0:
                costs = calculate_costs(
                    conn, batch_no,
                    good_units=cycle,
                    avg_heat_output_kw=readings["heat_output"],
                    hours=(cycle * SIMULATION_INTERVAL_SEC) / 3600,
                )
                print("ERP hisob-kitobi:", costs)

            print(f"[{cycle}] T={readings['temperature']} P={readings['pressure']} "
                  f"pH={readings['ph']} | Fan={plc_result['fan_on']} "
                  f"Valve={plc_result['relief_valve_open']} Trip={plc_result['trip_emergency']}")

            time.sleep(SIMULATION_INTERVAL_SEC)

    except KeyboardInterrupt:
        print("\nTo'xtatilmoqda, partiya yopilmoqda...")
        mes.close_batch()
        conn.close()


if __name__ == "__main__":
    main()
