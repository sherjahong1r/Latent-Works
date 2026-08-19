"""
FastAPI'siz, to'g'ridan-to'g'ri slotting logikasini sinab ko'rish skripti.
Bu orqali avval algoritm to'g'ri ishlashini tasdiqlaymiz, keyin API ga ulaymiz.

Ishga tushirish (WMS_AI papkasi ichidan, PowerShell'da):
    cd C:/Users/Owner/Desktop/WMS_AI
    py -m wms_slotting.test_slotting_standalone
"""
from wms_slotting.tools import slotting_db
from wms_slotting.tools.slotting_engine import SlottingInput, resolve_effective_product_info, rank_bins


def run_test(warehouse_id: int, product_id: int, qty: float):
    print(f"\n=== TEST: warehouse_id={warehouse_id}, product_id={product_id}, qty={qty} ===")

    product_row = slotting_db.get_product(product_id)
    if not product_row:
        print(f"  XATO: product_id={product_id} topilmadi")
        return
    print(f"  Mahsulot: {product_row['name_uz']} (category_id={product_row['category_id']})")

    slot_input = SlottingInput(warehouse_id=warehouse_id, qty=qty, product_id=product_id)
    slot_input = resolve_effective_product_info(slot_input, product_row)

    zone = slotting_db.resolve_putaway_zone(
        warehouse_id, product_id, slot_input.category_id
    ) if not slot_input.qc_required else "QUARANTINE"
    print(f"  Tanlangan zona: {zone}")

    candidates = slotting_db.get_candidate_bins_with_utilization(warehouse_id, zone, product_id)
    print(f"  Nomzod binlar soni: {len(candidates)}")

    ranked = rank_bins(candidates, slot_input, top_n=5)
    if not ranked:
        print("  Hech qanday tavsiya topilmadi.")
        return

    print(f"\n  TAVSIYA #1: {ranked[0].bin_code} (ball={ranked[0].score}, sig'adi={ranked[0].fits_capacity})")
    for reason in ranked[0].reasons:
        print(f"    - {reason}")

    print("\n  Muqobil variantlar:")
    for r in ranked[1:]:
        print(f"    {r.bin_code} (ball={r.score}, sig'adi={r.fits_capacity})")

    if slot_input.warnings:
        print("\n  Ogohlantirishlar:")
        for w in slot_input.warnings:
            print(f"    ! {w}")


if __name__ == "__main__":
    # Haqiqiy warehouse_task'lardan ko'rgan real misollar bilan sinaymiz:
    run_test(warehouse_id=5, product_id=65522, qty=23)     # W5, id=3602 vazifasidan
    run_test(warehouse_id=1, product_id=65490, qty=55)     # W1, id=3604 vazifasidan
    run_test(warehouse_id=2, product_id=65523, qty=123)    # W2, id=3603 vazifasidan (PROD-WIP-001 default)