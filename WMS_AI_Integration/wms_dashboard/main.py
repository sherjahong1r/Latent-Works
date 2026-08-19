import os
import httpx
from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="UzERP - WMS Dashboard", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SERVICES = {
    "agent": "http://localhost:8000/agent",
    "slotting": "http://localhost:8000/slotting",
    "voice": "http://localhost:8000/voice"
}

@app.get("/", response_class=HTMLResponse)
def dashboard_home():
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()

@app.post("/api/receipt")
async def proxy_receipt(file: UploadFile = File(...), po_document: UploadFile = File(None)):
    async with httpx.AsyncClient() as client:
        files = {"file": (file.filename, await file.read(), file.content_type)}
        if po_document:
            files["po_document"] = (po_document.filename, await po_document.read(), po_document.content_type)
        response = await client.post(f"{SERVICES['agent']}/wms/receipt", files=files, timeout=60.0)
        return response.json()

@app.post("/api/slotting-doc")
async def proxy_slotting_doc(file: UploadFile = File(...), warehouse_id: int = Form(None)):
    async with httpx.AsyncClient() as client:
        files = {"file": (file.filename, await file.read(), file.content_type)}
        data = {}
        if warehouse_id:
            data["warehouse_id"] = str(warehouse_id)
        response = await client.post(f"{SERVICES['slotting']}/wms/slotting/document", files=files, data=data, timeout=60.0)
        return response.json()

@app.post("/api/voice")
async def proxy_voice(
    request: Request,
    session_id: str = Form(None),
    task_id: str = Form(None),
    text: str = Form(None),
    audio: UploadFile = File(None)
):
    async with httpx.AsyncClient() as client:
        form_data = {}
        files = {}
        if session_id:
            form_data["session_id"] = session_id
        if task_id:
            form_data["task_id"] = task_id
        if text:
            form_data["text"] = text
        if audio:
            files["audio"] = (audio.filename, await audio.read(), audio.content_type)

        response = await client.post(
            f"{SERVICES['voice']}/wms/voice/turn",
            data=form_data,
            files=files if files else None,
            timeout=60.0
        )
        return response.json()


# 3 tasini bittada run qilish uchun:
# cd C:\Users\Owner\Desktop\WMS_AI    
# py -m uvicorn main:app --reload

# dashboard uchun:
# py -m uvicorn wms_dashboard.main:app --port 8030 --reload