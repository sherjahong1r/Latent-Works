"""
Dinamik slotting API endpointlari.

    POST /wms/slotting            -> qo'lda kiritilgan ma'lumot bo'yicha tavsiya
    POST /wms/slotting/document   -> yuklangan hujjat/rasm bo'yicha tavsiya (OCR ulangan)
    GET  /wms/slotting/pending    -> bin kutayotgan ochiq PUTAWAY vazifalari
"""
import os
import tempfile

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

from wms_slotting.tools import slotting_db
from wms_slotting.tools.slotting_engine import (
    SlottingInput, resolve_effective_product_info, rank_bins,
)

try:
    from wms_agent.tools.ocr import extract_receipt_data
    _OCR_AVAILABLE = True
    _OCR_IMPORT_ERROR = None
except Exception as _e:  
    _OCR_AVAILABLE = False
    _OCR_IMPORT_ERROR = str(_e)

try:
    from wms_slotting.tools.address_extract import extract_destination_text
    _ADDRESS_OCR_AVAILABLE = True
except Exception:
    _ADDRESS_OCR_AVAILABLE = False

router = APIRouter(prefix="/wms/slotting", tags=["Dinamik slotting"])


# ---------------------------------------------------------------------
# So'rov / javob sxemalari
# ---------------------------------------------------------------------

class SlottingRequest(BaseModel):
    warehouse_id: int = Field(..., description="Ombor ID (masalan 1)")
    qty: float = Field(..., gt=0, description="Kelayotgan miqdor")
    product_id: int | None = Field(None, description="Agar mahsulot bazada bo'lsa")
    product_name: str | None = Field(None, description="Mahsulot nomi (product_id yo'q bo'lsa)")
    category_id: int | None = Field(None, description="Kategoriya (bazada yo'q bo'lsa qo'lda)")
    unit_weight_kg: float | None = Field(None, description="Birlik og'irligi, kg (bazada yo'q bo'lsa qo'lda)")
    qc_required: bool | None = Field(None, description="Sifat tekshiruvi/karantin kerakmi")
    lot_number: str | None = None
    expiry_date: str | None = None


class BinRecommendationOut(BaseModel):
    bin_id: int | None = None
    bin_code: str
    zone: str
    bin_type: str
    score: float
    reasons: list[str]
    fits_capacity: bool | None
    remaining_weight_kg: float | None


class SlottingResponse(BaseModel):
    resolved_zone: str
    recommended: BinRecommendationOut | None
    alternatives: list[BinRecommendationOut]
    warnings: list[str]


class DocumentSlottingItem(BaseModel):
    line_no: int | None
    material_name: str
    quantity: float
    uom: str | None
    lot: str | None
    matched_product_id: int | None
    matched_product_name: str | None
    slotting: SlottingResponse | None
    error: str | None


class DocumentSlottingResponse(BaseModel):
    supplier: str | None
    po_number: str | None
    delivery_date: str | None
    ocr_source: str | None
    resolved_warehouse_id: int | None
    warehouse_resolution_note: str | None
    items: list[DocumentSlottingItem]
    summary_text: str


# ---------------------------------------------------------------------
# Umumiy logika
# ---------------------------------------------------------------------

def _build_summary_text(supplier, po_number, warehouse_note, items: list) -> str:
    lines = []
    if supplier:
        lines.append(f"Ta'minotchi: {supplier}")
    if po_number:
        lines.append(f"Buyurtma: {po_number}")
    if warehouse_note:
        lines.append(warehouse_note)
    lines.append("")

    ok_count = sum(1 for it in items if it.slotting and it.slotting.recommended)
    err_count = len(items) - ok_count
    if err_count == 0:
        lines.append(f"Barcha {len(items)} ta tovar uchun joy topildi.")
    else:
        lines.append(f"{len(items)} ta tovardan {ok_count} tasiga joy topildi, {err_count} tasida muammo bor.")
    lines.append("")

    for it in items:
        qty_str = f"{it.quantity:g}"
        if it.uom:
            qty_str += f" {it.uom}"

        if it.slotting and it.slotting.recommended:
            rec = it.slotting.recommended
            line = f"{it.line_no or '-'}) {it.material_name} ({qty_str}) → {rec.bin_code} yacheykasiga joylashtiring"
            if it.slotting.alternatives:
                alt_codes = ", ".join(a.bin_code for a in it.slotting.alternatives[:2])
                line += f"\n   (band bo'lsa: {alt_codes})"
            if not it.matched_product_id:
                line += "\n   ! Mahsulot bazada topilmadi — yangi tovar sifatida standart hajmda hisoblandi."
        else:
            line = f"{it.line_no or '-'}) {it.material_name} ({qty_str}) → MUAMMO: {it.error or 'sabab noma’lum'}"

        lines.append(line)
        lines.append("")

    return "\n".join(lines).strip()


def _run_slotting(payload: SlottingRequest,
                    extra_reserved_weight: dict | None = None) -> SlottingResponse:
    product_row = None
    if payload.product_id is not None:
        product_row = slotting_db.get_product(payload.product_id)

    slot_input = SlottingInput(
        warehouse_id=payload.warehouse_id,
        qty=payload.qty,
        product_id=payload.product_id,
        product_name=payload.product_name,
        category_id=payload.category_id,
        unit_weight_kg=payload.unit_weight_kg,
        qc_required=payload.qc_required,
        lot_number=payload.lot_number,
        expiry_date=payload.expiry_date,
        extra_reserved_weight=extra_reserved_weight or {},
    )
    slot_input = resolve_effective_product_info(slot_input, product_row)

    if payload.product_id is not None:
        try:
            history_rows = slotting_db.get_product_placement_history(
                payload.product_id, payload.warehouse_id
            )
            slot_input.placement_history = {
                r["bin_id"]: r["placement_count"] for r in history_rows if r["bin_id"]
            }
            slot_input.velocity_class = slotting_db.get_product_velocity_class(
                payload.product_id, payload.warehouse_id
            )
        except Exception:
            pass

    if slot_input.qc_required:
        zone = "QUARANTINE"
        slot_input.warnings.append("qc_required=true bo'lgani uchun zona majburan QUARANTINE qilindi.")
    else:
        zone = slotting_db.resolve_putaway_zone(
            payload.warehouse_id, payload.product_id, slot_input.category_id
        )
        if zone is None:
            zone = "STANDARD"  
            slot_input.warnings.append("Maxsus putaway qoidasi topilmadi, standart zona (STANDARD) ishlatildi.")

    candidates = slotting_db.get_candidate_bins_with_utilization(
        payload.warehouse_id, zone, payload.product_id
    )
    
    if not candidates:
        zone = "GENERAL"
        candidates = slotting_db.get_candidate_bins_with_utilization(
            payload.warehouse_id, zone, payload.product_id
        )
    
    if not candidates:
        raise HTTPException(
            status_code=422,
            detail=f"warehouse_id={payload.warehouse_id} uchun bo'sh yacheykalar topilmadi.",
        )

    ranked = rank_bins(candidates, slot_input, top_n=5)
    if not ranked:
        raise HTTPException(status_code=422, detail="Bin tavsiyasini hisoblab bo'lmadi.")

    best = ranked[0]
    rest = ranked[1:]

    return SlottingResponse(
        resolved_zone=zone,
        recommended=BinRecommendationOut(**best.__dict__),
        alternatives=[BinRecommendationOut(**r.__dict__) for r in rest],
        warnings=slot_input.warnings,
    )


@router.post("", response_model=SlottingResponse)
def slotting_manual(payload: SlottingRequest) -> SlottingResponse:
    return _run_slotting(payload)


@router.post("/document", response_model=DocumentSlottingResponse)
async def slotting_document(
    file: UploadFile = File(...),
    warehouse_id: int | None = None,
) -> DocumentSlottingResponse:
    if not _OCR_AVAILABLE:
        raise HTTPException(status_code=500, detail="OCR moduli topilmadi.")

    suffix = os.path.splitext(file.filename or "")[1] or ".jpg"
    tmp_path = None
    try:
        file_bytes = await file.read()
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        ocr_result = extract_receipt_data(tmp_path)

        # AI serveri ishlamagan yoki xato qaytargan holatni tekshiramiz
        if not ocr_result or not isinstance(ocr_result, dict):
            raise HTTPException(status_code=502, detail="Sun'iy intellekt hujjatni o'qiy olmadi yoki server ishlamayapti.")
        
        if ocr_result.get("supplier") == "Aniqlanmadi" and not ocr_result.get("lines"):
            raw_text = ocr_result.get("raw_text", "")
            if "xatosi" in raw_text.lower() or "error" in raw_text.lower() or "timeout" in raw_text.lower():
                raise HTTPException(status_code=502, detail=f"AI server xatosi: {raw_text}")

        resolved_warehouse_id = warehouse_id
        warehouse_note = None
        if resolved_warehouse_id is None:
            if not _ADDRESS_OCR_AVAILABLE:
                raise HTTPException(status_code=422, detail="warehouse_id berilmadi.")
            dest_text = extract_destination_text(tmp_path)
            if not dest_text:
                raise HTTPException(status_code=422, detail="Hujjatda ombor manzili topilmadi.")
            candidates = slotting_db.match_warehouses_by_text(dest_text)
            if len(candidates) == 1:
                resolved_warehouse_id = candidates[0]["id"]
                warehouse_note = f"Ombor aniqlandi: \"{candidates[0]['name']}\""
            elif len(candidates) == 0:
                resolved_warehouse_id = 1  
                warehouse_note = "Manzil bo'yicha ombor topilmadi, default ombor (ID: 1) olindi."
            else:
                resolved_warehouse_id = candidates[0]["id"]
                warehouse_note = f"Bir nechta ombor topildi, birinchisi tanlandi: {candidates[0]['name']}"
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"OCR yoki server xatosi: {e}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

    lines = ocr_result.get("lines") or []
    if not lines:
        raise HTTPException(status_code=502, detail="AI serveri ishlamayapti yoki hujjatdan pozitsiyalar topilmadi. URL yoki Ollama holatini tekshiring.")

    items: list[DocumentSlottingItem] = []
    reserved_by_bin: dict = {}
    
    for line in lines:
        material_name = line.get("material_name") or "Nomaʼlum tovar"
        quantity = line.get("quantity")
        try:
            quantity = float(quantity) if quantity is not None else 1.0
        except (TypeError, ValueError):
            quantity = 1.0

        matched = slotting_db.find_product_by_name(material_name)
        if matched is None:
            matched = {}  

        uom_raw = (line.get("uom") or "").strip().lower()
        WEIGHT_UOM_TO_KG = {
            "kg": 1.0, "kgs": 1.0, "kilogram": 1.0, "kilogramm": 1.0,
            "g": 0.001, "gr": 0.001, "gramm": 0.001,
            "t": 1000.0, "tonna": 1000.0, "tn": 1000.0,
        }
        effective_qty = quantity
        effective_unit_weight = matched.get("unit_weight_kg")

        if uom_raw in WEIGHT_UOM_TO_KG:
            effective_qty = 1.0
            effective_unit_weight = quantity * WEIGHT_UOM_TO_KG[uom_raw]

        item_payload = SlottingRequest(
            warehouse_id=resolved_warehouse_id,
            qty=effective_qty,
            product_id=matched.get("id"),
            product_name=material_name,
            unit_weight_kg=effective_unit_weight,
            qc_required=matched.get("qc_required", False),
            lot_number=line.get("lot"),
        )

        try:
            slotting_result = _run_slotting(item_payload, extra_reserved_weight=reserved_by_bin)
            error = None
            if slotting_result.recommended and slotting_result.recommended.bin_id:
                bin_id = slotting_result.recommended.bin_id
                incoming_weight = effective_qty * (effective_unit_weight or 25.0)
                reserved_by_bin[bin_id] = reserved_by_bin.get(bin_id, 0) + incoming_weight
        except HTTPException as e:
            slotting_result = None
            error = str(e.detail)

        items.append(DocumentSlottingItem(
            line_no=line.get("line_no"),
            material_name=material_name,
            quantity=quantity,
            uom=line.get("uom"),
            lot=line.get("lot"),
            matched_product_id=matched.get("id"),
            matched_product_name=matched.get("name_uz"),
            slotting=slotting_result,
            error=error,
        ))

    return DocumentSlottingResponse(
        supplier=ocr_result.get("supplier"),
        po_number=ocr_result.get("po_number"),
        delivery_date=ocr_result.get("delivery_date"),
        ocr_source=ocr_result.get("_source"),
        resolved_warehouse_id=resolved_warehouse_id,
        warehouse_resolution_note=warehouse_note or "Ombor aniqlandi",
        items=items,
        summary_text=_build_summary_text(
            ocr_result.get("supplier"),
            ocr_result.get("po_number"),
            warehouse_note,
            items,
        ),
    )


@router.get("/pending")
def pending_putaway_tasks(warehouse_id: int, limit: int = 50):
    return slotting_db.get_open_putaway_tasks(warehouse_id, limit)