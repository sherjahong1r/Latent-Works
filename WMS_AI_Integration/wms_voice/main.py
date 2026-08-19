"""
Ovoz/skaner vazifa yordamchisi — MUSTAQIL FastAPI xizmati.

1-topshiriq (wms_agent, port 8020) va 2-topshiriq (wms_slotting, port 8021)
bilan ARALASHMAYDI — butunlay alohida ilova, alohida portda. Uchalasi ham
bir vaqtda parallel ishga tushirilishi mumkin.

Ishga tushirish (WMS_AI papkasi ichidan):
    py -m uvicorn wms_voice.main:app --port 8022 --reload

Swagger UI: http://127.0.0.1:8022/docs
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from wms_voice.routers.voice import router as voice_router

app = FastAPI(
    title="WMS Voice Agent",
    description="Ovoz/skaner vazifa yordamchisi — deterministik qadam-baqadam ko'rsatma.",
    version="1.0.0",
)

# CORS — test sahifasi (browser'da ochilgan HTML) yoki boshqa frontend
# manzildan so'rov yubora olishi uchun. Ishlab chiqarishda allow_origins
# ni aniq domenlar bilan cheklang (masalan ["https://sizning-frontend.com"]).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(voice_router)


@app.get("/")
def root():
    return {
        "service": "wms-voice-agent",
        "status": "ok",
        "endpoints": [
            "GET  /wms/voice/tasks",
            "POST /wms/voice/turn           (ASOSIY: chat-ko'rinishi, matn+audio bitta so'rovda)",
            "POST /wms/voice/session/start  (eski, alohida oqim uchun)",
            "GET  /wms/voice/session/{session_id}/audio  (eski)",
            "POST /wms/voice/respond/text   (eski, sinov uchun, STT'siz)",
            "POST /wms/voice/respond/audio  (eski, haqiqiy, STT bilan)",
        ],
    }
