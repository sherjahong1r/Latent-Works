"""
erp.py — Enterprise Resource Planning (soddalashtirilgan).
MES'dan kelgan ishlab chiqarish hajmi asosida xomashyo xarajati,
energiya xarajati va taxminiy mahsulot qiymatini hisoblaydi.

Haqiqiy ERP (1C, SAP) bu yerga ombor, xodimlar, sotuv ma'lumotlarini ham qo'shadi.
"""

RAW_MATERIAL_COST_PER_UNIT = 4.2      # so'm/dollar shartli birlik
ENERGY_COST_PER_KWH = 0.09
OUTPUT_VALUE_PER_UNIT = 11.5


def calculate_costs(conn, batch_no: str, good_units: int, avg_heat_output_kw: float, hours: float):
    raw_material_cost = round(good_units * RAW_MATERIAL_COST_PER_UNIT, 2)
    energy_cost = round(avg_heat_output_kw * hours * ENERGY_COST_PER_KWH, 2)
    estimated_output_value = round(good_units * OUTPUT_VALUE_PER_UNIT, 2)

    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO erp_costs
               (batch_no, raw_material_cost, energy_cost, estimated_output_value)
               VALUES (%s, %s, %s, %s)""",
            (batch_no, raw_material_cost, energy_cost, estimated_output_value),
        )
    conn.commit()

    return {
        "raw_material_cost": raw_material_cost,
        "energy_cost": energy_cost,
        "estimated_output_value": estimated_output_value,
        "estimated_profit": round(estimated_output_value - raw_material_cost - energy_cost, 2),
    }
