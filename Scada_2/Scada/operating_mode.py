"""
operating_mode.py — Operating Mode aniqlash (STARTUP / NORMAL / SHUTDOWN
/ MAINTENANCE). YANGI MODUL.

NEGA KERAK: zavod ishga tushayotganda yoki to'xtayotganda ko'rsatkichlar
tabiiy ravishda keskin o'zgaradi (bir nechta uskuna bir vaqtda ON/OFF
bo'ladi). Agar tizim buni "NORMAL rejim"dagi anomaliya deb hisoblasa —
anomaly_detector.py va ai_advisor.py SOXTA ogohlantirish berishi
mumkin. Bu modul hozirgi rejimni aniqlaydi, qolgan tizim shunga
moslashadi (anomaliya chegarasi vaqtincha yumshatiladi).

QANDAY ISHLAYDI (avtomatik):
  So'nggi OPERATING_MODE_LOOKBACK_REPORTS ta vision_reports orasida
  ENG BIRINCHI va ENG OXIRGI equipment_states'ni solishtiradi. Necha
  foiz uskuna holati o'zgarganini (change_ratio) hisoblaydi:
    - change_ratio past  -> NORMAL
    - change_ratio yuqori, asosan OFF->ON  -> STARTUP
    - change_ratio yuqori, asosan ON->OFF  -> SHUTDOWN

QO'LDA BOSHQARISH (MAINTENANCE): avtomatik aniqlash texnik xizmatni
bila olmaydi (hammasi to'xtagan bo'lishi mumkin, lekin bu anomaliya
emas — rejalashtirilgan ish). Operator buni external_api.py orqali
(/api/operating-mode, POST) qo'lda MAINTENANCE qilib qo'yishi mumkin —
bu belgilangan muddatgacha (manual_until) avtomatik aniqlashni
to'xtatib turadi, muddat tugagach avtomatik rejimga qaytadi.
"""

from datetime import datetime, timezone

from config import (
    OPERATING_MODE_LOOKBACK_REPORTS,
    OPERATING_MODE_CHANGE_RATIO,
    OPERATING_MODE_ANOMALY_RELAXATION,
)
from database import get_recent_vision_payloads, get_operating_mode, save_operating_mode

UTC = timezone.utc

_ON_WORDS = ("ON", "RUNNING", "OPEN", "ACTIVE", "FILTERING")
_OFF_WORDS = ("OFF", "STOPPED", "CLOSED", "STOP", "IDLE")


def _normalize(state) -> str:
    s = str(state or "").upper()
    if any(w in s for w in _ON_WORDS):
        return "ON"
    if any(w in s for w in _OFF_WORDS):
        return "OFF"
    return "UNKNOWN"


def _auto_detect() -> tuple[str, dict]:
    """(mode, detail) qaytaradi. Yetarli ma'lumot bo'lmasa -> NORMAL."""
    reports = get_recent_vision_payloads(OPERATING_MODE_LOOKBACK_REPORTS)
    if len(reports) < 2:
        return "NORMAL", {"reason": "Yetarli tarix yo'q, standart NORMAL"}

    first_payload = reports[0]["payload"] if isinstance(reports[0]["payload"], dict) else {}
    last_payload = reports[-1]["payload"] if isinstance(reports[-1]["payload"], dict) else {}
    first_equip = first_payload.get("equipment_states", {})
    last_equip = last_payload.get("equipment_states", {})

    all_names = set(first_equip) | set(last_equip)
    if not all_names:
        return "NORMAL", {"reason": "Uskuna holati (equipment_states) ma'lumoti yo'q"}

    turned_on, turned_off, changed = 0, 0, 0
    for name in all_names:
        before = _normalize(first_equip.get(name))
        after = _normalize(last_equip.get(name))
        if before == "UNKNOWN" or after == "UNKNOWN" or before == after:
            continue
        changed += 1
        if before == "OFF" and after == "ON":
            turned_on += 1
        elif before == "ON" and after == "OFF":
            turned_off += 1

    change_ratio = changed / len(all_names)
    detail = {
        "change_ratio": round(change_ratio, 3),
        "turned_on": turned_on,
        "turned_off": turned_off,
        "total_equipment": len(all_names),
        "window_reports": len(reports),
    }

    if change_ratio < OPERATING_MODE_CHANGE_RATIO:
        return "NORMAL", detail

    if turned_on >= turned_off:
        return "STARTUP", detail
    return "SHUTDOWN", detail


def update_operating_mode() -> dict:
    """Har advisor siklida (120s'da bir marta) chaqiriladi. Qo'lda
    o'rnatilgan rejim hali kuchda bo'lsa — uni saqlab qoladi, aks
    holda avtomatik aniqlashni ishga tushirib, bazani yangilaydi."""
    current = get_operating_mode()
    now = datetime.now(UTC)

    if current and current.get("source") == "manual" and current.get("manual_until"):
        if current["manual_until"] > now:
            return current  # qo'lda o'rnatilgan rejim hali kuchda

    mode, detail = _auto_detect()
    save_operating_mode(mode, source="auto", detail=detail, manual_until=None)
    return {"ts": now, "mode": mode, "source": "auto", "detail": detail, "manual_until": None}


def anomaly_threshold_multiplier(mode: str) -> float:
    """NORMAL bo'lmagan rejimlarda anomaliya chegarasini yumshatadi —
    startup/shutdown/maintenance paytidagi tabiiy keskin o'zgarishlar
    SOXTA xavf deb baholanmasligi uchun."""
    if mode in ("STARTUP", "SHUTDOWN", "MAINTENANCE"):
        return OPERATING_MODE_ANOMALY_RELAXATION
    return 1.0


def mode_as_text(mode_data: dict | None) -> str:
    """LLM promptiga qo'shish uchun qisqa matn ko'rinishi."""
    if not mode_data:
        return "Ishlash rejimi (Operating Mode): NORMAL (hali aniqlanmagan, standart qiymat)."
    mode = mode_data.get("mode", "NORMAL")
    source = mode_data.get("source", "auto")
    if mode == "NORMAL":
        return "Ishlash rejimi (Operating Mode): NORMAL (barqaror ish rejimi)."
    label = "OPERATOR TOMONIDAN QO'LDA O'RNATILGAN" if source == "manual" else "AVTOMATIK ANIQLANGAN"
    return (
        f"Ishlash rejimi (Operating Mode): {mode} ({label}) — bu rejimda "
        f"ko'rsatkichlarning keskin o'zgarishi TABIIY bo'lishi mumkin, "
        f"buni avtomatik ravishda jiddiy xavf deb baholashda EHTIYOT bo'l."
    )
