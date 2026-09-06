# """
# llm_client.py — LLM serveriga so'rov yuboradigan UMUMIY (provider-
# agnostik) klient. Barcha boshqa fayllar (vision_toolkit.py,
# ai_advisor.py, predictor.py, shift_report.py) shu yerdagi
# `chat_completion()` funksiyasini chaqiradi — ular serverning aynan
# qanday API formatida ishlashini bilishi shart emas.

# QO'LLAB-QUVVATLANADIGAN SERVER TURLARI (config.LLM_PROVIDER orqali
# tanlanadi):

#   - "ollama" (standart): Ollama'ning /api/chat endpointi.
#       So'rov: {"model":..., "messages":[{"role":"user","content":...,
#                "images":[base64...]}], "format":"json", ...}

#   - "vllm": OpenAI-compatible server (masalan vLLM), /v1/chat/completions
#       endpointi, Authorization: Bearer <VLLM_API_KEY> header bilan.
#       So'rov: {"model":..., "messages":[{"role":"user","content":
#                [{"type":"text","text":...},
#                 {"type":"image_url","image_url":{"url":"data:image/jpeg;base64,..."}}]
#                }], "response_format":{"type":"json_object"}, ...}

# YANGI PROVIDER QO'SHISH: shu faylga yangi `_call_<nom>()` funksiyasi
# yozib, `chat_completion()` ichidagi if/elif zanjiriga qo'shish kifoya —
# qolgan barcha fayllarga tegishga hojat yo'q.
# """

# import json
# import time

# import requests

# from config import (
#     LLM_PROVIDER,
#     OLLAMA_BASE_URL,
#     VLLM_API_KEY,
#     OLLAMA_TIMEOUT_SECONDS,
#     MAX_RETRIES,
#     RETRY_DELAY_SECONDS,
# )


# def _call_ollama(model: str, prompt: str, image_b64: str | None, json_mode: bool) -> str:
#     """Ollama /api/chat formatida so'rov yuboradi. Xom matn javobni
#     (JSON parslashdan OLDIN) qaytaradi."""
#     message = {"role": "user", "content": prompt}
#     if image_b64:
#         message["images"] = [image_b64]

#     payload = {
#         "model": model,
#         "messages": [message],
#         "stream": False,
#         "options": {"temperature": 0},
#     }
#     if json_mode:
#         payload["format"] = "json"

#     response = requests.post(
#         f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat",
#         headers={"ngrok-skip-browser-warning": "true", "Content-Type": "application/json"},
#         json=payload,
#         timeout=OLLAMA_TIMEOUT_SECONDS,
#     )
#     response.raise_for_status()
#     return response.json()["message"]["content"]


# def _call_vllm(model: str, prompt: str, image_b64: str | None, json_mode: bool) -> str:
#     """OpenAI-compatible vLLM /v1/chat/completions formatida so'rov
#     yuboradi. Xom matn javobni qaytaradi."""
#     if image_b64:
#         content = [
#             {"type": "text", "text": prompt},
#             {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
#         ]
#     else:
#         content = prompt

#     payload = {
#         "model": model,
#         "messages": [{"role": "user", "content": content}],
#         "temperature": 0,
#     }
#     if json_mode:
#         payload["response_format"] = {"type": "json_object"}

#     headers = {"Content-Type": "application/json"}
#     if VLLM_API_KEY:
#         headers["Authorization"] = f"Bearer {VLLM_API_KEY}"

#     response = requests.post(
#         f"{OLLAMA_BASE_URL.rstrip('/')}/v1/chat/completions",
#         headers=headers,
#         json=payload,
#         timeout=OLLAMA_TIMEOUT_SECONDS,
#     )
#     response.raise_for_status()
#     return response.json()["choices"][0]["message"]["content"]


# def chat_completion(model: str, prompt: str, image_b64: str | None = None,
#                      json_mode: bool = True, max_retries: int = MAX_RETRIES) -> dict:
#     """LLM'ga so'rov yuboradi va JAVOBNI JSON (dict) sifatida qaytaradi.

#     `image_b64` berilsa — vision so'rov (rasm + matn), berilmasa —
#     faqat matn so'rovi. `json_mode=True` bo'lsa, server (imkon qadar)
#     JSON formatida javob berishga undaladi va javob avtomatik
#     `json.loads()` qilinadi.

#     Vaqtincha muammo bo'lsa (tarmoq, timeout), `max_retries` marta
#     qayta urinadi (config.RETRY_DELAY_SECONDS oralig'ida)."""
#     last_error = None

#     for attempt in range(1, max_retries + 1):
#         try:
#             if LLM_PROVIDER == "vllm":
#                 raw = _call_vllm(model, prompt, image_b64, json_mode)
#             else:
#                 raw = _call_ollama(model, prompt, image_b64, json_mode)

#             return json.loads(raw) if json_mode else {"text": raw}

#         except (requests.RequestException, KeyError, IndexError, json.JSONDecodeError) as e:
#             last_error = e
#             if attempt < max_retries:
#                 print(f"[LLM][OGOHLANTIRISH] {attempt}-urinish muvaffaqiyatsiz ({e}). "
#                       f"{RETRY_DELAY_SECONDS}s kutib, qayta urinaman ({attempt + 1}/{max_retries})...")
#                 time.sleep(RETRY_DELAY_SECONDS)
#             else:
#                 print(f"[LLM][XATO] {max_retries} marta urinildi, hammasi muvaffaqiyatsiz.")

#     raise last_error





"""
llm_client.py — LLM serveriga so'rov yuboradigan UMUMIY (provider-
agnostik) klient. Barcha boshqa fayllar (vision_toolkit.py,
ai_advisor.py, predictor.py, shift_report.py) shu yerdagi
`chat_completion()` funksiyasini chaqiradi — ular serverning aynan
qanday API formatida ishlashini bilishi shart emas.

QO'LLAB-QUVVATLANADIGAN SERVER TURLARI (config.LLM_PROVIDER orqali
tanlanadi):

  - "ollama" (standart): Ollama'ning /api/chat endpointi.
      So'rov: {"model":..., "messages":[{"role":"user","content":...,
               "images":[base64...]}], "format":"json", ...}

  - "vllm": OpenAI-compatible server (masalan vLLM), /v1/chat/completions
      endpointi, Authorization: Bearer <VLLM_API_KEY> header bilan.
      So'rov: {"model":..., "messages":[{"role":"user","content":
               [{"type":"text","text":...},
                {"type":"image_url","image_url":{"url":"data:image/jpeg;base64,..."}}]
               }], "response_format":{"type":"json_object"}, ...}

YANGI PROVIDER QO'SHISH: shu faylga yangi `_call_<nom>()` funksiyasi
yozib, `chat_completion()` ichidagi if/elif zanjiriga qo'shish kifoya —
qolgan barcha fayllarga tegishga hojat yo'q.
"""

import json
import time

import requests

from config import (
    LLM_PROVIDER,
    OLLAMA_BASE_URL,
    VLLM_API_KEY,
    VLLM_JSON_MODE,
    OLLAMA_TIMEOUT_SECONDS,
    MAX_RETRIES,
    RETRY_DELAY_SECONDS,
)


def _call_ollama(model: str, prompt: str, image_b64: str | None, json_mode: bool,
                  max_tokens: int | None) -> str:
    """Ollama /api/chat formatida so'rov yuboradi. Xom matn javobni
    (JSON parslashdan OLDIN) qaytaradi."""
    message = {"role": "user", "content": prompt}
    if image_b64:
        message["images"] = [image_b64]

    options = {"temperature": 0}
    if max_tokens:
        options["num_predict"] = max_tokens

    payload = {
        "model": model,
        "messages": [message],
        "stream": False,
        "options": options,
    }
    if json_mode:
        payload["format"] = "json"

    response = requests.post(
        f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat",
        headers={"ngrok-skip-browser-warning": "true", "Content-Type": "application/json"},
        json=payload,
        timeout=OLLAMA_TIMEOUT_SECONDS,
    )
    if response.status_code != 200:
        raise requests.HTTPError(
            f"{response.status_code} {response.reason} | URL: {response.url} | "
            f"Server javobi: {response.text[:500]!r}"
        )
    return response.json()["message"]["content"]


def _call_vllm(model: str, prompt: str, image_b64: str | None, json_mode: bool,
                max_tokens: int | None) -> str:
    """OpenAI-compatible vLLM /v1/chat/completions formatida so'rov
    yuboradi. Xom matn javobni qaytaradi."""
    if image_b64:
        content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
        ]
    else:
        content = prompt

    headers = {"Content-Type": "application/json"}
    if VLLM_API_KEY:
        headers["Authorization"] = f"Bearer {VLLM_API_KEY}"

    url = f"{OLLAMA_BASE_URL.rstrip('/')}/v1/chat/completions"

    def _post(with_response_format: bool) -> requests.Response:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": content}],
            "temperature": 0,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if json_mode and with_response_format and VLLM_JSON_MODE:
            payload["response_format"] = {"type": "json_object"}
        return requests.post(url, headers=headers, json=payload, timeout=OLLAMA_TIMEOUT_SECONDS)

    response = _post(with_response_format=True)

    if response.status_code == 400 and "response_format" in response.text.lower():
        response = _post(with_response_format=False)

    if response.status_code != 200:
        raise requests.HTTPError(
            f"{response.status_code} {response.reason} | URL: {response.url} | "
            f"Server javobi: {response.text[:500]!r}"
        )
    return response.json()["choices"][0]["message"]["content"]


def _strip_markdown_fence(text: str) -> str:
    """Ba'zi modellar JSON'ni ```json ... ``` ichiga o'rab yuborishi mumkin."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1] if "\n" in t else t
        if t.endswith("```"):
            t = t[:-3]
        t = t.strip()
    return t


def chat_completion(model: str, prompt: str, image_b64: str | None = None,
                     json_mode: bool = True, max_retries: int = MAX_RETRIES,
                     max_tokens: int | None = None, label: str = "LLM") -> dict:
    """LLM'ga so'rov yuboradi va JAVOBNI JSON (dict) sifatida qaytaradi.
    `label` — log'da qaysi chaqiruv ekanini aniq ko'rsatish uchun
    (masalan "VISION", "ADVISOR", "PREDICTOR", "SHIFT")."""
    last_error = None
    prompt_len = len(prompt)
    image_note = ", rasm bor" if image_b64 else ""

    for attempt in range(1, max_retries + 1):
        start = time.monotonic()
        print(f"[{label}] So'rov yuborildi (prompt: {prompt_len} belgi{image_note}, "
              f"model: {model}, max_tokens: {max_tokens})...")
        try:
            if LLM_PROVIDER == "vllm":
                raw = _call_vllm(model, prompt, image_b64, json_mode, max_tokens)
            else:
                raw = _call_ollama(model, prompt, image_b64, json_mode, max_tokens)

            elapsed = time.monotonic() - start
            print(f"[{label}] Javob keldi: {elapsed:.1f}s da ({len(raw)} belgi javob).")

            if json_mode:
                return json.loads(_strip_markdown_fence(raw))
            return {"text": raw}

        except (requests.RequestException, KeyError, IndexError, json.JSONDecodeError) as e:
            elapsed = time.monotonic() - start
            last_error = e
            print(f"[{label}] {elapsed:.1f}s dan keyin xato: {e}")
            if attempt < max_retries:
                print(f"[LLM][OGOHLANTIRISH] {attempt}-urinish muvaffaqiyatsiz ({e}). "
                      f"{RETRY_DELAY_SECONDS}s kutib, qayta urinaman ({attempt + 1}/{max_retries})...")
                time.sleep(RETRY_DELAY_SECONDS)
            else:
                print(f"[LLM][XATO] {max_retries} marta urinildi, hammasi muvaffaqiyatsiz.")

    raise last_error