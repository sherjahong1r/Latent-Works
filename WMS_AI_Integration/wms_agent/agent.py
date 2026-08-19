"""
WMS Agent — barcha biznes mantiq.

ESLATMA: Dinamik slotting BU YERDA EMAS — u alohida, real bazaga
ulangan xizmat (wms_slotting, port 8021) sifatida qurilgan. Bu yerdagi
eski mock-slotting kodi (wms_agent/tools/slotting.py, mock_data/...)
butunlay olib tashlandi, chunki u wms_slotting bilan almashtirilgan.
"""
from shared.llm_client import ask_llm, ask_llm_fast
from wms_agent.tools.wms_api import (
    fetch_purchase_order,
    fetch_inventory,
    fetch_tasks,
    fetch_bin_status,
    fetch_exceptions,
    create_receipt_draft
)
from wms_agent.tools.ocr import extract_receipt_data, compare_with_po
from wms_agent.prompts.wms_prompts import (
    SYSTEM_PROMPT,
    receipt_comparison_prompt,
    exception_explainer_prompt,
    voice_task_prompt
)


def _ocr_to_po_format(ocr_data: dict) -> dict:
    """
    OCR natijasini (extract_receipt_data formatida) PO formatiga
    o'giradi — shunda bir xil compare_with_po() funksiyasi ikkala
    holatda ham (real PO bilan yoki ikki hujjat bilan) ishlatiladi.
    """
    lines = []
    for i, line in enumerate(ocr_data.get("lines", []), start=1):
        lines.append({
            "line_no": line.get("line_no", i),
            "material_name": line.get("material_name"),
            "material_code": line.get("material_code"),
            "ordered_qty": line.get("quantity"),
            "uom": line.get("uom"),
        })
    return {
        "po_number": ocr_data.get("po_number"),
        "supplier": ocr_data.get("supplier"),
        "lines": lines,
    }


def process_receipt_document(image_path: str, po_doc_no: str = None,
                             po_image_path: str = None) -> dict:
    """
    Qabul hujjati yordamchisi — 2 xil rejimda ishlaydi:

    A) po_doc_no berilsa: PO ma'lumoti WMS'dan (real API yoki mock)
        olinadi va kelgan hujjat bilan solishtiriladi.
    B) po_image_path berilsa: ikkala hujjat ham (asl buyurtma +
        kelgan tovar hujjati) rasm sifatida yuklanadi, ikkalasi ham
        OCR qilinadi, keyin bir-biriga solishtiriladi — WMS'dagi
        saqlangan PO'ga bog'liq bo'lmasdan.

    Ikkalasi ham berilsa — B varianti ustuvor (aniqroq, chunki
    haqiqiy qog'oz hujjatdan olingan).
    """
    ocr_data = extract_receipt_data(image_path)
    if "error" in ocr_data:
        return {"error": f"OCR xatosi: {ocr_data['error']}", "raw": ocr_data.get("raw_text")}

    if po_image_path:
        po_ocr = extract_receipt_data(po_image_path)
        if "error" in po_ocr:
            return {"error": f"Buyurtma hujjati OCR xatosi: {po_ocr['error']}"}
        po_data = _ocr_to_po_format(po_ocr)
        po_source = "po_document_ocr"
    elif po_doc_no:
        po_data = fetch_purchase_order(po_doc_no)
        if "error" in po_data:
            return {"error": f"PO topilmadi: {po_data['error']}"}
        po_source = "wms_api"
    else:
        return {"error": "po_number yoki po_document berilishi shart"}

    differences = compare_with_po(ocr_data, po_data)
    explanation = _build_receipt_summary(po_data, differences)

    return {
        "type": "receipt_document",
        "po_number": po_doc_no or po_data.get("po_number"),
        "po_source": po_source,
        "po_data": po_data,
        "ocr_data": ocr_data,
        "differences": differences,
        "explanation": explanation,
        "status": "awaiting_operator_confirmation",
        "warning": "Operator tasdiqlamasdan WMS ga qayd etilmaydi."
    }


def _build_receipt_summary(po_data: dict, differences: dict) -> str:
    """
    Farqlar asosida ANIQ, Python tomonidan hisoblangan xulosa matni
    quradi — LLM'ga bog'liq emas, shuning uchun har doim to'g'ri.
    """
    diffs = differences.get("differences", [])
    mismatches = [d for d in diffs if d["field"] == "quantity_mismatch"]
    missing = [d for d in diffs if d["field"] == "missing_item"]
    extra = [d for d in diffs if d["field"] == "extra_item"]
    supplier_diff = [d for d in diffs if d["field"] == "supplier"]

    total_lines = len(po_data.get("lines", []))
    ok_count = total_lines - len(mismatches) - len(missing)

    lines = []
    if not diffs:
        lines.append(f"✅ Barcha {total_lines} ta pozitsiya to'liq va aniq mos keldi.")
    else:
        lines.append(f"{total_lines} ta pozitsiyadan {ok_count} tasi mos keldi, {len(diffs)} tasida muammo bor:")
        for d in mismatches:
            lines.append(f"  • {d['material']}: buyurtma qilingan {d['po_value']}, kelgan {d['doc_value']} (farq {d['diff']:+g})")
        for d in missing:
            lines.append(f"  • {d['material']}: buyurtmada bor edi, lekin hujjatda umuman yo'q")
        for d in extra:
            lines.append(f"  • {d['material']}: hujjatda bor, lekin buyurtmada yo'q edi (ortiqcha)")
        for d in supplier_diff:
            lines.append(f"  • Ta'minotchi nomi mos kelmadi: buyurtmada \"{d['po_value']}\", hujjatda \"{d['doc_value']}\"")

    lines.append("")
    if diffs:
        lines.append("XULOSA: To'liq emas — operator farqlarni ko'rib chiqib, tasdiqlashi kerak.")
    else:
        lines.append("XULOSA: To'liq mos — operator tasdiqlasa, qabul drafti yaratiladi.")

    return "\n".join(lines)


def confirm_receipt(po_doc_no: str, lines: list) -> dict:
    """Operator 'Tasdiqlash' bosganda chaqiriladi. Real WMS API ga draft yuboradi."""
    return create_receipt_draft(po_doc_no, lines)


def explain_warehouse_exception(task_id: str) -> dict:
    """Ombor istisnolari copiloti."""
    tasks = fetch_tasks()
    task = next((t for t in tasks if t["task_id"] == task_id), None)
    if not task:
        return {"error": f"{task_id} topilmadi"}

    bin_id = task.get("from_bin") or task.get("to_bin")
    bin_info = fetch_bin_status(bin_id) if bin_id else {}
    material = task.get("material_code")
    inventory = fetch_inventory(material_code=material) if material else []

    prompt = exception_explainer_prompt(task, bin_info, inventory)
    explanation = ask_llm(prompt, system=SYSTEM_PROMPT)

    return {
        "type": "warehouse_exception",
        "task_id": task_id,
        "explanation": explanation,
        "task_data": task,
        "bin_info": bin_info,
        "alternative_locations": bin_info.get("alternative_bins", [])
    }


def answer_voice_question(question: str, operator_id: str = None) -> dict:
    """Ovozli vazifa yordamchisi (moslashuvchan, ortiqcha qattiq cheklovlarsiz)."""
    inventory = fetch_inventory()
    tasks = fetch_tasks(operator_id=operator_id) if operator_id else fetch_tasks()

    prompt = voice_task_prompt(question, inventory, tasks)
    
    # Model xatolik bermasligi uchun qisqa va tezkor chaqiruv,
    # shuningdek xatoliklarni xavfsiz ushlash mexanizmi bilan
    try:
        answer = ask_llm_fast(prompt, system=SYSTEM_PROMPT)
        if not answer or "xatosi" in answer.lower():
            answer = "Kechirasiz, so'rovingizni qayta ishlashda vaqtinchalik xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring."
    except Exception as e:
        answer = f"Kechirasiz, AI xizmatiga ulanishda xatolik yuz berdi: {str(e)}"

    return {
        "type": "voice_answer",
        "question": question,
        "answer": answer,
        "speak_text": answer
    }


def get_exceptions_summary() -> dict:
    """Joriy istisnolar ro'yxati."""
    exceptions = fetch_exceptions()
    if not exceptions:
        return {"type": "exceptions_summary", "message": "Hozirda istisno yo'q.", "exceptions": []}

    prompt = f"""
Quyidagi ombor istisnolari ro'yxatini qisqa xulosa qil:
{exceptions}
Har biri uchun: nima muammo, kim hal qiladi, qanchalik shoshilinch.
"""
    summary = ask_llm_fast(prompt, system=SYSTEM_PROMPT)
    return {
        "type": "exceptions_summary",
        "count": len(exceptions),
        "summary": summary,
        "exceptions": exceptions
    }