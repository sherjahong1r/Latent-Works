<<<<<<< HEAD
# WMS AI Agentlar — MES_WMS_AI_Integratsiyasi loyihasi

Ombor boshqaruv tizimi (WMS) uchun 4 ta mustaqil AI yordamchi. Har biri
**alohida FastAPI xizmati**, o'z portida ishlaydi — bir-biriga bog'liq
emas, mustaqil ishga tushiriladi va sinaladi.

| # | Vazifa | Papka | Port | AI turi |
|---|--------|-------|------|---------|
| 1 | Qabul hujjati yordamchisi | `wms_agent/` | **8020** | OCR + Document AI |
| 2 | Dinamik slotting | `wms_slotting/` | **8021** | Optimization + learning-to-rank |
| 3 | Ovoz/skaner vazifa yordamchisi | `wms_voice/` | **8022** | Speech + deterministic workflow |
| 4 | Cycle-count ustuvorligi | `wms_cyclecount/` | **8023** | Risk scoring |

Manba: `MES_WMS_AI_Integratsiyasi` hujjati (rahbariyat tomonidan
tasdiqlangan AI funksiyalar rejasi).

---

## Papka tuzilishi

```
WMS_AI/
├── shared/              # Barcha 4 xizmat uchun UMUMIY modullar
│   ├── config.py           # .env dan sozlamalarni o'qiydi
│   ├── llm_client.py       # Ollama LLM (matn + vision) chaqiruvlari
│   ├── stt_tts.py          # (eski/yordamchi STT-TTS funksiyalar)
│   ├── vector_store.py     # pgvector — RAG bilim bazasi (ixtiyoriy)
│   └── wms_auth.py         # Real WMS API uchun login/token boshqaruvi
│
├── mock_data/            # USE_MOCK=True rejimida ishlatiladigan soxta ma'lumot
│   ├── wms_mock.py
│   └── slotting_mock.py
│
├── tests/                 # Umumiy testlar
│   └── test_wms.py
│
├── wms_agent/             # 1-TOPSHIRIQ — Qabul hujjati yordamchisi
│   ├── main.py               # FastAPI ilova (port 8020)
│   ├── agent.py
│   ├── prompts/
│   └── tools/
│       ├── ocr.py               # Vision LLM orqali hujjat o'qish
│       ├── slotting.py           # (eskirgan qoldiq — tekshirilmoqda)
│       └── wms_api.py            # Real WMS API bilan bog'lanish
│
├── wms_slotting/          # 2-TOPSHIRIQ — Dinamik slotting
│   ├── main.py               # FastAPI ilova (port 8021)
│   ├── test_slotting_standalone.py   # API'siz sinov skripti
│   ├── routers/slotting.py
│   └── tools/
│       ├── slotting_db.py        # Bazadan bin/mahsulot o'qish (SELECT)
│       ├── slotting_engine.py    # Skorlash (optimization) algoritmi
│       └── address_extract.py    # Hujjatdan ombor manzilini aniqlash
│
├── wms_voice/             # 3-TOPSHIRIQ — Ovoz/skaner vazifa yordamchisi
│   ├── main.py               # FastAPI ilova (port 8022)
│   ├── mock_tasks.py          # Sinov uchun soxta PUTAWAY/PICK vazifalari
│   ├── routers/voice.py
│   └── tools/
│       ├── stt_client.py         # Real STT (Uzbek Whisper) API
│       ├── tts_client.py         # Real TTS (Uzbek XTTS) API
│       ├── response_parser.py    # Qat'iy (regex) javob tahlili
│       ├── workflow_engine.py    # Deterministik qadam mashinasi
│       ├── qa_engine.py          # Erkin savol-javob (LLM, qat'iy JSON)
│       ├── company_knowledge.py  # QA uchun statik kompaniya konteksti
│       └── voice_db.py           # QA uchun haqiqiy baza grounding
│
├── wms_cyclecount/        # 4-TOPSHIRIQ — Cycle-count ustuvorligi
│   ├── main.py               # FastAPI ilova (port 8023)
│   ├── test_cyclecount_standalone.py
│   ├── routers/cyclecount.py
│   └── tools/
│       ├── cyclecount_db.py      # Bazadan tarixiy ma'lumot o'qish
│       └── cyclecount_engine.py  # Risk scoring algoritmi
│
├── test_voice_chat.html   # Brauzerda ovoz/matn bilan sinash uchun chat
├── .env                    # Barcha sozlamalar (pastga qarang)
├── requirements.txt
└── README.md               # Shu fayl
```

---

## .env — kerakli sozlamalar

```env
# --- LLM (Ollama, matn va vision) ---
OLLAMA_HOST=https://xxxx.ngrok-free.app
LLM_MODEL=qwen3:8b
LLM_FAST_MODEL=qwen3:8b
VISION_MODEL=qwen3-vl:8b

# --- STT/TTS server (Ovoz/skaner uchun) ---
STT_TTS_API_URL=https://xxxx.ngrok-free.app

# --- Haqiqiy WMS bazasi (o'qish uchun — slotting, voice-QA, cyclecount) ---
WMS_DB_HOST=192.168.1.7
WMS_DB_PORT=5432
WMS_DB_NAME=wmsdb
WMS_DB_USER=read-user-wms
WMS_DB_PASSWORD=...

# --- Real WMS API (autentifikatsiya, wms_agent uchun) ---
WMS_API_URL=https://api-wms.tenzorsoft.uz
# (login ma'lumotlari shared/wms_auth.py orqali boshqariladi)

# --- Mahalliy pgvector (RAG bilim bazasi, ixtiyoriy) ---
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=wms_ai
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
```

> ⚠️ **VPN eslatma:** `WMS_DB_HOST=192.168.1.7` — ichki tarmoq manzili,
> faqat OpenVPN ulangan holda ishlaydi.
>
> ⚠️ **ngrok eslatma:** `OLLAMA_HOST` va `STT_TTS_API_URL` — bepul ngrok
> tunnellari, har safar qayta ishga tushirilganda manzil o'zgaradi.
> Manzil o'zgarsa, faqat `.env`ni yangilash kifoya (kodga tegilmaydi).

---

## O'rnatish

```powershell
cd C:\Users\Owner\Desktop\WMS_AI
pip install -r requirements.txt
```

---

## Ishga tushirish

Har biri **alohida terminal oynasida**, WMS_AI papkasi ichidan:

```powershell
# 1) Qabul hujjati yordamchisi
py -m uvicorn wms_agent.main:app --port 8020 --reload

# 2) Dinamik slotting
py -m uvicorn wms_slotting.main:app --port 8021 --reload

# 3) Ovoz/skaner vazifa yordamchisi
py -m uvicorn wms_voice.main:app --port 8022 --reload

# 4) Cycle-count ustuvorligi
py -m uvicorn wms_cyclecount.main:app --port 8023 --reload
```

Har biri uchun Swagger UI: `http://127.0.0.1:<port>/docs`

---

## Xizmatlar bo'yicha qisqacha

### 1. Qabul hujjati yordamchisi — `:8020`
Supplier hujjatini (packing-list/ASN) rasm/PDF sifatida qabul qilib,
OCR (vision LLM) orqali o'qiydi, PO bilan solishtiradi, tafovutlarni
ko'rsatadi.

- `POST /wms/receipt` — hujjatni yuklab tahlil qilish
- `USE_MOCK` bayrog'i orqali soxta yoki real WMS API'ga ulanadi
  (`wms_agent/tools/wms_api.py`, `shared/wms_auth.py`)

### 2. Dinamik slotting — `:8021`
Kelayotgan tovar uchun (qo'lda kiritilgan yoki hujjatdan OCR bilan
o'qilgan) eng mos ombor yacheykasini tavsiya qiladi — aylanish,
o'lcham, vazn, moslik, muddat, masofa va sig'imga qarab.

- `POST /wms/slotting` — qo'lda kiritilgan ma'lumot bo'yicha
- `POST /wms/slotting/document` — hujjat yuklab (bir nechta tovar
  qatori bo'lsa, har biri uchun alohida tavsiya; ombor manzili
  hujjatdan avtomatik aniqlanadi yoki qo'lda beriladi)
- `GET /wms/slotting/pending` — bin kutayotgan ochiq PUTAWAY vazifalari
- Sinov: `py -m wms_slotting.test_slotting_standalone`

### 3. Ovoz/skaner vazifa yordamchisi — `:8022`
Operatorga joriy vazifani ovozda aytadi, ovozli/matnli javobini qat'iy
(regex asosli) qadam mashinasi orqali tahlil qiladi. Haqiqiy yozuv
faqat barkod skaneri orqali amalga oshiriladi — ovoz orqali hech narsa
WMS'ga yozilmaydi. Shuningdek, ombor/korxona haqidagi erkin savollarga
ham (LLM orqali, qat'iy JSON formatda, faqat shu mavzuda) javob beradi.

- `POST /wms/voice/turn` — **asosiy**, yagona "chat" endpointi (matn
  yoki audio, STT+workflow/QA+TTS bitta so'rovda)
- `GET /wms/voice/tasks` — sinov vazifalari ro'yxati
- `POST /wms/voice/session/start`, `POST /wms/voice/respond/text`,
  `POST /wms/voice/respond/audio`, `GET /wms/voice/session/{id}/audio`
  — eski/qismli endpointlar (sinov uchun qulay)
- Brauzerda sinash: `test_voice_chat.html`ni oching (Server maydoniga
  `http://127.0.0.1:8022` yozing)

### 4. Cycle-count ustuvorligi — `:8023`
Harakat tarixi, tuzatishlar, qiymat va tekshiruv muddatiga asoslanib,
qaysi ombor yacheykalarini birinchi navbatda jismoniy tekshirish
(inventarizatsiya) kerakligini tavsiya qiladi.

- `GET /wms/cyclecount/priority?warehouse_id=1` — ustuvorlik ro'yxati
- Sinov: `py -m wms_cyclecount.test_cyclecount_standalone`

---

## Muhim eslatmalar

- **Xavfsizlik:** barcha 4 xizmat ham WMS bazasiga **faqat o'qish**
  (`read-user-wms`, SELECT) huquqi bilan ulanadi — hech biri
  to'g'ridan-to'g'ri yozuv qilmaydi. Yakuniy tasdiq har doim operator/
  menejer orqali.
- **Test ma'lumoti:** hozirgi `wmsdb` ba'zi joylarda sinov/demo
  ma'lumotiga o'xshash belgilar ko'rsatgan (bir xil miqdorlar, tasodifiy
  mahsulot-bin bog'lanishlari) — bu tasdiqlanishi kerak, natijalar shu
  nuqtai nazardan baholansin.
- **`.env`dagi zaxira parollar:** ba'zi fayllarda `.env` bo'sh bo'lsa
  ham ishlashi uchun kodda zaxira (fallback) parol qoldirilgan — real
  muhitga chiqarishdan oldin bularni olib tashlab, faqat `.env` orqali
  boshqarish tavsiya etiladi.





<!-- 1)
cd C:\Users\Owner\Desktop\WMS_AI
py -m uvicorn wms_agent.main:app --port 8020 --reload
2)
cd C:\Users\Owner\Desktop\WMS_AI
py -m uvicorn wms_slotting.main:app --port 8021 --reload
3)
cd C:\Users\Owner\Desktop\WMS_AI
py -m uvicorn wms_voice.main:app --port 8022 --reload
4)
cd C:\Users\Owner\Desktop\WMS_AI
py -m uvicorn wms_cyclecount.main:app --port 8023 --reload


1-topshiriq (Qabul hujjati):
http://127.0.0.1:8020/docs

2-topshiriq (Dinamik slotting):
http://127.0.0.1:8021/docs
=======
wms-ai -->
>>>>>>> d6a740f05a7bf6b464609c61ed62df23928b93ee
