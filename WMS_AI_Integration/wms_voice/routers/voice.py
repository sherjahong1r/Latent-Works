"""
Ovoz/skaner yordamchisi — soddalashtirilgan versiya.

MUHIM O'ZGARISH: qat'iy PUTAWAY/PICK vazifa ssenariysi (mock_tasks,
workflow_engine) ENDI ISHLATILMAYDI. Endi bitta oddiy oqim bor:
operator matn yoki ovoz bilan ISTALGAN savol beradi, tizim
qa_engine.answer_question() orqali javob beradi (kerak bo'lsa SQL
bazadan o'qib). Aloqasiz mavzu bo'lsa yoki bazada ma'lumot topilmasa,
mos ravishda rad javobi/ma'lumot yo'qligi haqida javob qaytaradi.

Endpoint: POST /wms/voice/turn
  - session_id: ixtiyoriy (frontend kuzatuv uchun, mantiqqa ta'siri yo'q)
  - text: matn savol (ixtiyoriy)
  - audio: ovoz fayli (ixtiyoriy, STT orqali matnga aylantiriladi)
  - Ikkalasi ham bo'sh bo'lsa (masalan sahifa birinchi ochilganda) —
    salomlashuv/imkoniyatlar xabari qaytariladi (xato emas).
"""
import uuid

from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse

from wms_voice.tools.qa_engine import answer_question
from wms_voice.tools.stt_client import transcribe_audio
from wms_voice.tools.tts_client import synthesize_speech

router = APIRouter(prefix="/wms/voice", tags=["Ovoz yordamchisi"])


@router.post("/turn")
async def turn(
    session_id: str = Form(default=None),
    text: str = Form(default=None),
    audio: UploadFile = File(default=None),
):
    """
    Bitta "muloqot burilishi": operator xabarini oladi (matn yoki ovoz),
    umumiy savol-javob mexanizmiga yuboradi, javobni matn + (bo'lsa)
    ovoz ko'rinishida qaytaradi.
    """
    if not session_id:
        session_id = str(uuid.uuid4())

    stt_text = None
    question_text = text or ""

    if audio is not None:
        audio_bytes = await audio.read()
        try:
            stt_text = transcribe_audio(audio_bytes, language="uz")
            question_text = stt_text
        except NotImplementedError as e:
            return JSONResponse({
                "session_id": session_id,
                "prompt_text": f"Ovozni tanib bo'lmadi (STT ulanmagan): {e}",
                "finished": False,
                "exception": False,
            })
        except Exception as e:
            return JSONResponse({
                "session_id": session_id,
                "prompt_text": f"Ovozni tanishda xato: {e}",
                "finished": False,
                "exception": False,
            })

    result = answer_question(question_text)
    prompt_text = result["answer"]

    response = {
        "session_id": session_id,
        "stt_text": stt_text,
        "prompt_text": prompt_text,
        "on_topic": result.get("on_topic"),
        "finished": False,
        "exception": False,
    }

    # TTS — bo'lsa audio ham qo'shamiz, bo'lmasa jim o'tkazib yuboramiz
    # (matnli javob baribir bor, suhbat to'xtamaydi).
    try:
        audio_bytes = await synthesize_speech(prompt_text, language="uz")
        import base64
        response["audio_base64"] = base64.b64encode(audio_bytes).decode("utf-8")
        response["audio_mime"] = "audio/mpeg"
    except Exception as e:
        response["tts_error"] = str(e)

    return JSONResponse(response)
