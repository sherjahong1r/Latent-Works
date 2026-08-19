import ollama
from shared.config import OLLAMA_HOST, LLM_MODEL, LLM_FAST_MODEL, LLM_HEAVY_MODEL, VISION_MODEL

# timeout ni 120 soniyaga oshiramiz (kattaroq modellar va ngrok orqali sekinroq kelganda qiynalmasligi uchun)
client = ollama.Client(
    host=OLLAMA_HOST, 
    headers={"ngrok-skip-browser-warning": "true"},
    timeout=120.0  # <--- Timeout qo'shildi
)


def ask_llm(prompt: str, model: str = None, system: str = None) -> str:
    """
    LLM ga savol berish.
    model: None bo'lsa LLM_MODEL ishlatiladi
    system: tizim prompti (ixtiyoriy)
    """
    use_model = model or LLM_MODEL
    messages = []

    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        response = client.chat(model=use_model, messages=messages)
        return response["message"]["content"]
    except Exception as e:
        return f"[LLM xatosi: {str(e)}]"


def ask_llm_fast(prompt: str, system: str = None) -> str:
    """Tez javob uchun — qwen3:8b"""
    return ask_llm(prompt, model=LLM_FAST_MODEL, system=system)


def ask_llm_heavy(prompt: str, system: str = None) -> str:
    """Murakkab tahlil uchun — qwen3.6:35b"""
    return ask_llm(prompt, model=LLM_HEAVY_MODEL, system=system)


def ask_vision(prompt: str, image_base64: str, model: str = None) -> str:
    """
    Vision LLM ga rasm + savol berish.
    image_base64: rasm base64 formatida
    """
    use_model = model or VISION_MODEL
    try:
        response = client.chat(
            model=use_model,
            messages=[{
                "role": "user",
                "content": prompt,
                "images": [image_base64]
            }]
        )
        return response["message"]["content"]
    except Exception as e:
        return f"[Vision xatosi: {str(e)}]"


def get_embedding(text: str) -> list[float]:
    """Matnni vektorlashtirish — bge-m3"""
    from shared.config import EMBED_MODEL
    try:
        response = client.embeddings(model=EMBED_MODEL, prompt=text)
        return response["embedding"]
    except Exception as e:
        print(f"Embedding xatosi: {e}")
        return []

    