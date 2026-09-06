# """
# ai_advisor.py — AI Advisor: matn LLM yordamida vision_reports
# tarixini, oxirgi metrikalar tendensiyasini, statistik anomaliya
# hisobotini va OLDINGI ZAVOD HOLATINI (Plant State Memory) birlashtirib,
# yangilangan xulosa + tavsiya + YANGI holat yozadi.

# MUHIM YANGILIK #1 — SINXRON ISHLASH: bu fayl endi o'zining mustaqil
# timer'i (ADVISOR_CYCLE_SECONDS) bilan emas, balki capture_pipeline.py
# tomonidan HAR BIR YANGI SKRINSHOT TAHLILIDAN KEYIN DARHOL chaqiriladi
# (`run_cycle()` funksiyasi orqali). Shunda JSON (xom ma'lumot) va AI
# xulosasi BIR VAQTDA, bir sikl ichida tayyor bo'ladi. Mustaqil
# `py ai_advisor.py` sifatida ishga tushirilsa, o'zining ADVISOR_CYCLE_SECONDS
# timer'i bilan ishlashda davom etadi (fallback/sinov uchun).

# MUHIM YANGILIK #2 — KENGROQ TARIXIY KONTEKST: faqat "eng so'nggi
# skrinshot" emas, balki oxirgi bir necha daqiqadagi HAR BIR metrikaning
# so'nggi bir necha nuqtasi ham promptga qo'shiladi — shunda AI xulosasi
# faqat bitta lahzaga emas, balki qisqa muddatli tendentsiyaga
# asoslanadi.

# MUHIM YANGILIK — PLANT STATE MEMORY: har siklda avval OLDINGI holatni
# (plant_state jadvalidan) o'qiydi, uni promptga qo'shadi, LLM esa buni
# hisobga olib YANGI holatni chiqaradi.

# Ishga tushirish (yakka o'zi, o'z timer'i bilan): py ai_advisor.py
# Yoki barchasi bitta jarayonda (capture bilan sinxron): py main.py
# """

# import json
# import time
# from datetime import datetime

# import requests

# from database import (
#     init_all_tables,
#     get_recent_metric_names,
#     get_recent_metric_series,
#     get_plant_state,
#     save_plant_state,
#     save_advisor_insight,
#     get_latest_vision_report,
# )
# from anomaly_detector import compute_anomaly_report, anomaly_report_as_text
# from process_topology import topology_as_text
# from config import (
#     OLLAMA_BASE_URL,
#     OLLAMA_TEXT_MODEL,
#     OLLAMA_TIMEOUT_SECONDS,
#     ADVISOR_CYCLE_SECONDS,
#     ANOMALY_LOOKBACK_MINUTES,
#     USE_PROCESS_TOPOLOGY,
# )

# ADVISOR_PROMPT_TEMPLATE = """Sen sanoat SCADA tizimini kuzatuvchi tajribali muhandis-maslahatchisan.

# === ENG SO'NGGI XOM HISOBOT (SCADA ekranidan, joriy lahza) ===
# {latest_report_json}

# === SO'NGGI METRIKALAR TARIXI (oxirgi bir necha nuqta, har bir o'lchov bo'yicha) ===
# {trends_text}

# === STATISTIK ANOMALIYA TAHLILI (avtomatik hisoblangan) ===
# {anomaly_text}

# === OLDINGI ZAVOD HOLATI (o'zingning avvalgi xulosang, xotira sifatida) ===
# {previous_state_json}
# {topology_section}
# VAZIFANG:
# 1. Yuqoridagi barcha ma'lumotni birlashtirib tahlil qil — FAQAT joriy
#    lahzaga emas, balki "SO'NGGI METRIKALAR TARIXI" bo'limidagi qisqa
#    muddatli tendentsiyaga ham tayan.
# 2. OLDINGI HOLAT bilan solishtir — nima o'zgargan, nima davom etayotganini aniqla.
# 3. Statistik anomaliya bo'lsa, uni alohida izohla (sensordagi xato bo'lishi
#    ham mumkinligini eslatib o't, agar shubhali bo'lsa).
# 4. Hozirgi holat qanchalik jiddiy ekanini bahola.
# 5. Operator uchun ANIQ, AMALIY tavsiya yoz.

# MUHIM TIL QOIDASI: "severity" FAQAT NORMAL/WARNING/CRITICAL (inglizcha).
# Boshqa barcha matn maydonlari FAQAT O'ZBEK TILIDA.

# Javobni FAQAT quyidagi JSON formatida qaytar, boshqa hech narsa yozma:

# {{
#   "severity": "<NORMAL yoki WARNING yoki CRITICAL>",
#   "summary": "<vaziyatning 1-2 gapli qisqa tavsifi — O'ZBEK TILIDA>",
#   "trend_analysis": "<tarixiy tendentsiya haqida topilma — O'ZBEK TILIDA>",
#   "recommendation": "<operator uchun aniq, amaliy tavsiya — O'ZBEK TILIDA>",
#   "trends": {{"<metrika nomi>": "<rising/falling/stable — ixtiyoriy, faqat aniq bo'lsa>"}},
#   "active_anomalies": ["<hozir faol deb hisoblagan anomaliyalar qisqa nomi>"],
#   "recommended_checks": ["<operator zudlik bilan tekshirishi kerak bo'lgan narsalar>"]
# }}

# Agar hammasi normal bo'lsa, "severity": "NORMAL" deb yoz, "active_anomalies"
# va "recommended_checks"ni bo'sh ro'yxat qoldir — xavf yo'q joyda sun'iy
# xavf o'ylab topma."""


# def _build_trends_text(lookback_minutes: int = ANOMALY_LOOKBACK_MINUTES, max_points: int = 8) -> str:
#     """Har bir raqamli metrikaning oxirgi bir necha nuqtasini
#     (vaqt=qiymat ko'rinishida) matn qilib beradi — AI'ga faqat "hozir"
#     emas, balki QISQA MUDDATLI TENDENSIYANI ham ko'rsatish uchun."""
#     names = get_recent_metric_names(lookback_minutes)
#     if not names:
#         return "(hali yetarli tarix yo'q — bu birinchi tahlil)"

#     lines = []
#     for name in sorted(names):
#         series = get_recent_metric_series(name, lookback_minutes)
#         if len(series) < 2:
#             continue
#         recent = series[-max_points:]
#         points_str = ", ".join(f"{ts.strftime('%H:%M:%S')}={value}" for ts, value in recent)
#         lines.append(f"- {name}: {points_str}")

#     return "\n".join(lines) if lines else "(hali yetarli tarix yo'q — bu birinchi tahlil)"


# def _build_prompt() -> tuple[str, dict]:
#     latest = get_latest_vision_report()
#     latest_report_json = json.dumps(latest["payload"], ensure_ascii=False, indent=2) if latest else "{}"

#     trends_text = _build_trends_text()

#     anomaly_report = compute_anomaly_report()
#     anomaly_text = anomaly_report_as_text(anomaly_report)

#     prev = get_plant_state()
#     previous_state_json = json.dumps(prev["state"], ensure_ascii=False, indent=2) if prev else "(hali yo'q — bu birinchi tahlil)"

#     topology_section = ""
#     if USE_PROCESS_TOPOLOGY:
#         topo_text = topology_as_text()
#         if topo_text:
#             topology_section = f"\n{topo_text}\n"

#     prompt = ADVISOR_PROMPT_TEMPLATE.format(
#         latest_report_json=latest_report_json,
#         trends_text=trends_text,
#         anomaly_text=anomaly_text,
#         previous_state_json=previous_state_json,
#         topology_section=topology_section,
#     )
#     return prompt, anomaly_report


# def ask_advisor(prompt: str) -> dict:
#     response = requests.post(
#         f"{OLLAMA_BASE_URL}/api/chat",
#         headers={"ngrok-skip-browser-warning": "true", "Content-Type": "application/json"},
#         json={
#             "model": OLLAMA_TEXT_MODEL,
#             "messages": [{"role": "user", "content": prompt}],
#             "stream": False,
#             "format": "json",
#             "options": {"temperature": 0.2},
#         },
#         timeout=OLLAMA_TIMEOUT_SECONDS,
#     )
#     response.raise_for_status()
#     raw = response.json()["message"]["content"]
#     return json.loads(raw)


# def run_cycle() -> dict | None:
#     """BITTA advisor siklini bajaradi: prompt tayyorlaydi, LLM'dan
#     xulosa oladi, bazaga (advisor_insights + plant_state) yozadi.

#     capture_pipeline.py buni HAR YANGI SKRINSHOT TAHLILIDAN KEYIN
#     to'g'ridan-to'g'ri chaqiradi (sinxron rejim). Mustaqil main()
#     funksiyasi ham buni o'z timer'i bilan chaqiradi (fallback rejim).

#     Agar hali umuman ma'lumot bo'lmasa, None qaytaradi (sikl
#     o'tkazib yuboriladi)."""
#     names = get_recent_metric_names(ANOMALY_LOOKBACK_MINUTES)
#     if not names:
#         print("Tahlil uchun yetarli tarix yo'q, kutilmoqda...")
#         return None

#     prompt, anomaly_report = _build_prompt()
#     insight = ask_advisor(prompt)

#     save_advisor_insight(
#         insight.get("severity", "UNKNOWN"),
#         insight.get("summary", ""),
#         insight.get("trend_analysis", ""),
#         insight.get("recommendation", ""),
#     )

#     new_state = {
#         "current_state": {"status": insight.get("severity", "UNKNOWN")},
#         "trends": insight.get("trends", {}),
#         "active_anomalies": insight.get("active_anomalies", []),
#         "statistical_anomaly_score": anomaly_report.get("anomaly_score", 0.0),
#         "recommended_checks": insight.get("recommended_checks", []),
#         "last_summary": insight.get("summary", ""),
#         "updated_at": datetime.now().isoformat(),
#     }
#     save_plant_state(new_state)

#     ts = datetime.now().strftime("%H:%M:%S")
#     print(f"\n[ADVISOR {ts}] XULOSA ({insight.get('severity')}):")
#     print(f"  {insight.get('summary')}")
#     if insight.get("trend_analysis"):
#         print(f"  Tendentsiya: {insight.get('trend_analysis')}")
#     if insight.get("recommendation"):
#         print(f"  Tavsiya: {insight.get('recommendation')}")

#     return insight


# def main():
#     """Mustaqil rejim (fallback): o'z timer'i (ADVISOR_CYCLE_SECONDS)
#     bilan ishlaydi. main.py orqali ishlatilganda BU FUNKSIYA
#     CHAQIRILMAYDI — buning o'rniga capture_pipeline.py har skrinshotdan
#     keyin to'g'ridan-to'g'ri run_cycle()ni chaqiradi (sinxron)."""
#     print(f"AI advisor MUSTAQIL rejimda ishga tushdi. Model: {OLLAMA_TEXT_MODEL!r}. "
#           f"Har {ADVISOR_CYCLE_SECONDS}s tahlil qiladi.")
#     while True:
#         try:
#             run_cycle()
#         except Exception as e:
#             print(f"[XATO] Advisor siklida muammo: {e}")
#         time.sleep(ADVISOR_CYCLE_SECONDS)


# if __name__ == "__main__":
#     init_all_tables()
#     main()









"""
ai_advisor.py — AI Advisor: matn LLM yordamida vision_reports
tarixini, oxirgi metrikalar tendensiyasini, statistik anomaliya
hisobotini va OLDINGI ZAVOD HOLATINI (Plant State Memory) birlashtirib,
yangilangan xulosa + tavsiya + YANGI holat yozadi.

MUHIM YANGILIK #1 — SINXRON ISHLASH: bu fayl endi o'zining mustaqil
timer'i (ADVISOR_CYCLE_SECONDS) bilan emas, balki capture_pipeline.py
tomonidan HAR BIR YANGI SKRINSHOT TAHLILIDAN KEYIN DARHOL chaqiriladi
(`run_cycle()` funksiyasi orqali). Shunda JSON (xom ma'lumot) va AI
xulosasi BIR VAQTDA, bir sikl ichida tayyor bo'ladi. Mustaqil
`py ai_advisor.py` sifatida ishga tushirilsa, o'zining ADVISOR_CYCLE_SECONDS
timer'i bilan ishlashda davom etadi (fallback/sinov uchun).

MUHIM YANGILIK #2 — KENGROQ TARIXIY KONTEKST: faqat "eng so'nggi
skrinshot" emas, balki oxirgi bir necha daqiqadagi HAR BIR metrikaning
so'nggi bir necha nuqtasi ham promptga qo'shiladi — shunda AI xulosasi
faqat bitta lahzaga emas, balki qisqa muddatli tendentsiyaga
asoslanadi.

MUHIM YANGILIK — PLANT STATE MEMORY: har siklda avval OLDINGI holatni
(plant_state jadvalidan) o'qiydi, uni promptga qo'shadi, LLM esa buni
hisobga olib YANGI holatni chiqaradi.

Ishga tushirish (yakka o'zi, o'z timer'i bilan): py ai_advisor.py
Yoki barchasi bitta jarayonda (capture bilan sinxron): py main.py
"""

import json
import time
from datetime import datetime

import llm_client
from database import (
    init_all_tables,
    get_recent_metric_names,
    get_recent_metric_series,
    get_plant_state,
    save_plant_state,
    save_advisor_insight,
    get_latest_vision_report,
)
from anomaly_detector import compute_anomaly_report, anomaly_report_as_text
from process_topology import topology_as_text
from config import (
    OLLAMA_TEXT_MODEL,
    TEXT_MAX_TOKENS,
    ADVISOR_CYCLE_SECONDS,
    ANOMALY_LOOKBACK_MINUTES,
    USE_PROCESS_TOPOLOGY,
)

ADVISOR_PROMPT_TEMPLATE = """Sen sanoat SCADA tizimini kuzatuvchi tajribali muhandis-maslahatchisan.

=== ENG SO'NGGI XOM HISOBOT (SCADA ekranidan, joriy lahza) ===
{latest_report_json}

=== SO'NGGI METRIKALAR TARIXI (oxirgi bir necha nuqta, har bir o'lchov bo'yicha) ===
{trends_text}

=== STATISTIK ANOMALIYA TAHLILI (avtomatik hisoblangan) ===
{anomaly_text}

=== OLDINGI ZAVOD HOLATI (o'zingning avvalgi xulosang, xotira sifatida) ===
{previous_state_json}
{topology_section}
VAZIFANG:
1. Yuqoridagi barcha ma'lumotni birlashtirib tahlil qil — FAQAT joriy
   lahzaga emas, balki "SO'NGGI METRIKALAR TARIXI" bo'limidagi qisqa
   muddatli tendentsiyaga ham tayan.
2. OLDINGI HOLAT bilan solishtir — nima o'zgargan, nima davom etayotganini aniqla.
3. Statistik anomaliya bo'lsa, uni alohida izohla (sensordagi xato bo'lishi
   ham mumkinligini eslatib o't, agar shubhali bo'lsa).
4. Hozirgi holat qanchalik jiddiy ekanini bahola.
5. Operator uchun ANIQ, AMALIY tavsiya yoz.

MUHIM QOIDA — FAQAT BERILGAN MA'LUMOTGA TAYAN (HAQIQATGA SODIQLIK):
- Yuqorida BERILMAGAN hech qanday voqea, tizim holati, xatolik turi
  yoki texnik tafsilotni O'YLAB TOPMA. Masalan, agar yuqorida ulanish
  xatosi, tarmoq holati yoki boshqa texnik infratuzilma haqida hech
  narsa YOZILMAGAN bo'lsa — bunday narsa haqida GAPIRMA.
  Faqat "readings", "trends", "anomaly" va "previous state" bo'limida
  aniq ko'rsatilgan raqamlar va holatlar asosida xulosa chiqar.
- Agar biror narsa noaniq yoki ma'lumot yetarli bo'lmasa — "aniq emas"
  yoki "ma'lumot yetarli emas" deb yoz, taxmin bilan to'ldirma.

MUHIM TIL QOIDASI: "severity" FAQAT NORMAL/WARNING/CRITICAL (inglizcha).
Boshqa barcha matn maydonlari FAQAT O'ZBEK TILIDA.

Javobni FAQAT quyidagi JSON formatida qaytar, boshqa hech narsa yozma:

{{
  "severity": "<NORMAL yoki WARNING yoki CRITICAL>",
  "summary": "<vaziyatning 1-2 gapli qisqa tavsifi — O'ZBEK TILIDA>",
  "trend_analysis": "<tarixiy tendentsiya haqida topilma — O'ZBEK TILIDA>",
  "recommendation": "<operator uchun aniq, amaliy tavsiya — O'ZBEK TILIDA>",
  "trends": {{"<metrika nomi>": "<rising/falling/stable — ixtiyoriy, faqat aniq bo'lsa>"}},
  "active_anomalies": ["<hozir faol deb hisoblagan anomaliyalar qisqa nomi>"],
  "recommended_checks": ["<operator zudlik bilan tekshirishi kerak bo'lgan narsalar>"]
}}

Agar hammasi normal bo'lsa, "severity": "NORMAL" deb yoz, "active_anomalies"
va "recommended_checks"ni bo'sh ro'yxat qoldir — xavf yo'q joyda sun'iy
xavf o'ylab topma."""


def _build_trends_text(lookback_minutes: int = ANOMALY_LOOKBACK_MINUTES, max_points: int = 4) -> str:
    """Har bir raqamli metrikaning oxirgi bir necha nuqtasini
    (vaqt=qiymat ko'rinishida) matn qilib beradi — AI'ga faqat "hozir"
    emas, balki QISQA MUDDATLI TENDENSIYANI ham ko'rsatish uchun.
    TEZLIK UCHUN QISQARTIRILDI: 8 nuqta o'rniga 4 nuqta."""
    names = get_recent_metric_names(lookback_minutes)
    if not names:
        return "(hali yetarli tarix yo'q — bu birinchi tahlil)"

    lines = []
    for name in sorted(names):
        series = get_recent_metric_series(name, lookback_minutes)
        if len(series) < 2:
            continue
        recent = series[-max_points:]
        points_str = ", ".join(f"{ts.strftime('%H:%M:%S')}={value}" for ts, value in recent)
        lines.append(f"- {name}: {points_str}")

    return "\n".join(lines) if lines else "(hali yetarli tarix yo'q — bu birinchi tahlil)"


def _build_prompt() -> tuple[str, dict]:
    latest = get_latest_vision_report()
    latest_report_json = json.dumps(latest["payload"], ensure_ascii=False, indent=2) if latest else "{}"

    trends_text = _build_trends_text()

    anomaly_report = compute_anomaly_report()
    anomaly_text = anomaly_report_as_text(anomaly_report)

    prev = get_plant_state()
    # TEZLIK UCHUN QISQARTIRILDI: to'liq JSON dump o'rniga qisqa xulosa.
    if prev and prev.get("state"):
        prev_summary = prev["state"].get("last_summary", "")
        previous_state_json = prev_summary if prev_summary else "(oldingi xulosa yo'q)"
    else:
        previous_state_json = "(hali yo'q — bu birinchi tahlil)"

    topology_section = ""
    if USE_PROCESS_TOPOLOGY:
        topo_text = topology_as_text()
        if topo_text:
            topology_section = f"\n{topo_text}\n"

    prompt = ADVISOR_PROMPT_TEMPLATE.format(
        latest_report_json=latest_report_json,
        trends_text=trends_text,
        anomaly_text=anomaly_text,
        previous_state_json=previous_state_json,
        topology_section=topology_section,
    )
    return prompt, anomaly_report


def ask_advisor(prompt: str) -> dict:
    return llm_client.chat_completion(
        model=OLLAMA_TEXT_MODEL, prompt=prompt, json_mode=True,
        max_tokens=TEXT_MAX_TOKENS, label="ADVISOR"
    )


def run_cycle() -> dict | None:
    """BITTA advisor siklini bajaradi: prompt tayyorlaydi, LLM'dan
    xulosa oladi, bazaga (advisor_insights + plant_state) yozadi.

    capture_pipeline.py buni HAR YANGI SKRINSHOT TAHLILIDAN KEYIN
    to'g'ridan-to'g'ri chaqiradi (sinxron rejim). Mustaqil main()
    funksiyasi ham buni o'z timer'i bilan chaqiradi (fallback rejim).

    Agar hali umuman ma'lumot bo'lmasa, None qaytaradi (sikl
    o'tkazib yuboriladi)."""
    names = get_recent_metric_names(ANOMALY_LOOKBACK_MINUTES)
    if not names:
        print("Tahlil uchun yetarli tarix yo'q, kutilmoqda...")
        return None

    prompt, anomaly_report = _build_prompt()
    insight = ask_advisor(prompt)

    save_advisor_insight(
        insight.get("severity", "UNKNOWN"),
        insight.get("summary", ""),
        insight.get("trend_analysis", ""),
        insight.get("recommendation", ""),
    )

    new_state = {
        "current_state": {"status": insight.get("severity", "UNKNOWN")},
        "trends": insight.get("trends", {}),
        "active_anomalies": insight.get("active_anomalies", []),
        "statistical_anomaly_score": anomaly_report.get("anomaly_score", 0.0),
        "recommended_checks": insight.get("recommended_checks", []),
        "last_summary": insight.get("summary", ""),
        "updated_at": datetime.now().isoformat(),
    }
    save_plant_state(new_state)

    ts = datetime.now().strftime("%H:%M:%S")
    print(f"\n[ADVISOR {ts}] XULOSA ({insight.get('severity')}):")
    print(f"  {insight.get('summary')}")
    if insight.get("trend_analysis"):
        print(f"  Tendentsiya: {insight.get('trend_analysis')}")
    if insight.get("recommendation"):
        print(f"  Tavsiya: {insight.get('recommendation')}")

    return insight


def main():
    """Mustaqil rejim (fallback): o'z timer'i (ADVISOR_CYCLE_SECONDS)
    bilan ishlaydi. main.py orqali ishlatilganda BU FUNKSIYA
    CHAQIRILMAYDI — buning o'rniga capture_pipeline.py har skrinshotdan
    keyin to'g'ridan-to'g'ri run_cycle()ni chaqiradi (sinxron)."""
    print(f"AI advisor MUSTAQIL rejimda ishga tushdi. Model: {OLLAMA_TEXT_MODEL!r}. "
          f"Har {ADVISOR_CYCLE_SECONDS}s tahlil qiladi.")
    while True:
        try:
            run_cycle()
        except Exception as e:
            print(f"[XATO] Advisor siklida muammo: {e}")
        time.sleep(ADVISOR_CYCLE_SECONDS)


if __name__ == "__main__":
    init_all_tables()
    main()