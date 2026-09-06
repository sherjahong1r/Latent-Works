# SCADA AI Monitoring — README

Sanoat SCADA/HMI dashboardini AI yordamida avtomatik kuzatuvchi,
tahlil qiluvchi va bashorat qiluvchi tizim.

---

## 1. Arxitektura

```
                 ┌────────────────────┐
                 │  capture_pipeline   │  har 45s: skrinshot -> AI -> JSON
                 └──────────┬──────────┘
                            ▼
              vision_reports + metric_history (Postgres)
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                    ▼
 ┌─────────────┐   ┌────────────────┐   ┌─────────────────┐
 │ ai_advisor   │   │   predictor     │   │  shift_report    │
 │ (120s)       │   │ (1-15 daq,      │   │  (12 soatda 1)   │
 │ Plant State  │   │  adaptiv)       │   │                  │
 │ Memory       │   │ 10/20/30 daq    │   │                  │
 │ + Anomaly    │   │ bashorat        │   │                  │
 └──────┬───────┘   └────────┬────────┘   └────────┬─────────┘
        ▼                    ▼                     ▼
 advisor_insights    plant_predictions       shift_reports
 plant_state
        │                    │                     │
        └────────────────────┼─────────────────────┘
                              ▼
                     external_api.py (ALOHIDA)
                     -> http://localhost:5001
```

**Ikkita mustaqil jarayon:**
- `main.py` — ma'lumot yig'ish, tahlil, bashorat (DOIM ishlab turishi kerak)
- `external_api.py` — faqat ko'rish uchun interfeys (ixtiyoriy, xohlagan vaqtda)

---

## 2. Fayllar

| Fayl | Vazifasi |
|---|---|
| `config.py` | Markaziy sozlamalar |
| `database.py` | Bazaga ulanish, jadvallar, yordamchi funksiyalar |
| `vision_toolkit.py` | Skrinshot olish + AI orqali JSON qilish |
| `capture_pipeline.py` | Asosiy capture sikli (video YO'Q, faqat skrinshot) |
| `anomaly_detector.py` | Statistik anomaliya aniqlash (ML plug-in nuqtasi bilan) |
| `ai_advisor.py` | Plant State Memory + tarixiy tahlil + tavsiya |
| `predictor.py` | 10/20/30 daqiqalik bashorat, adaptiv interval |
| `shift_report.py` | Avtomatik smena hisoboti |
| `process_topology.py` | P&ID/jarayon bog'liqligi (ixtiyoriy skelet) |
| `external_api.py` | Interfeys (FastAPI + dashboard) |
| `retention_cleanup.py` | Qo'lda ishga tushiriladigan tozalash (ixtiyoriy) |
| `test_promt.py`, `debug_raw.py` | Debug/sinov skriptlari |

---

## 3. Baza jadvallari

| Jadval | Nima saqlaydi |
|---|---|
| `vision_reports` | Har bir skrinshotning xom AI tahlili |
| `metric_history` | Har bir raqamli o'lchov, vaqt bo'yicha (time-series) |
| `plant_state` | Zavodning joriy "xotirasi" (bitta qator) |
| `advisor_insights` | AI Advisor xulosalari tarixi |
| `plant_predictions` | Bashorat natijalari |
| `shift_reports` | Smena hisobotlari |

---

## 4. O'rnatish

```bash
pip install -r requirements.txt
playwright install chromium
```

`.env.example`ni `.env` deb nusxalab, haqiqiy qiymatlarni to'ldiring
(baza, ngrok manzili, modellar).

---

## 5. Ishga tushirish

**Development:**
```bash
py main.py              # asosiy quvur — bitta terminalda, doim ochiq
py external_api.py      # interfeys — boshqa terminalda, ixtiyoriy
```

**Production (interfeys uchun tavsiya etiladi):**
```bash
uvicorn external_api:app --host 0.0.0.0 --port 5001
```
> `--reload` faqat development uchun, production'da ishlatmang.
> Ishonchli avtomatik qayta ishga tushirish uchun Windows Service,
> `systemd`, yoki `pm2`/`supervisor` kabi process manager tavsiya
> etiladi (bu skriptlar buni o'zi qilmaydi).

Dashboard: `http://localhost:5001`
Swagger (API hujjatlari): `http://localhost:5001/docs`

---

## 6. Real SCADA'ga o'tish

Faqat `config.py` (yoki `.env`)dagi `SCADA_URL`ni real manzilga
almashtiring. Agar real SCADA veb-emas (desktop dastur) bo'lsa,
`CAPTURE_MODE = "window"` qilib, `SCADA_WINDOW_TITLE`ni sozlang.

---

## 7. ML modelingizni ulash (Anomaly Detection)

`anomaly_detector.py` faylidagi `compute_anomaly_report()`
funksiyasini o'z ML modelingiz bilan almashtiring — funksiya imzosi
(kirish/chiqish formati) bir xil qolsa, qolgan pipeline
o'zgarishsiz ishlayveradi. Batafsil izoh fayl ichida.

---

## 8. P&ID topologiyasini to'ldirish

`process_topology.py` faylidagi `TOPOLOGY` lug'atini real
zavodingizdagi uskunalar va ularning bog'liqligi bilan to'ldiring —
bu AI Advisor va Predictor'ga sabab-oqibat xulosalar chiqarishga
yordam beradi. Bo'sh qoldirilsa, bu funksiya sokin o'tkazib
yuboriladi.







Boshqa kampiyuterga ko'chirilsa qilinadigan ishlar 

1. Python o'rnatilishi
2. pip install -r requirements.txt o'rnatiladi
3. playwright install chromium   alohida o'rnatiladi requirementsda yo'q 
4. PSQL baza o'zgarish kerak bo'lsa lokolhost emas boshqa baza parolllri va h.k lari to'g'ri qaytadan yoziladi
5. Tarmoq ruxsati	Yangi kompyuter — SCADA'ga, vLLM serveringizga (ngrok), va internetga (o'rnatish uchun) kirish huquqiga ega bo'lishi kerak 
6. yangi sqlga CREATE DATABASE chem_scada; deb db yaratish kerak qolgan jadvallar o'zi avtomatskiy yaratiladi
CREATE TABLE IF NOT EXISTS vision_reports (...)
CREATE TABLE IF NOT EXISTS metric_history (...)
CREATE TABLE IF NOT EXISTS plant_state (...)
CREATE TABLE IF NOT EXISTS advisor_insights (...)
CREATE TABLE IF NOT EXISTS plant_predictions (...)
CREATE TABLE IF NOT EXISTS shift_reports (...)


Test uchun yaratilgan va hozir ishlamayotgan fayllar 
test_promt.py
debug_raw.py
retention_cleanup.py