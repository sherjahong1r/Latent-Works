"""
Hujjatdan tovar YETKAZILADIGAN/QABUL QILINADIGAN ombor manzilini alohida
o'qiydi. 1-topshiriqdagi asosiy OCR funksiyasiga (extract_receipt_data)
TEGILMAYDI — faqat bitta qo'shimcha, kichik vision so'rovi qo'shiladi,
chunki extract_receipt_data hozircha manzilni qaytarmaydi (faqat
supplier/PO/tovar qatorlarini o'qiydi).
"""
from wms_agent.tools.ocr import image_to_base64
from shared.llm_client import ask_vision
from shared.config import VISION_MODEL


def extract_destination_text(image_path: str) -> str | None:
    """
    Hujjatda qabul qiluvchi ombor manzili/nomi ko'rsatilgan bo'lsa,
    o'sha matnni qaytaradi. Topilmasa None qaytaradi.
    """
    img_b64 = image_to_base64(image_path)
    prompt = (
        "Bu hujjatda tovar YETKAZILADIGAN yoki QABUL QILINADIGAN ombor "
        "manzili yoki nomi ko'rsatilganmi (masalan 'Qabul qiluvchi ombor', "
        "'Yetkazish manzili', 'Ship to' kabi qatorda)? "
        "Agar bo'lsa, FAQAT o'sha manzil/nom matnini qaytar, boshqa hech "
        "narsa yozma. Agar bunday ma'lumot yo'q bo'lsa, FAQAT 'YOQ' deb yoz."
    )
    raw = ask_vision(prompt, img_b64, model=VISION_MODEL)
    raw = (raw or "").strip()
    if not raw or raw.upper().replace("'", "") in ("YOQ", "NO", "YO'Q"):
        return None
    return raw