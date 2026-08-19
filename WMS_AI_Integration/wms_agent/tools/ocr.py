"""
Hujjat skanerlash — qwen3-vl:8b bilan.
Packing list, ASN, yorliq va boshqa hujjatlardan ma'lumot ajratish.

Qo'llab-quvvatlanadigan formatlar: .jpg, .jpeg, .png, .pdf
PDF fayllar avtomatik ravishda rasmga aylantiriladi (birinchi sahifa),
chunki vision model faqat rasm bilan ishlay oladi.
"""
import base64
import json
import difflib
from pathlib import Path
from shared.llm_client import ask_vision, ask_llm_fast
from shared.config import VISION_MODEL

PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def _pdf_first_page_to_png_bytes(pdf_path: str) -> bytes:
    """
    PDF faylning birinchi sahifasini PNG rasmga aylantiradi.
    PyMuPDF (fitz) kutubxonasi kerak: pip install pymupdf
    """
    import fitz  # PyMuPDF
    doc = fitz.open(pdf_path)
    if doc.page_count == 0:
        raise ValueError("PDF faylida sahifa yo'q")
    page = doc.load_page(0)
    # 2x kattalashtirish — matn aniqroq o'qilishi uchun
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
    png_bytes = pix.tobytes("png")
    doc.close()
    return png_bytes


def image_to_base64(file_path: str) -> str:
    """
    Fayl (rasm yoki PDF) ni vision model uchun base64 formatga aylantiradi.
    PDF bo'lsa — avval birinchi sahifasi rasmga aylantiriladi.
    """
    ext = Path(file_path).suffix.lower()

    if ext in PDF_EXTENSIONS:
        png_bytes = _pdf_first_page_to_png_bytes(file_path)
        return base64.b64encode(png_bytes).decode("utf-8")

    if ext not in IMAGE_EXTENSIONS:
        pass

    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _try_parse_json(raw: str):
    """```json ... ``` bilan o'ralgan bo'lsa tozalab, JSON'ga aylantirishga urinadi."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    return json.loads(cleaned.strip())


def extract_receipt_data(file_path: str) -> dict:
    """
    Qabul hujjatidan (packing list, ASN, yorliq — rasm yoki PDF)
    ma'lumot ajratish. JSON formatida qaytaradi.
    """
    img_b64 = image_to_base64(file_path)

    prompt = """Bu qabul hujjati (packing list, ASN yoki yorliq).

QATIY QOIDALAR:
1. Hujjatdagi HAR BIR qatorni (birinchisidan oxirigisigacha, birontasini
   ham tushirib qoldirmasdan) chiqar. Avval hujjatda nechta pozitsiya
   borligini sanab chiq, keyin JSON "lines" massivida aynan shuncha
   element bo'lishini tekshir.
2. Material nomini hujjatda YOZILGAN ANIQ SHAKLDA ber — harflarni
   boshqa alifboga o'girma (masalan kirill harflarini lotinga
   aylantirma), tarjima qilma, qisqartirma.

Quyidagi ma'lumotlarni JSON formatida ajrat:
{
  "supplier": "ta'minotchi nomi",
  "po_number": "PO raqami",
  "asn_number": "ASN raqami yoki null",
  "delivery_date": "yetkazib berish sanasi yoki null",
  "lines": [
    {
      "line_no": "satr raqami",
      "material_name": "material nomi (hujjatdagi original yozuvi, o'girmasdan)",
      "material_code": "material kodi yoki null",
      "quantity": "miqdor (raqam)",
      "uom": "o'lchov birligi",
      "lot": "lot/batch raqami yoki null",
      "expiry": "yaroqlilik muddati yoki null"
    }
  ],
  "total_weight": "umumiy og'irlik yoki null",
  "notes": "izohlar yoki null"
}
Faqat JSON qaytarish, boshqa matn yo'q."""

    raw = ask_vision(prompt, img_b64, model=VISION_MODEL)

    # AI serveri ishlamasa yoki xato qaytarsa, uni yashirmasdan xato sifatida chiqaramiz
    if not raw or "xatosi" in raw.lower() or "error" in raw.lower() or "timeout" in raw.lower():
        raise RuntimeError(f"Sun'iy intellekt (Vision) serveriga ulanishda xatolik: {raw}")

    try:
        return _try_parse_json(raw)
    except json.JSONDecodeError:
        pass

    retry_prompt = (
        "Quyidagi matndan supplier, material, miqdor ma'lumotlarini "
        "JSON formatida ajrat. Faqat JSON qaytar, boshqa matn yo'q:\n\n"
        f"{raw}\n\n"
        "Format:\n"
        '{"supplier": "...", "lines": '
        '[{"material_name": "...", "quantity": 0, "uom": "..."}]}'
    )
    retry_raw = ask_llm_fast(retry_prompt)

    if not retry_raw or "xatosi" in retry_raw.lower() or "error" in retry_raw.lower():
        raise RuntimeError(f"LLM server xatosi: {retry_raw}")

    try:
        return _try_parse_json(retry_raw)
    except json.JSONDecodeError:
        raise ValueError(f"Hujjatdan ma'lumotni JSON formatida o'qib bo'lmadi. AI javobi: {raw}")


def _normalize(text: str) -> str:
    """Solishtirish uchun matnni soddalashtirish: kichik harf, bo'sh joysiz."""
    if not text:
        return ""
    return "".join(ch for ch in text.lower().strip() if ch.isalnum())


def _find_best_match(target_name: str, candidates: list, used_indices: set,
                     threshold: float = 0.6):
    """
    target_name'ga eng o'xshash nomni candidates ro'yxatidan topadi
    (allaqachon ishlatilganlarini hisobga olmaydi). Material nomlaridagi
    kichik imlo farqlarini (OCR xatolari) chidamli qiladi.
    """
    target_norm = _normalize(target_name)
    if not target_norm:
        return None

    best_idx, best_score = None, 0.0
    for idx, cand in enumerate(candidates):
        if idx in used_indices:
            continue
        cand_norm = _normalize(cand.get("material_name") or cand.get("material_code") or "")
        if not cand_norm:
            continue
        score = difflib.SequenceMatcher(None, target_norm, cand_norm).ratio()
        if score > best_score:
            best_score, best_idx = score, idx

    if best_idx is not None and best_score >= threshold:
        return best_idx
    return None


def compare_with_po(ocr_data: dict, po_data: dict) -> dict:
    """
    OCR dan chiqqan ma'lumotni PO bilan MATERIAL NOMI bo'yicha
    taqqoslaydi (qator tartibi bo'yicha emas — shuning uchun OCR
    bitta qatorni o'tkazib yuborsa yoki tartib boshqacha bo'lsa ham
    to'g'ri ishlaydi).
    """
    differences = []

    # Supplier tekshirish
    if ocr_data.get("supplier") and po_data.get("supplier"):
        sup_score = difflib.SequenceMatcher(
            None, _normalize(ocr_data["supplier"]), _normalize(po_data["supplier"])
        ).ratio()
        if sup_score < 0.75: 
            differences.append({
                "field": "supplier",
                "po_value": po_data["supplier"],
                "doc_value": ocr_data["supplier"],
                "severity": "high"
            })

    po_lines = po_data.get("lines", [])
    doc_lines = ocr_data.get("lines", [])

    matched_po_indices = set()
    matched_doc_indices = set()

    for doc_idx, doc_line in enumerate(doc_lines):
        material = doc_line.get("material_name")
        po_idx = _find_best_match(material, po_lines, matched_po_indices)

        if po_idx is None:
            differences.append({
                "field": "extra_item",
                "material": material,
                "po_value": None,
                "doc_value": doc_line.get("quantity"),
                "severity": "high",
            })
            continue

        matched_po_indices.add(po_idx)
        matched_doc_indices.add(doc_idx)

        po_line = po_lines[po_idx]
        po_qty = po_line.get("ordered_qty")
        doc_qty = doc_line.get("quantity")

        if po_qty is not None and doc_qty is not None and po_qty != doc_qty:
            differences.append({
                "field": "quantity_mismatch",
                "material": po_line.get("material_name") or material,
                "po_value": po_qty,
                "doc_value": doc_qty,
                "diff": round(doc_qty - po_qty, 3),
                "severity": "medium",
            })

    for po_idx, po_line in enumerate(po_lines):
        if po_idx not in matched_po_indices:
            differences.append({
                "field": "missing_item",
                "material": po_line.get("material_name"),
                "po_value": po_line.get("ordered_qty"),
                "doc_value": 0,
                "severity": "high",
            })

    return {
        "has_differences": len(differences) > 0,
        "differences": differences,
        "missing_questions": [
            f"{d['field']} ({d.get('material','?')}): PO da {d['po_value']}, hujjatda {d['doc_value']}"
            for d in differences
        ]
    }
