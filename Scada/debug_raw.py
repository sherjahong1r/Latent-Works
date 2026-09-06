# """
# debug_raw.py — LLM serveridan qaytayotgan XOM javobni ko'rish uchun,
# JSON parslashdan oldin. Ollama va vLLM ikkalasini ham qo'llab-
# quvvatlaydi (config.LLM_PROVIDER'ga qarab).

# Ishga tushirish: py debug_raw.py rasm_nomi.png
# """

# import sys

# import requests

# from config import (
#     LLM_PROVIDER,
#     OLLAMA_BASE_URL,
#     OLLAMA_MODEL,
#     OLLAMA_TIMEOUT_SECONDS,
#     VLLM_API_KEY,
# )
# from vision_toolkit import PROMPT, _compress_image_for_ai

# image_path = sys.argv[1] if len(sys.argv) > 1 else "shot.png"

# print(f"Provider: {LLM_PROVIDER}")
# print(f"Model: {OLLAMA_MODEL}")
# print(f"Server manzili: {OLLAMA_BASE_URL}")
# print(f"Rasm: {image_path}\n")

# b64_image = _compress_image_for_ai(image_path)

# if LLM_PROVIDER == "vllm":
#     url = f"{OLLAMA_BASE_URL.rstrip('/')}/v1/chat/completions"
#     headers = {"Content-Type": "application/json"}
#     if VLLM_API_KEY:
#         headers["Authorization"] = f"Bearer {VLLM_API_KEY}"
#     payload = {
#         "model": OLLAMA_MODEL,
#         "messages": [{
#             "role": "user",
#             "content": [
#                 {"type": "text", "text": PROMPT},
#                 {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}},
#             ],
#         }],
#         "response_format": {"type": "json_object"},
#         "temperature": 0,
#     }
# else:
#     url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat"
#     headers = {"ngrok-skip-browser-warning": "true", "Content-Type": "application/json"}
#     payload = {
#         "model": OLLAMA_MODEL,
#         "messages": [{"role": "user", "content": PROMPT, "images": [b64_image]}],
#         "stream": False,
#         "format": "json",
#         "options": {"temperature": 0},
#     }

# response = requests.post(url, headers=headers, json=payload, timeout=OLLAMA_TIMEOUT_SECONDS)

# print("HTTP status:", response.status_code)
# print("\n--- TO'LIQ XOM JAVOB ---")
# print(response.json())

# print("\n--- FAQAT MODEL JAVOBI MATNI ---")
# data = response.json()
# if LLM_PROVIDER == "vllm":
#     print(repr(data.get("choices", [{}])[0].get("message", {}).get("content")))
# else:
#     print(repr(data.get("message", {}).get("content")))


    