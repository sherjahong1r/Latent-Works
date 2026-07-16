"""
ai_vision_reporter.py — SCADA dashboard skrinshotini Groq (bepul) vision
modeli yordamida o'qib, natijani JSON qilib tashqi API'ga jo'natadi.
"""

import os
import json
import base64
import time

import requests
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from groq import Groq

load_dotenv()   # .env faylini o'qib, GROQ_API_KEY ni environment'ga yuklaydi

DASHBOARD_URL = "http://localhost:5000"
EXTERNAL_API_ENDPOINT = "http://localhost:5001/api/report"
# EXTERNAL_API_ENDPOINT = "https://httpbin.org/post"   # test uchun; haqiqiy API bilan almashtiring
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
CYCLE_SECONDS = 30

PROMPT = """Bu — kimyoviy reaktor SCADA dashboard skrinshoti. Rasmda ko'ringan
barcha datchik qiymatlari (harorat, bosim, issiqlik, tezlik, pH, sarf, sath,
tebranish, namlik, kuchlanish, tok) va alarm xabarlarini quyidagi JSON
formatida qaytar. Faqat JSON qaytar, boshqa hech qanday matn yozma:

{
  "temperature": <son yoki null>,
  "pressure": <son yoki null>,
  "heat_output": <son yoki null>,
  "speed": <son yoki null>,
  "ph": <son yoki null>,
  "flow_rate": <son yoki null>,
  "level_pct": <son yoki null>,
  "vibration": <son yoki null>,
  "humidity": <son yoki null>,
  "voltage": <son yoki null>,
  "current_a": <son yoki null>,
  "alarms": [<matn ro'yxati, agar bo'lmasa bo'sh ro'yxat>]
}"""


def take_screenshot(path: str = "dashboard_screenshot.png"):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(DASHBOARD_URL, timeout=15000)
        page.wait_for_timeout(1000)
        page.screenshot(path=path, full_page=True)
        browser.close()
    return path


def read_dashboard_with_ai(image_path: str) -> dict:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY topilmadi. .env fayl yarating va ichiga "
            "GROQ_API_KEY=gsk_... qo'shing, yoki environment variable sifatida o'rnating."
        )

    client = Groq(api_key=api_key)

    with open(image_path, "rb") as f:
        b64_image = base64.b64encode(f.read()).decode("utf-8")

    response = client.chat.completions.create(
        model=VISION_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64_image}"},
                    },
                ],
            }
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )

    raw = response.choices[0].message.content
    return json.loads(raw)


def send_to_external_api(data: dict):
    try:
        resp = requests.post(EXTERNAL_API_ENDPOINT, json=data, timeout=10)
        return resp.status_code
    except requests.RequestException as e:
        print(f"[XATO] API'ga yuborishda muammo: {e}")
        return None


def main():
    print(f"AI vision reporter ishga tushdi. Har {CYCLE_SECONDS} soniyada bir marta ishlaydi.")
    while True:
        try:
            screenshot_path = take_screenshot()
            data = read_dashboard_with_ai(screenshot_path)
            print("O'qilgan qiymatlar:", json.dumps(data, ensure_ascii=False, indent=2))

            status = send_to_external_api(data)
            print(f"API javobi: {status}")

        except Exception as e:
            print(f"[XATO] Sikl davomida muammo: {e}")

        time.sleep(CYCLE_SECONDS)


if __name__ == "__main__":
    main()