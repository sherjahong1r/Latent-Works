"""
TTS (Text-to-Speech) — edge-tts orqali (Microsoft'ning bepul, ochiq
kutubxonasi). Tunnel/tashqi serverga bog'liq emas.

MUHIM: bu funksiya ASYNC (async def). Chaqiruvchi kod (routers/voice.py)
`await synthesize_speech(...)` deb chaqirishi kerak — FastAPI allaqachon
asenkron tsikl (event loop) ichida ishlaganidek, ichkarida yana
asyncio.run() chaqirib bo'lmaydi (aynan shu xato oldin chiqqan edi).

O'rnatish (bir marta):
    py -m pip install edge-tts
"""
import tempfile
import os

_VOICE_MAP = {
    "uz": "uz-UZ-MadinaNeural",
    "ru": "ru-RU-SvetlanaNeural",
    "en": "en-US-JennyNeural",
}


async def synthesize_speech(text: str, language: str = "uz") -> bytes:
    """
    Matnni ovozga aylantiradi — edge-tts orqali (async).

    Kirish:
        text — o'qilishi kerak bo'lgan matn
        language — "uz", "ru" yoki "en"

    Chiqish:
        MP3 audio fayl baytlari (bytes)
    """
    import edge_tts

    if not text or not text.strip():
        text = "."

    voice = _VOICE_MAP.get(language, "uz-UZ-MadinaNeural")

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(tmp_path)
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        os.unlink(tmp_path)