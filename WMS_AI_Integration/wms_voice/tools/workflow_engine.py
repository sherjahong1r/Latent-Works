"""
Ovoz/skaner vazifa yordamchisi — DETERMINISTIK qadam mashinasi.

MUHIM: bu yerda erkin suhbat (open-ended chat) YO'Q. Har bir qadam aniq
bitta javob turini kutadi (ha/yo'q, raqam, bin kodi), va operator javobi
shu qat'iy formatga solishtiriladi (regex bilan, LLM emas). Agar mos
kelmasa — qayta so'raladi, 3 marta mos kelmasa — istisno (exception) deb
belgilanadi va odam chaqiriladi.

Bu — hujjatdagi "Speech + deterministic workflow" talabiga mos yozilgan.

XAVFSIZLIK: haqiqiy yozuv (WMS'ga tasdiqni yozish) BU YERDA AMALGA
OSHIRILMAYDI — tizim faqat operatorni skaner bilan tasdiqlashga
yo'naltiradi (guardrails: skaner tasdig'i — asosiy vakolatli dalil).
"""
import re
import uuid

from wms_voice.tools.response_parser import parse_response
from wms_voice.tools.qa_engine import answer_question


# ============================================================
# Vazifa shabloni — har bir vazifa turi uchun qadamlar ketma-ketligi
# ============================================================

def build_steps(task: dict) -> list:
    """
    Vazifa ma'lumotidan (mahsulot, bin, miqdor) qadamlar ro'yxatini quradi.
    task: {"task_id", "task_type", "product_name", "bin_code", "qty", "uom"}
    """
    if task["task_type"] == "PUTAWAY":
        return [
            {
                "id": "intro",
                "expects": "none",
                "text": f"Vazifa {task['task_id']}: {task['product_name']}, "
                        f"{task['qty']} {task['uom']} — {task['bin_code']} yacheykasiga joylashtiring."
            },
            {
                "id": "confirm_bin",
                "expects": "confirm",
                "text": f"{task['bin_code']} yacheykasiga yetib keldingizmi? Ha yoki yo'q deng."
            },
            {
                "id": "confirm_qty",
                "expects": "quantity",
                "text": "Necha birlik joylashtirdingiz? Raqamni ayting."
            },
            {
                "id": "done",
                "expects": "none",
                "text": "Rahmat. Endi barkodni skaner bilan o'qib, yozuvni tasdiqlang."
            },
        ]
    if task["task_type"] == "PICK":
        return [
            {
                "id": "intro",
                "expects": "none",
                "text": f"Vazifa {task['task_id']}: {task['bin_code']} dan "
                        f"{task['product_name']} — {task['qty']} {task['uom']} tering."
            },
            {
                "id": "confirm_bin",
                "expects": "confirm",
                "text": f"{task['bin_code']} yacheykasidamisiz? Ha yoki yo'q deng."
            },
            {
                "id": "confirm_qty",
                "expects": "quantity",
                "text": "Necha birlik terib oldingiz? Raqamni ayting."
            },
            {
                "id": "done",
                "expects": "none",
                "text": "Rahmat. Endi barkodni skaner bilan o'qib, yozuvni tasdiqlang."
            },
        ]
    # Noma'lum vazifa turi uchun oddiy 1 qadamli xabar
    return [{
        "id": "intro",
        "expects": "none",
        "text": f"Vazifa {task['task_id']}: {task.get('product_name', '')}."
    }]


# ============================================================
# Sessiya holati — xotirada saqlanadi (oddiy dict, in-memory)
# Eslatma: ishlab chiqarishda ko'p operator/ko'p server bo'lsa,
# buni Redis yoki DB'ga ko'chirish kerak. Hozircha bitta server
# uchun yetarli.
# ============================================================

_sessions = {}

MAX_RETRIES = 3


def _advance_through_none_steps(session) -> list:
    """
    step_index dan boshlab, 'kirish kutmaydigan' (expects='none') bosqichlar
    matnini yig'ib, birinchi HARAKAT talab qiladigan bosqichgacha (yoki
    oxirigacha) suradi. Masalan 'intro' xabari operatordan javob kutmaydi —
    darhol undan keyingi savolga o'tiladi, lekin ikkalasining matni
    birgalikda o'qiladi/ko'rsatiladi.
    """
    steps = session["steps"]
    texts = []
    idx = session["step_index"]
    while idx < len(steps) and steps[idx]["expects"] == "none":
        texts.append(steps[idx]["text"])
        idx += 1
    session["step_index"] = idx
    if idx >= len(steps):
        session["finished"] = True
    return texts


def start_session(task: dict) -> dict:
    steps = build_steps(task)
    session_id = str(uuid.uuid4())
    session = {
        "task": task,
        "steps": steps,
        "step_index": 0,
        "retry_count": 0,
        "finished": False,
        "exception": False,
    }
    _sessions[session_id] = session
    none_texts = _advance_through_none_steps(session)
    return _session_response(session_id, extra_texts=none_texts)


def respond(session_id: str, text: str) -> dict:
    session = _sessions.get(session_id)
    if not session:
        raise KeyError("Sessiya topilmadi yoki muddati tugagan")

    if session["finished"] or session["exception"]:
        return _session_response(session_id)

    steps = session["steps"]
    idx = session["step_index"]
    current_step = steps[idx]

    parsed = parse_response(current_step["expects"], text)

    if not parsed["understood"]:
        # Regex qat'iy kutilgan formatga mos kelmadi. Lekin bu operator
        # ODDIY SAVOL bergani uchun bo'lishi mumkin (masalan "bu vazifa
        # nega paydo bo'ldi" yoki "omborda yana nima bor"). Shuni tekshiramiz —
        # agar savol ombor/korxonaga oid bo'lsa, javob beramiz va SESSIYA
        # BOSQICHINI O'ZGARTIRMAYMIZ (operator keyin baribir kutilgan
        # javobni — ha/yo'q/raqamni — berishi kerak). Bu retry hisobiga
        # QO'SHILMAYDI, chunki bu operator xatosi emas.
        try:
            qa = answer_question(text)
        except Exception:
            qa = {"on_topic": False, "answer": None}

        if qa.get("on_topic"):
            return _session_response(
                session_id, understood=True, answered_question=True,
                extra_texts=[qa["answer"]],
            )

        session["retry_count"] += 1
        if session["retry_count"] >= MAX_RETRIES:
            session["exception"] = True
            return _session_response(
                session_id, understood=False,
                extra_texts=["Tushunolmadim. Operator/menejerga signal berildi."]
            )
        return _session_response(
            session_id, understood=False,
            extra_texts=["Tushunmadim, qayta ayting."]
        )

    # Tushunildi.
    session["retry_count"] = 0

    if current_step["id"] == "confirm_bin" and parsed["value"] is False:
        # Operator hali kerakli yacheykaga YETIB KELMAGAN ("yo'q" dedi).
        # BOSQICHNI OLDINGA SURMAYMIZ — aks holda tizim "necha birlik
        # joylashtirdingiz" deb so'rab qolardi, holbuki operator hali
        # yacheykaga yetib ham kelmagan (avval shunday bug bor edi).
        # Buning o'rniga xuddi shu savolni erkalab qayta beramiz —
        # operator yacheykaga yetib kelgach, qayta "ha" deydi.
        return _session_response(
            session_id, understood=True, parsed_value=False,
            extra_texts=["Xo'p, yacheykaga yetib kelganingizda qayta tasdiqlang."]
        )

    session["step_index"] += 1
    none_texts = _advance_through_none_steps(session)

    return _session_response(session_id, understood=True,
                              parsed_value=parsed["value"], extra_texts=none_texts)


def _session_response(session_id: str, understood: bool = True,
                       parsed_value=None, extra_texts: list = None,
                       answered_question: bool = False) -> dict:
    session = _sessions[session_id]
    steps = session["steps"]

    if session["finished"]:
        # Barcha bosqichlar tugagan — faqat yig'ilgan matnlarni ko'rsatamiz.
        # Agar bu safar hech qanday yangi matn yig'ilmagan bo'lsa (masalan
        # operator vazifa tugagandan KEYIN yana xabar yuborsa), bo'sh matn
        # TTS'ga yuborilmasligi uchun tayyor xabar qo'yamiz.
        prompt_text = " ".join(extra_texts or []) or "Bu vazifa allaqachon yakunlangan."
        step_id = steps[-1]["id"] if steps else "done"
        expects = "none"
    else:
        idx = session["step_index"]
        step = steps[idx]
        combined = list(extra_texts or [])
        combined.append(step["text"])
        prompt_text = " ".join(combined)
        step_id = step["id"]
        expects = step["expects"]

    return {
        "session_id": session_id,
        "task_id": session["task"]["task_id"],
        "step_id": step_id,
        "expects": expects,
        "prompt_text": prompt_text,
        "understood": understood,
        "answered_question": answered_question,
        "parsed_value": parsed_value,
        "finished": session["finished"],
        "exception": session["exception"],
        "retry_count": session["retry_count"],
    }








