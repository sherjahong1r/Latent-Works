from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Har bir qismning o'z app'larini import qilamiz
from wms_agent.main import app as agent_app
from wms_slotting.main import app as slotting_app
from wms_voice.main import app as voice_app

app = FastAPI(
    title="WMS Unified AI System",
    description="Ombor uchun yagona sun'iy intellekt tizimi API",
    version="1.0.0"
)

# CORS sozlamalari
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Har bir xizmatni o'zining alohida API manzili (prefix) ostida ulaymiz
app.mount("/agent", agent_app)       # Qabul hujjati va agent funksiyalari uchun
app.mount("/slotting", slotting_app) # Dinamik slotting uchun
app.mount("/voice", voice_app)       # Ovozli va matnli yordamchi uchun

@app.get("/")
def root():
    return {
        "status": "running",
        "message": "WMS Unified AI API ishga tushdi",
        "endpoints": {
            "agent": "/agent",
            "slotting": "/slotting",
            "voice": "/voice"
        }
    }
    