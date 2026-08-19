"""
Operator javobini DETERMINISTIK (regex, LLM emas) tahlil qilish.

workflow_engine.py shu yerdagi parse_response() ni chaqiradi — har bir
qadam ("confirm", "quantity", "bin_code", "none") uchun qat'iy format
kutiladi. LLM bu yerda ISHLATILMAYDI — faqat qoidaviy (regex) tahlil,
xavfsizlik/determinism talabiga mos.

Qo'shimcha: miqdor so'z bilan aytilganda ham (masalan "o'ttiz besh kilo")
tushunish uchun oddiy o'zbekcha son-so'z lug'ati qo'shilgan.
"""
import re

_POSITIVE_WORDS = ["ha", "tasdiqlayman", "tasdiqlandi", "ho'p", "hop",
                    "bo'ldi", "boldi", "tayyor", "ok", "okay", "mayli"]
_NEGATIVE_WORDS = ["yo'q", "yoq", "bekor", "xato", "noto'g'ri", "notogri"]

# Oddiy o'zbekcha son-so'zlar — faqat operator ko'p ishlatadigan
# diapazon (0-99 + yuz/ming), murakkab grammatika emas.
_UNITS = {
    "nol": 0, "bir": 1, "ikki": 2, "uch": 3, "to'rt": 4, "tort": 4,
    "besh": 5, "olti": 6, "yetti": 7, "sakkiz": 8, "to'qqiz": 9, "toqqiz": 9,
}
_TENS = {
    "o'n": 10, "on": 10, "yigirma": 20, "o'ttiz": 30, "ottiz": 30,
    "qirq": 40, "ellik": 50, "oltmish": 60, "yetmish": 70,
    "sakson": 80, "to'qson": 90, "toqson": 90,
}
_SCALES = {"yuz": 100, "ming": 1000}


# Miqdordan keyin aytilishi mumkin bo'lgan birlik so'zlari — bular
# raqamdan keyin kelsa ham baribir "faqat son aytildi" deb hisoblanadi.
_TRAILING_UNIT_WORDS = {
    "kg", "kilo", "dona", "birlik", "litr", "metr", "tonna",
    "quti", "karobka", "sm", "gramm", "gr", "pachka",
}


def _words_to_number(text: str):
    """
    Matn BOSHIDAN boshlab ketma-ket son-so'zlarni yig'ishga urinadi
    (masalan "o'ttiz besh kilo" -> 35). Faqat matn boshidagi uzluksiz
    son-so'zlar hisobga olinadi, undan keyin faqat birlik so'zi
    (_TRAILING_UNIT_WORDS) kelishi mumkin — aks holda butunlay rad
    etiladi.

    MUHIM (xavfsizlik uchun): bu qat'iylik ataylab shunday — masalan
    "bir bir quruq bo'lmaydi" degan (STT xato tanigan) gapda "bir"
    so'zi 2 marta uchraydi, lekin bu ANIQ miqdor javobi EMAS, oddiy
    gap. Agar biz gapning istalgan joyidan son-so'z qidiraversak, bu
    kabi tasodifiy so'zlar noto'g'ri "miqdor tasdiqlandi" deb
    qabul qilinib, operator hali aytmagan miqdorni yozib yuborishi
    mumkin edi. Shu bois: FAQAT matn son-so'z bilan boshlansagina va
    undan keyin faqat birlik so'zi (yoki hech narsa) kelsagina qabul
    qilinadi.
    """
    tokens = re.findall(r"[a-zA-Zʻʼ'’]+", text.lower())
    if not tokens:
        return None

    total = 0
    current = 0
    idx = 0
    matched_any = False

    while idx < len(tokens):
        tok = tokens[idx]
        if tok in _UNITS:
            current += _UNITS[tok]
            matched_any = True
            idx += 1
        elif tok in _TENS:
            current += _TENS[tok]
            matched_any = True
            idx += 1
        elif tok in _SCALES:
            multiplier = _SCALES[tok]
            current = (current or 1) * multiplier
            total += current
            current = 0
            matched_any = True
            idx += 1
        else:
            break

    if not matched_any:
        return None

    total += current
    remaining = tokens[idx:]
    if remaining and not all(r in _TRAILING_UNIT_WORDS for r in remaining):
        # Son-so'zlardan keyin tanish bo'lmagan so'z(lar) kelyapti —
        # demak bu haqiqiy miqdor javobi emas, oddiy gap edi.
        return None

    return total


def _contains_word(text: str, word: str) -> bool:
    """
    So'zni MATNDA SO'Z SIFATIDA (chegaralari bilan) qidiradi — oddiy
    `word in text` EMAS. Sabab: masalan "ha" so'zini oddiy substring
    sifatida qidirsak, "qancha" so'zining ichidagi "...cha" qismi ham
    noto'g'ri "ha" (tasdiq) deb topilib qolar edi. \\b chegarasi bunday
    xatoni oldini oladi (harflar orasida emas, so'z chetida qidiradi).
    """
    return re.search(rf"\b{re.escape(word)}\b", text) is not None


def parse_response(expects: str, text: str) -> dict:
    """
    Operator aytgan (STT'dan kelgan yoki sinov uchun to'g'ridan-to'g'ri
    yozilgan) matnni kutilgan qadam turiga mos qat'iy tahlil qiladi.

    Qaytaradi: {"understood": bool, "value": ...}
    """
    t = (text or "").strip().lower()

    if expects == "confirm":
        if any(_contains_word(t, w) for w in _POSITIVE_WORDS):
            return {"understood": True, "value": True}
        if any(_contains_word(t, w) for w in _NEGATIVE_WORDS):
            return {"understood": True, "value": False}
        return {"understood": False, "value": None}

    if expects == "quantity":
        # 1-urinish: matn AYNAN raqam bilan boshlansa (masalan "30 dona").
        # MUHIM: bu ham _words_to_number bilan bir xil xavfsizlik
        # qoidasiga bo'ysunadi — raqam matn ichidagi ISTALGAN joyda
        # emas, faqat BOSHIDA bo'lsa qabul qilinadi. Aks holda masalan
        # "shunda 4 ta vazifa uchun yordam beraolasanmi" degan SAVOL
        # ichidagi "4" raqami noto'g'ri "miqdor javobi" deb qabul
        # qilinib, operator hali miqdorni aytmasdan turib vazifa
        # tasodifan "tugatilgan" deb belgilanib qolishi mumkin edi.
        m = re.match(r"\s*(\d+(?:[.,]\d+)?)", t)
        if m:
            remaining = t[m.end():].strip()
            remaining_tokens = re.findall(r"[a-zA-Zʻʼ'’]+", remaining)
            if not remaining_tokens or all(r in _TRAILING_UNIT_WORDS for r in remaining_tokens):
                val = float(m.group(1).replace(",", "."))
                return {"understood": True, "value": val}
        # 2-urinish: so'z bilan aytilgan son (masalan "o'ttiz besh kilo")
        word_val = _words_to_number(t)
        if word_val is not None and word_val > 0:
            return {"understood": True, "value": float(word_val)}
        return {"understood": False, "value": None}

    if expects == "bin_code":
        m = re.search(r"[a-zA-Z]\d{2}-?\d{2}-?\d{2}", t)
        if m:
            return {"understood": True, "value": m.group(0).upper()}
        return {"understood": False, "value": None}

    # "none" — kirish kutilmaydi, har doim tushunilgan hisoblanadi
    return {"understood": True, "value": None}