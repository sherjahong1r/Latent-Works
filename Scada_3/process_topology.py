"""
process_topology.py — P&ID / jarayon topologiyasi (ixtiyoriy skelet).

MAQSAD: AI'ga faqat "raqamlar"ni emas, balki UNS URLARNING (uskunalar)
bir-biriga qanday ULANGANINI ham bilib olishga yordam berish. Masalan,
"P-102 dan keyin V-103, undan keyin E-104" kabi ma'lumot bo'lsa, AI:

  "P-102 chiqish bosimi pasayishi, E-104 kirish oqimi pasayishiga
   olib kelmoqda"

kabi SABAB-OQIBAT xulosalar chiqara oladi — bu oddiy raqam ko'rishdan
ancha kuchli.

QANDAY TO'LDIRISH KERAK:
Har bir uskuna/nuqta uchun quyidagicha yozing:

TOPOLOGY = {
    "P-204": {
        "description": "Asosiy nasos, filtrlash liniyasi",
        "upstream": ["Raw Water Pump 1"],      # bu uskunaga nima kiradi
        "downstream": ["Filter #1", "Filter #2"],  # bundan keyin nima keladi
    },
    "Filter #1": {
        "description": "1-filtr, oddiy qum filtri",
        "upstream": ["P-204"],
        "downstream": ["Clearwell Tank"],
    },
    ...
}

Kalitlar (masalan "P-204", "Filter #1") — SCADA ekranida AI ko'rgan
nomlar bilan MOS bo'lishi kerak (equipment_states / readings
kalitlaridagi nomlar bilan bir xil bo'lsa, AI ularni avtomatik
bog'lay oladi).

Bo'sh {} qoldirilsa — bu funksiya sokin o'tkazib yuboriladi, tizim
xatosiz ishlayveradi (config.py'dagi USE_PROCESS_TOPOLOGY=False qilib
ham butunlay o'chirish mumkin).
"""

# ── MUHIM ESLATMA — QIYMATLARNI TEKSHIRING ─────────────────────────────
# Quyidagi TOPOLOGY odatiy suv tozalash zavodi tuzilishi asosida
# (hozirgi demo SCADA ekranida ko'ringan "Filter #1"..."Filter #6",
# havo bosimi (backwash) va kimyoviy pompa elementlariga tayanib)
# TAXMINIY tarzda to'ldirilgan. Ishlatishdan oldin:
#
#   1. "Xom JSON ma'lumotlar" bo'limida (dashboard) haqiqiy
#      equipment_states / readings kalitlarini ko'ring.
#   2. Pastdagi kalit nomlarni O'SHA aniq nomlarga moslang (masalan,
#      ekranda "Filter 1" deb yozilgan bo'lsa, "Filter #1" emas
#      "Filter 1" deb o'zgartiring).
#   3. Agar nom mos kelmasa — tizim XATOGA tushmaydi, faqat Alarm
#      Correlation va topologiya asosidagi sabab-oqibat xulosalari
#      ishlamay qoladi (qolgan hamma narsa oldingidek ishlayveradi).

TOPOLOGY: dict = {
    "Raw Water Pump": {
        "description": "Xom suvni manbadan tozalash liniyasiga tortadigan asosiy nasos",
        "upstream": [],
        "downstream": ["Chemical Dosing Pump"],
    },
    "Chemical Dosing Pump": {
        "description": "Koagulyant/kimyoviy moddalarni suvga qo'shuvchi dozalash pompasi",
        "upstream": ["Raw Water Pump"],
        "downstream": ["Coagulation"],
    },
    "Coagulation": {
        "description": "Kimyoviy moddalar suv bilan aralashib, iflosliklarni yiriklashtiradigan bosqich",
        "upstream": ["Chemical Dosing Pump"],
        "downstream": ["Sedimentation"],
    },
    "Sedimentation": {
        "description": "Yiriklashgan zarrachalarning cho'kish (tindirish) havzasi",
        "upstream": ["Coagulation"],
        "downstream": [
            "Filter #1", "Filter #2", "Filter #3",
            "Filter #4", "Filter #5", "Filter #6",
        ],
    },
    "Filter #1": {"description": "1-qum filtri (parallel filtrlash liniyasi)", "upstream": ["Sedimentation"], "downstream": ["Clearwell Tank"]},
    "Filter #2": {"description": "2-qum filtri", "upstream": ["Sedimentation"], "downstream": ["Clearwell Tank"]},
    "Filter #3": {"description": "3-qum filtri", "upstream": ["Sedimentation"], "downstream": ["Clearwell Tank"]},
    "Filter #4": {"description": "4-qum filtri", "upstream": ["Sedimentation"], "downstream": ["Clearwell Tank"]},
    "Filter #5": {"description": "5-qum filtri", "upstream": ["Sedimentation"], "downstream": ["Clearwell Tank"]},
    "Filter #6": {"description": "6-qum filtri", "upstream": ["Sedimentation"], "downstream": ["Clearwell Tank"]},
    "Air Pressure": {
        "description": "Filtrlarni teskari yuvish (backwash) uchun havo bosimi tizimi — barcha filtrlarga bog'liq",
        "upstream": [],
        "downstream": [
            "Filter #1", "Filter #2", "Filter #3",
            "Filter #4", "Filter #5", "Filter #6",
        ],
    },
    "Clearwell Tank": {
        "description": "Filtrlangan toza suvning yig'ilish rezervuari",
        "upstream": [
            "Filter #1", "Filter #2", "Filter #3",
            "Filter #4", "Filter #5", "Filter #6",
        ],
        "downstream": ["Chlorination"],
    },
    "Chlorination": {
        "description": "Suvni dezinfeksiya qilish (xlorlash) bosqichi",
        "upstream": ["Clearwell Tank"],
        "downstream": ["Distribution Pump"],
    },
    "Distribution Pump": {
        "description": "Tayyor suvni tarmoqqa (iste'molchilarga) uzatuvchi nasos",
        "upstream": ["Chlorination"],
        "downstream": [],
    },
}


def topology_as_text() -> str:
    """TOPOLOGY lug'atini LLM promptiga qo'shish uchun o'qiladigan
    matn ko'rinishiga o'giradi. Bo'sh bo'lsa, bo'sh satr qaytaradi."""
    if not TOPOLOGY:
        return ""

    lines = ["=== JARAYON TOPOLOGIYASI (uskunalar bog'liqligi) ==="]
    for name, info in TOPOLOGY.items():
        desc = info.get("description", "")
        upstream = ", ".join(info.get("upstream", [])) or "—"
        downstream = ", ".join(info.get("downstream", [])) or "—"
        lines.append(
            f"- {name} ({desc}): oldidan -> {upstream}; keyin -> {downstream}"
        )
    return "\n".join(lines)
