"""
Dinamik slotting — asosiy skorlash (optimization) algoritmi.

Endi hisobga oladi:
  - sig'im (qolgan bo'sh joy)
  - masofa (travel_sequence) — aylanish tezligiga qarab og'irligi o'zgaradi
  - konsolidatsiya (shu mahsulot allaqachon shu binda bormi)
  - TARIX — bu mahsulot avval qaysi binlarga ko'proq joylashtirilgan
  - AYLANISH TEZLIGI (fast/medium/slow) — tez aylanadigan mahsulot uchun
    yaqinlik ko'proq ahamiyatli, sekin aylanadigan uchun kamroq
"""
from dataclasses import dataclass, field

DEFAULT_UNIT_WEIGHT_KG = 25.0

# Bazaviy og'irliklar
WEIGHT_CAPACITY = 0.35
WEIGHT_DISTANCE_BASE = 0.25
WEIGHT_AFFINITY = 0.15   # shu mahsulot hozir shu binda bor
WEIGHT_HISTORY = 0.25    # shu mahsulot AVVAL shu binga ko'p joylashtirilgan

# Aylanish tezligiga qarab masofa og'irligini ko'paytirish/kamaytirish
VELOCITY_DISTANCE_MULTIPLIER = {
    "fast": 1.6,    # tez aylanadigan — yaqinlik juda muhim
    "medium": 1.0,
    "slow": 0.5,    # sekin aylanadigan — yaqinlik unchalik muhim emas
}


@dataclass
class SlottingInput:
    warehouse_id: int
    qty: float
    product_id: int | None = None
    product_name: str | None = None
    category_id: int | None = None
    unit_weight_kg: float | None = None
    qc_required: bool | None = None
    lot_number: str | None = None
    expiry_date: str | None = None
    velocity_class: str = "medium"          # "fast" | "medium" | "slow"
    placement_history: dict = field(default_factory=dict)  # {bin_id: count}
    extra_reserved_weight: dict = field(default_factory=dict)  # {bin_id: kg} — shu hujjat ichida oldingi qatorlar band qilgan og'irlik
    warnings: list = field(default_factory=list)


@dataclass
class BinRecommendation:
    bin_code: str
    zone: str
    bin_type: str
    score: float
    reasons: list
    fits_capacity: bool | None
    remaining_weight_kg: float | None
    bin_id: int | None = None  # chaqiruvchi kod (router) session-capacity uchun ishlatadi


def resolve_effective_product_info(slot_input: SlottingInput, product_row) -> SlottingInput:
    if product_row:
        if slot_input.category_id is None:
            slot_input.category_id = product_row.get("category_id")
        if slot_input.unit_weight_kg is None:
            slot_input.unit_weight_kg = product_row.get("unit_weight_kg")
        if slot_input.qc_required is None:
            slot_input.qc_required = product_row.get("qc_required", False)
        if slot_input.product_name is None:
            slot_input.product_name = product_row.get("name_uz")

    if slot_input.qc_required is None:
        slot_input.qc_required = False

    if slot_input.unit_weight_kg is None:
        slot_input.warnings.append(
            f"Mahsulot og'irligi bazada ham, so'rovda ham berilmagan. "
            f"Standart qiymat ({DEFAULT_UNIT_WEIGHT_KG} kg) ishlatildi."
        )
        slot_input.unit_weight_kg = DEFAULT_UNIT_WEIGHT_KG

    return slot_input


def _normalize(values: list) -> dict:
    if not values:
        return {}
    lo, hi = min(values), max(values)
    if hi == lo:
        return {i: 0.5 for i in range(len(values))}
    return {i: (v - lo) / (hi - lo) for i, v in enumerate(values)}


def rank_bins(candidates: list, slot_input: SlottingInput, top_n: int = 5) -> list:
    """
    candidates — slotting_db.get_candidate_bins_with_utilization() natijasi.
    slot_input.extra_reserved_weight — bitta hujjat ichida oldingi
    qatorlar allaqachon "band qilgan" (lekin hali bazaga yozilmagan)
    og'irlik — shu bilan bir xil binni ketma-ket 3 marta to'ldirib
    yubormaslik ta'minlanadi.
    slot_input.placement_history — {bin_id: necha marta shu binga
    avval shu mahsulot qo'yilgan}.
    """
    incoming_weight = slot_input.qty * slot_input.unit_weight_kg
    distance_weight = WEIGHT_DISTANCE_BASE * VELOCITY_DISTANCE_MULTIPLIER.get(
        slot_input.velocity_class, 1.0
    )

    max_history = max(slot_input.placement_history.values(), default=0)

    enriched = []
    for c in candidates:
        bin_id = c.get("bin_id")
        max_w = c.get("max_weight_kg")
        used_w = float(c.get("used_weight_kg") or 0)
        reserved = float(slot_input.extra_reserved_weight.get(bin_id, 0))
        effective_used = used_w + reserved

        if max_w is not None:
            remaining = float(max_w) - effective_used
            fits = remaining >= incoming_weight
            capacity_ratio = max(0.0, remaining / float(max_w)) if float(max_w) > 0 else 0.0
        else:
            remaining = None
            fits = None
            capacity_ratio = 0.5

        travel = c.get("travel_sequence")
        history_count = slot_input.placement_history.get(bin_id, 0)
        history_score = (history_count / max_history) if max_history > 0 else 0.0

        enriched.append({
            **c,
            "remaining_weight_kg": remaining,
            "fits": fits,
            "capacity_ratio": capacity_ratio,
            "travel_sequence_val": travel if travel is not None else 10**6,
            "history_score": history_score,
            "history_count": history_count,
            "reserved_this_doc": reserved,
        })

    if not enriched:
        return []

    travel_vals = [e["travel_sequence_val"] for e in enriched]
    travel_norm = _normalize(travel_vals)

    scored = []
    for i, c in enumerate(enriched):
        distance_score = 1.0 - travel_norm[i]
        capacity_score = c["capacity_ratio"]
        affinity_score = 1.0 if c.get("has_same_product") else 0.0
        history_score = c["history_score"]

        score = (
            WEIGHT_CAPACITY * capacity_score
            + distance_weight * distance_score
            + WEIGHT_AFFINITY * affinity_score
            + WEIGHT_HISTORY * history_score
        )

        if c["fits"] is False:
            score -= 1.0

        reasons = []
        if c["history_count"] > 0:
            reasons.append(f"Bu mahsulot avval {c['history_count']} marta shu yerga joylashtirilgan (odatiy joyi)")
        if c.get("has_same_product"):
            reasons.append("Shu mahsulot hozir ham shu binda bor")
        if c["reserved_this_doc"] > 0:
            reasons.append(f"Shu hujjatdagi oldingi qatorlar bu bindan {c['reserved_this_doc']:.0f} kg joy band qilgan")
        if c["fits"] is True:
            reasons.append(f"Sig'imda joy yetarli (qolgan ~{c['remaining_weight_kg']:.0f} kg)")
        elif c["fits"] is False:
            reasons.append(
                f"DIQQAT: sig'im yetmaydi (qolgan ~{c['remaining_weight_kg']:.0f} kg, kerak {incoming_weight:.0f} kg)"
            )
        else:
            reasons.append("Bin sig'imi bazada ko'rsatilmagan — taxminiy baholandi")

        scored.append(BinRecommendation(
            bin_code=c["bin_code"], zone=c["zone"], bin_type=c["bin_type"],
            score=round(score, 4), reasons=reasons,
            fits_capacity=c["fits"], remaining_weight_kg=c["remaining_weight_kg"],
            bin_id=c.get("bin_id"),
        ))

    scored.sort(key=lambda r: r.score, reverse=True)
    return scored[:top_n]