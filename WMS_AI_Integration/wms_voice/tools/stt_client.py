"""
STT (Speech-to-Text) — MAHALLIY (local) faster-whisper orqali.

Bu — tashqi server/ngrok tunneliga BOG'LIQ EMAS. Model to'g'ridan-to'g'ri
shu kompyuterda ishlaydi (bir marta yuklanadi, xotirada saqlanadi).
Shuning uchun ngrok manzili o'zgarib/o'chib turishi bu yerga ta'sir
qilmaydi — doimiy barqaror ishlaydi.

O'rnatish (bir marta):
    py -m pip install faster-whisper
"""
import tempfile
import os

_model = None

# "medium" — o'zbek/rus tilini yaxshi tushunadi, o'rtacha tezlikda ishlaydi.
# Sekin ketsa "small"ga tushiring, sifat kerak bo'lsa "large-v3"ga chiqing.
MODEL_SIZE = "medium"


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        # CPU'da barqaror ishlaydi; GPU (CUDA) bo'lsa device="cuda" qiling —
        # ancha tezroq bo'ladi.
        _model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
    return _model


def transcribe_audio(audio_bytes: bytes, language: str = "uz") -> str:
    """
    Audio baytlarni matnga aylantiradi — mahalliy faster-whisper orqali.

    Kirish:
        audio_bytes — operator ovozi (fayl baytlari, .wav/.mp3/.webm va h.k.)
        language — "uz" yoki "ru"

    Chiqish:
        Aniqlangan matn (str)
    """
    model = _get_model()

    # faster-whisper fayl yo'lidan o'qiydi — vaqtinchalik faylga yozamiz
    with tempfile.NamedTemporaryFile(suffix=".audio", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        segments, info = model.transcribe(tmp_path, language=language)
        text = " ".join(seg.text.strip() for seg in segments).strip()
        return text
    finally:
        os.unlink(tmp_path)
