"""
WMS Agent FastAPI server.
Ishga tushirish: uvicorn wms_agent.main:app --port 8020 --reload

ESLATMA: Dinamik slotting BU YERDA EMAS — u alohida xizmat sifatida
(wms_slotting, o'z main.py'si bilan, port 8021) ishga tushiriladi.
Bu yerga uni ulash SHART EMAS.
"""
from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
import tempfile, os
from wms_agent.agent import (
    process_receipt_document,
    explain_warehouse_exception,
    answer_voice_question,
    get_exceptions_summary,
)

app = FastAPI(
    title="WMS Agent API",
    description="Ombor boshqaruv tizimi uchun AI yordamchi",
    version="1.0.0"
)


class VoiceTextRequest(BaseModel):
    question: str
    operator_id: str = None
    language: str = "uz"


@app.get("/")
def root():
    return {"agent": "WMS Agent", "status": "running", "version": "1.0.0"}


@app.post("/wms/receipt")
async def process_receipt(
    file: UploadFile = File(..., description="Kelgan tovar hujjati (packing list/ASN)"),
    po_number: str = None,
    po_document: UploadFile = File(
        None,
        description="Ixtiyoriy: asl buyurtma hujjati rasmi. Berilsa, "
                     "WMS'dagi PO o'rniga shu hujjat OCR qilinib solishtiriladi."
    ),
):
    """
    Qabul hujjati yordamchisi.
    Ikki rejimda ishlaydi:
      - po_number berilsa: PO ma'lumoti WMS'dan olinadi
      - po_document (rasm) berilsa: ikkala hujjat ham OCR qilinib
        bir-biriga solishtiriladi (WMS'ga bog'liq emas)
    """
    suffix = os.path.splitext(file.filename)[1]
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    po_tmp_path = None
    if po_document is not None:
        po_suffix = os.path.splitext(po_document.filename)[1]
        with tempfile.NamedTemporaryFile(suffix=po_suffix, delete=False) as po_tmp:
            po_tmp.write(await po_document.read())
            po_tmp_path = po_tmp.name

    try:
        result = process_receipt_document(tmp_path, po_number, po_tmp_path)
        
        # AI serveri yoki OCR xatolarini to'g'ri tutib HTTPException qaytarish
        if isinstance(result, dict):
            err_msg = result.get("error") or result.get("note") or ""
            raw_text = str(result.get("raw_text", ""))
            combined = f"{err_msg} {raw_text}".lower()
            if any(k in combined for k in ["xatosi", "error", "timeout", "offline", "connection", "refused"]):
                raise HTTPException(
                    status_code=502, 
                    detail=f"AI server yoki OCR xatosi: {err_msg or raw_text}"
                )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=502, 
            detail=f"Sun'iy intellekt (Vision/LLM) serveriga ulanib bo'lmadi: {str(e)}"
        )
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        if po_tmp_path and os.path.exists(po_tmp_path):
            os.unlink(po_tmp_path)

    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get("/wms/exception/{task_id}")
def explain_exception(task_id: str):
    """Ombor istisnolari copiloti. Bloklangan vazifani tushuntiradi."""
    try:
        result = explain_warehouse_exception(task_id)
        if isinstance(result, dict) and "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI server xatosi: {str(e)}")


@app.get("/wms/exceptions")
def list_exceptions():
    """Barcha joriy istisnolar xulosasi."""
    try:
        return get_exceptions_summary()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Server xatosi: {str(e)}")


@app.post("/wms/ask")
def ask_text(req: VoiceTextRequest):
    """Matnli savol — ovozli yordamchi uchun."""
    try:
        return answer_voice_question(req.question, req.operator_id)
    except Exception as e:
        raise HTTPException(
            status_code=502, 
            detail=f"Ovozli yordamchi (LLM) server xatosi: {str(e)}"
        )


@app.get("/wms/health")
def health():
    return {"status": "ok", "mode": "mock"}