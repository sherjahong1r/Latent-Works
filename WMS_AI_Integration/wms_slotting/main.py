"""
Dinamik slotting — MUSTAQIL FastAPI xizmati.

Bu 1-topshiriq (Qabul hujjati yordamchisi, wms_agent, port 8020) bilan
ARALASHMAYDI — butunlay alohida ilova, alohida portda ishlaydi. Ikkalasi
ham bir vaqtda parallel ishga tushirilishi mumkin.

Ishga tushirish (WMS_AI papkasi ichidan):
    py -m uvicorn wms_slotting.main:app --port 8021 --reload

Swagger UI: http://127.0.0.1:8021/docs
"""
from fastapi import FastAPI

from wms_slotting.routers.slotting import router as slotting_router

app = FastAPI(
    title="WMS Slotting Agent",
    description="Dinamik slotting — kelayotgan tovar uchun eng mos ombor joyini tavsiya qiladi.",
    version="1.0.0",
)

app.include_router(slotting_router)


@app.get("/")
def root():
    return {
        "service": "wms-slotting-agent",
        "status": "ok",
        "endpoints": [
            "POST /wms/slotting",
            "POST /wms/slotting/document",
            "GET  /wms/slotting/pending",
        ],
    }