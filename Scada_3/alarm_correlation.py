"""
alarm_correlation.py — Alarm Correlation. YANGI MODUL.

MAQSAD: hozir har bir chegaradan chiqqan metrika (anomaly_detector.py
flag'i) ALOHIDA-ALOHIDA ko'rsatiladi. Lekin agar bir-biriga process
topology (process_topology.py) orqali ULANGAN bir nechta uskuna bir
vaqtning o'zida anomaliya bersa, bular ko'pincha BITTA asosiy
sababning oqibati bo'ladi (masalan, nasos yomonlashsa — undan keyingi
BARCHA uskunalar ham "anomaliya" ko'rsatadi).

Bu modul flag qilingan metrikalarni TOPOLOGY bo'yicha guruhlaydi va
har bir guruh uchun ENG YUQORI OQIMDAGI (eng "ustki", eng boshqa hech
narsaga bog'liq bo'lmagan) uskunani EHTIMOLIY SABAB-NOMZOD sifatida
belgilaydi.

CHEKLOV: bu oddiy grafik-yurish evristikasi — chinakam ehtimollik
hisob-kitobi (root cause probability) emas. TOPOLOGY bo'sh yoki
metrika nomlari mos kelmasa, har bir flag alohida guruh sifatida
qaytadi — hech narsa buzilmaydi, faqat guruhlash ishlamaydi.
"""

from process_topology import TOPOLOGY


def _topo_key_for_metric(metric_name: str) -> str | None:
    """metric_name (masalan 'Filter #1 Pressure') ichida TOPOLOGY'dagi
    qaysi uskuna nomi ('Filter #1') uchrayotganini topadi (moslashuvchan,
    aniq mos kelish shart emas)."""
    name_upper = metric_name.upper()
    for key in TOPOLOGY:
        if key.upper() in name_upper:
            return key
    return None


def _upstream_equipment(topo_key: str) -> list[str]:
    info = TOPOLOGY.get(topo_key)
    return info.get("upstream", []) if info else []


def _find_root(metric: str, metric_topo: dict, flagged: set[str], visited: set[str]) -> str:
    if metric in visited:
        return metric
    visited.add(metric)

    topo_key = metric_topo.get(metric)
    if not topo_key:
        return metric

    for up_equip in _upstream_equipment(topo_key):
        for other_metric, other_key in metric_topo.items():
            if other_key == up_equip and other_metric in flagged and other_metric not in visited:
                return _find_root(other_metric, metric_topo, flagged, visited)
    return metric


def correlate_alarms(anomaly_report: dict) -> list[dict]:
    """anomaly_report['flags'] ro'yxatini guruhlarga bo'ladi.
    Qaytadi: [{"root_cause_candidate", "affected_metrics", "confidence"}, ...]
    (eng ko'p a'zoli guruh birinchi)."""
    flags = anomaly_report.get("flags", [])
    if not flags:
        return []

    flagged = {f["metric"] for f in flags}

    if not TOPOLOGY:
        # Topologiya bo'sh — har biri o'z-o'zicha mustaqil guruh
        return [
            {"root_cause_candidate": f["metric"], "affected_metrics": [f["metric"]], "confidence": "past"}
            for f in flags
        ]

    metric_topo = {m: _topo_key_for_metric(m) for m in flagged}

    groups: dict[str, list[str]] = {}
    for m in flagged:
        root = _find_root(m, metric_topo, flagged, set())
        groups.setdefault(root, []).append(m)

    result = []
    for root, members in groups.items():
        confidence = "yuqori" if len(members) >= 3 else ("o'rta" if len(members) == 2 else "past")
        result.append({
            "root_cause_candidate": root,
            "affected_metrics": sorted(members),
            "confidence": confidence,
        })

    result.sort(key=lambda g: len(g["affected_metrics"]), reverse=True)
    return result


def correlation_as_text(groups: list[dict]) -> str:
    """LLM promptiga qo'shish uchun qisqa matn ko'rinishi."""
    if not groups:
        return "Alarm korrelyatsiyasi: hozircha bog'liq (bir-biriga ta'sir qiluvchi) anomaliyalar aniqlanmadi."

    lines = ["=== ALARM KORRELYATSIYASI (bog'liq anomaliyalar guruhi) ==="]
    for g in groups:
        others = [m for m in g["affected_metrics"] if m != g["root_cause_candidate"]]
        if others:
            lines.append(
                f"- Ehtimoliy sabab: {g['root_cause_candidate']} "
                f"(ishonch darajasi: {g['confidence']}) -> ta'sirlangan: {', '.join(others)}"
            )
        else:
            lines.append(f"- {g['root_cause_candidate']} (yakka anomaliya, bog'liq uskuna topilmadi)")
    return "\n".join(lines)
