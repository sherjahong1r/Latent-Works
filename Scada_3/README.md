# SCADA AI Monitoring

Sanoat SCADA/HMI dashboardini AI yordamida avtomatik **o'qiydigan**,
**tahlil qiladigan** va **bashorat qiladigan** tizim.

Ekranga qarab turadi, ko'rganini raqamlarga aylantiradi, bazaga yozadi,
tarixga qarab xulosa chiqaradi va 10/20/30 daqiqadan keyin nima
bo'lishini aytadi. Smena oxirida hisobot yozadi.

**Tizim bitta aniq dashboardga bog'lanmagan** — koordinata yozib
berish shart emas, istalgan SCADA/HMI ekranida ishlaydi. Buning
qanday ishlashi [5-bo'limda](#5-istalgan-dashboardda-ishlashi).

---

## 1. Arxitektura

```
                  ┌──────────────────────┐
                  │   capture_pipeline    │  har 45s
                  │  skrinshot → AI → JSON│
                  └───────────┬───────────┘
                              │  (shu yerning o'zida, sinxron)
                              ▼
                      ai_advisor.run_cycle()
                              │
              vision_reports + metric_history (Postgres)
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
   ┌─────────────┐   ┌────────────────┐   ┌─────────────────┐
   │ ai_advisor   │   │   predictor     │   │  shift_report   │
   │ Plant State  │   │ 1–15 daq        │   │  12 soatda 1    │
   │ Memory       │   │ (moslashuvchan) │   │                 │
   │ + Anomaliya  │   │ 10/20/30 daq    │   │                 │
   └──────┬───────┘   └────────┬────────┘   └────────┬────────┘
          ▼                    ▼                     ▼
   advisor_insights     plant_predictions       shift_reports
   plant_state
          │                    │                     │
          └────────────────────┼─────────────────────┘
                               ▼
                    external_api.py (ALOHIDA jarayon)
                    → http://localhost:5001
```

**Ikkita mustaqil jarayon:**

| Jarayon | Vazifasi | Kerakmi |
|---|---|---|
| `main.py` | ma'lumot yig'ish, tahlil, bashorat | **DOIM** ishlab turishi kerak |
| `external_api.py` | ko'rish uchun interfeys | ixtiyoriy, xohlagan vaqtda |

> **Muhim:** `ai_advisor` alohida oqim (thread) emas. U
> `capture_pipeline` ichida, har skrinshot tahlilidan keyin **sinxron**
> chaqiriladi. Shuning uchun xom JSON va AI xulosasi **deyarli bir
> vaqtda** chiqadi — maslahatchi doim eng oxirgi JSON'ni tahlil qiladi.
> Eski mustaqil 120 soniyalik rejimda sinash uchun `py ai_advisor.py`
> ni alohida ishga tushiring — lekin `main.py` bilan **birga emas**,
> aks holda advisor ikki marta chaqiriladi.

---

## 2. Fayllar va ularning vazifasi

### Ishga tushiriladigan fayllar

| Fayl | Vazifasi |
|---|---|
| `main.py` | Asosiy quvur. `capture_pipeline`, `predictor`, `shift_report` ni oqimlarda ishga tushiradi, biri yiqilsa 10 s dan keyin qayta tiklaydi. |
| `external_api.py` | FastAPI interfeysi. Faqat bazani **o'qiydi** (GET), hech narsa yozmaydi. 5 ta API endpoint + bosh sahifa. |
| `camera_calibrate.py` | Faqat kamera rejimida, kamera joylashtirilgach **bir marta**: kadrda ekranning 4 burchagini sichqoncha bilan belgilaysiz → `camera_calibration.json`. |

### Yadro modullari

| Fayl | Vazifasi |
|---|---|
| `config.py` | Barcha sozlamalar bitta joyda. Deyarli hammasi `.env` orqali ham beriladi. |
| `database.py` | Postgres ulanishi, jadvallarni yaratish, o'qish/yozish yordamchilari. |
| `llm_client.py` | Provayderdan mustaqil LLM mijozi — Ollama ham, vLLM ham bir xil interfeys orqali. Qayta urinish va JSON rejimi shu yerda. |
| `vision_toolkit.py` | **Eng muhim fayl.** Ekranni mazmun hajmiga qarab bo'laklarga bo'ladi, bo'laklarni parallel AI'ga yuboradi, javoblarni bitta JSON'ga birlashtiradi. Sekin bo'lakni keyingi siklda o'zi ikkiga bo'ladi. |
| `capture_source.py` | Kadr manbalari: veb-sahifa (`url`), kamera (`camera`), dastur oynasi (`window`), ekran (`screen`). Kamerada ekranni 4 burchak bo'yicha kesib, qiyaligini to'g'rilaydi; buzilgan kadrni tashlaydi. |
| `capture_pipeline.py` | 45 soniyalik sikl: kadr → `vision_toolkit` → bazaga yozish → `ai_advisor.run_cycle()` (har 2-o'qishda, fonda). |
| `ai_advisor.py` | Plant State Memory (zavod "xotirasi"), tarixiy tahlil, tavsiya. Anomaliya va topologiyani hisobga oladi. |
| `anomaly_detector.py` | Statistik anomaliya (z-score). **O'z ML modelingizni shu yerga ulaysiz** — [7-bo'lim](#7-oz-ml-modelingizni-ulash). |
| `predictor.py` | 10/20/30 daqiqalik bashorat. Chiziqli ekstrapolyatsiya + fizik va statistik cheklovlar, keyin LLM izohi. |
| `shift_report.py` | Har 12 soatda smena hisoboti. |
| `process_topology.py` | P&ID/jarayon bog'liqligi. Bo'sh bo'lsa sokin o'tkazib yuboriladi — [8-bo'lim](#8-pid-topologiyasini-toldirish). |

### Interfeys

| Fayl | Vazifasi |
|---|---|
| `dashboard.html` | Butun interfeys — HTML, CSS, JS bitta faylda. Kunduzgi/tungi rejim, 6 ta bo'lim, qidiruv. Tashqi kutubxona yo'q (faqat shrift). |

> `external_api.py` bu faylni **har so'rovda diskdan qayta o'qiydi**.
> Dizaynni o'zgartirsangiz serverni qayta ishga tushirish shart emas —
> brauzerni yangilash kifoya. Fayl topilmasa API ishlayveradi, faqat
> bosh sahifada ogohlantirish chiqadi.

### Yordamchi / ishlatilmayotgan fayllar

| Fayl | Holati |
|---|---|
| `retention_cleanup.py` | Qo'lda ishga tushiriladi. Avtomatik chaqirilmaydi. |
| `test_promt.py`, `debug_raw.py` | Sinov skriptlari. Quvurning bir qismi emas. |
| `alarm_correlation.py` | **Hech kim import qilmaydi.** Tayyor kod, lekin quvurga ulanmagan. |
| `operating_mode.py` | **Hech kim import qilmaydi.** Tayyor kod, lekin quvurga ulanmagan. |

> Oxirgi ikkitasi ishlayotgan tizimga hech qanday ta'sir qilmaydi.
> Kerak bo'lsa `ai_advisor.py` ga `process_topology` qanday ulangan
> bo'lsa, xuddi shunday ulash mumkin.

---

## 3. O'rnatish

```bash
pip install -r requirements.txt
playwright install chromium        # requirements.txt da YO'Q, alohida
```

Keyin `.env` faylini yarating (`.env.example` dan nusxa oling) va
haqiqiy qiymatlarni yozing: baza paroli, SCADA manzili, model
manzillari, API kaliti.

> `.env` fayli `.gitignore` da — hech qachon git'ga tushmaydi.
> Parollarni `config.py` ga to'g'ridan-to'g'ri yozmang.

Postgres'da bitta baza yarating:

```sql
CREATE DATABASE chem_scada;
```

Qolgan **6 ta jadval avtomatik yaratiladi** — `init_all_tables()`
`main.py` va `external_api.py` ishga tushganda o'zi chaqiradi.

| Jadval | Nima saqlaydi |
|---|---|
| `vision_reports` | Har bir skrinshotning xom AI tahlili (JSON) |
| `metric_history` | Har bir raqamli o'lchov, vaqt bo'yicha (time-series) |
| `plant_state` | Zavodning joriy "xotirasi" (bitta qator) |
| `advisor_insights` | AI Advisor xulosalari tarixi |
| `plant_predictions` | Bashorat natijalari |
| `shift_reports` | Smena hisobotlari |

---

## 4. Ishga tushirish

**Ikkita alohida terminal kerak.**

```bash
# 1-terminal — asosiy quvur, doim ochiq turishi kerak
py main.py

# 2-terminal — interfeys, ixtiyoriy
py external_api.py
```

Keyin brauzerda:

- **Interfeys:** http://localhost:5001
- **API hujjatlari (Swagger):** http://localhost:5001/docs

**Production'da interfeysni** shunday ko'targan ma'qul:

```bash
uvicorn external_api:app --host 0.0.0.0 --port 5001
```

> `--reload` faqat development uchun. Avtomatik qayta ishga tushirish
> kerak bo'lsa Windows Service, `systemd` yoki `pm2`/`supervisor`
> ishlating — bu skriptlar buni o'zi qilmaydi.

**To'xtatish:** `CTRL+C`.

### Birinchi marta ishga tushganda nima kutish kerak

| Vaqt | Nima chiqadi |
|---|---|
| ~45–90 s | birinchi xom JSON va birinchi AI xulosasi (birga) |
| ~1–15 daq | birinchi bashorat |
| 12 soat | birinchi smena hisoboti |

Ya'ni **darrov hamma bo'lim to'lmaydi** — bu normal. Interfeys bo'sh
bo'limlarda "Hozircha ... yo'q" deb yozib turadi.

---

## 5. Istalgan dashboardda ishlashi

Tizim ekranni **mazmuniga qarab** bo'laklarga bo'ladi:
piksellar farqini o'lchab, panellar orasidagi bo'sh joylarni topadi va
kesishni **o'sha bo'shliqlarga** joylashtiradi. Koordinata yozib berish
kerak emas — boshqa SCADA'ga ulasangiz ham o'zi moslashadi.

Har bo'lak **asl o'lchamida** (kichraytirilmasdan) parallel yuboriladi,
javoblar bitta JSON'ga birlashtiriladi.

### `VISION_MODE` — uchta rejim

| Rejim | Nima qiladi | Qachon |
|---|---|---|
| `grid` | Mazmunga qarab avtomatik bo'ladi | **Standart.** Deyarli doim shu. |
| `regions` | `config.py` dagi qo'lda yozilgan `VISION_REGIONS` | Faqat bitta aniq ekran uchun |
| `full` | Butun ekran bitta so'rovda | Zaxira. Eng sekin, eng kam aniq. |

### O'lchangan natijalar

Bir xil ekran, bir xil server holati, 57 ta qo'lda tekshirilgan qiymat:

| Rejim | Vaqt (mediana) | Aniqlik | Uydirma qiymat |
|---|---|---|---|
| `grid` (mazmunga qarab) | 69 s | **100 %** | **0** |
| qo'lda yozilgan bo'laklar | 58 s | 98.2 % | 3 |
| butun ekran, 640 px | — | 14 % | 67 % |

Avtomatik bo'lish qo'lda yozilganidan **aniqroq** chiqdi — ustiga
ustak koordinata yozish kerak emas. Qo'lda usul 3 ta mavjud bo'lmagan
qiymat to'qib chiqargan, avtomatik usul esa bittasini ham chiqarmagan.

### Boshqa dashboardda sinovdan o'tgan

Universallik aytib qo'yilgan da'vo emas — **mutlaqo boshqa tizimda
sinab ko'rilgan**:

| | Asosiy dashboard | Sinov dashboardi |
|---|---|---|
| Ishlab chiqaruvchi | Inductive Automation | Ecava IntegraXor |
| Turi | suv tozalash, jadvallar | havo tayyorlash (AHU), SVG sxema |
| O'lcham | 1920 x 1080 | **3840 x 2160 (4K)** |
| Koordinata yozilganmi | yo'q | yo'q |
| Natija | 57/57 qiymat | **17/17 qiymat, 6 uskuna, 1 alarm** |
| Vaqt | 69 s | **15 s** |

Ikkinchisida barcha qiymatlar (`CHWTS 25.96`, `VSD FB 45.1`,
`AIR FLOW 97`, `RAH 96.4`, setpointlar) ekrandagi bilan **bir xil**
chiqdi. Hech qanday sozlash qilinmadi — faqat `SCADA_URL` almashtirildi.

### Yangi dashboardga ulash

1. `.env` da `SCADA_URL` ni yangi manzilga o'zgartiring.
2. Boshqa hech narsa kerak emas — `main.py` ni ishga tushiring.
3. Birinchi sikldan keyin interfeysning **"Xom JSON"** bo'limiga qarang:
   ekrandagi qiymatlar chiqyaptimi?

Agar ekran juda zich bo'lsa va qiymatlar yetishmasa:

```env
VISION_GRID_COLS=3         # ko'proq bo'lakka bo'lish
VISION_GRID_ROWS=3
VISION_REGION_MAX_TOKENS=3500
```

SCADA veb-emas, desktop dastur bo'lsa — `.env` da
`CAPTURE_MODE=window` qiling va `config.py` da `SCADA_WINDOW_TITLE` ni yozing.

### Kamera orqali (dashboard boshqa monitorda)

1. Kamerani monitorga **tik** qarating, butun ekran kadrga sig'sin, qotiring.
   Monitorning uyqu rejimini o'chiring.
2. `.env` da:
   ```env
   CAPTURE_MODE=camera
   CAMERA_INDEX=1        # 0 — noutbuk kamerasi, 1 — tashqi USB kamera
   ```
3. Bir marta kalibrlash: `py camera_calibrate.py` → oynada ekranning
   4 burchagini bosing → `ENTER`. Kamera surilsa — qayta kalibrlang.
4. `py main.py`.

Kadrdan stol va monitor tagligi kesib tashlanadi, qiya ekran to'g'ri
to'rtburchakka keltiriladi. Kadr USB orqali to'liq kelmasa (pastki qismi
kulrang), monitor o'chsa yoki fokus yo'qolsa — kadr tashlanadi va
qaytadan olinadi. Kamera bir vaqtda faqat bitta dasturda ochiladi.

### Bo'laklarga bo'lish va tezlik

Ekran teng panjaraga emas, **mazmun hajmiga** qarab bo'linadi: eng zich
bo'lak panellar orasidagi bo'sh joydan ikkiga bo'linadi, jadval esa hech
qachon o'rtasidan kesilmaydi (pastki yarmida ustun nomlari qolmaydi).
Har siklda bo'laklar vaqti o'lchanadi — eng sekini qolganlaridan 1.6
barobar sekin bo'lsa, keyingi siklda o'zi ikkiga bo'linadi
(`VISION_MAX_TILES` gacha). Hammasi koordinatasiz, istalgan dashboardda.

Model jadvalni `H|sarlavhalar` + `D|qator` ko'rinishida yozadi — nom har
katakda takrorlanmaydi, javob ~40 % qisqa. Qiymat birligi nomga qo'shiladi
(`Clearwell ft`, `Clearwell %`), shuning uchun bitta nom ostida goh foiz,
goh hajm yozilib qolmaydi.

---

### Ma'lumot sifati uchun himoyalar

AI modeli notanish ekranda ba'zan chalkashadi. Quyidagilar
`vision_toolkit.py` da avtomatik tozalanadi — hech qanday sozlash
talab qilmaydi va ekranga bog'liq emas:

| Muammo | Misol | Nima qilinadi |
|---|---|---|
| Qiymat nom o'rniga tushib qolgan | `R\|19.6 in LOH\|19.6` | Nom raqamdan boshlanib, o'sha raqam qiymatning o'ziga teng bo'lsa — satr tashlanadi |
| Bo'lak chegarasi yozuvni kesgan | `asin #3` (`Basin #3` yonida) | Qiymati bir xil va nomi ikkinchisining ichiga so'z o'rtasidan kirgan kalit tashlanadi |
| Yorliq holat deb yozilgan | `E\|BMS\|BMS` | Nomi va qiymati bir xil yozuv tashlanadi |
| Yalang raqam nom sifatida | `E\|1\|Off` | Faqat raqamdan iborat uskuna nomi tashlanadi |
| Nom goh katta, goh kichik harf | `Basin #1` / `basin #1` | `metric_history` ga yozishda eng ko'p ishlatilgan yozilishga keltiriladi (xom JSON tegilmaydi) |

> Oxirgisi `database.py` da. Sababi: bitta ko'rsatkich ikki xil nom
> bilan yozilsa, time-series ikkiga bo'linadi va tendensiya buziladi.

## 6. Interfeys

Chap tomonda doimiy ro'yxat, o'ngda tanlangan bo'lim. **6 ta bo'lim:**

| Bo'lim | Nima ko'rsatadi | Manba |
|---|---|---|
| Bosh sahifa | qolgan 5 bo'limning qisqa ko'rinishi + oxirgi o'qish | hammasi |
| AI Maslahatchi | oxirgi xulosa (tendensiya, tavsiya) + tarix | `/api/insights` |
| Zavod xotirasi | joriy holat, tendensiyalar, anomaliyalar, tekshiruvlar | `/api/plant-state` |
| Bashorat | 10/20/30 daqiqalik bashoratlar, xavf darajasi | `/api/predictions` |
| Smena hisobotlari | 12 soatlik hisobotlar | `/api/shift-reports` |
| Xom JSON | har bir o'qishning to'liq JSON'i + qidiruv | `/api/reports` |

**Imkoniyatlar:**

- **Kunduzgi / tungi / avto** rejim — tanlov brauzerda eslab qolinadi.
  "Avto" tizim sozlamasiga ergashadi.
- Har **20 soniyada** avtomatik yangilanadi; **⏸ To'xtatish** tugmasi
  bilan to'xtatib turish mumkin (bir yozuvni tinch o'qish uchun).
- **`1`–`6` tugmalari** bilan bo'limlar orasida tez o'tish.
- Xom JSON bo'limida **qidiruv** — nom yoki qiymat bo'yicha filtrlaydi.
- Vaqtlar "4 soat oldin" ko'rinishida; ustiga kursor olib borsangiz
  aniq sana-vaqt chiqadi.
- Telefonda ham ochiladi (yon aylanma chiqmaydi).

> Dizayn o'zgardi, **ko'rsatiladigan ma'lumotlar tarkibi o'zgarmadi** —
> o'sha 6 bo'lim, o'sha 5 endpoint, o'sha maydonlar.

### API endpointlar

Hammasi `GET`, hammasi oxirgi 10 ta yozuvni qaytaradi:

```
GET /api/reports          → id, ts, model, payload
GET /api/insights         → id, ts, severity, summary, trend_analysis, recommendation
GET /api/plant-state      → ts, state   (yoki null)
GET /api/predictions      → id, ts, interval_seconds, risk_level, summary, details
GET /api/shift-reports    → id, ts, period_start, period_end, report
```

---

## 7. O'z ML modelingizni ulash

`anomaly_detector.py` dagi `compute_anomaly_report()` funksiyasini
o'zingiznikiga almashtiring. **Funksiya imzosi (kirish/chiqish
formati) bir xil qolsa**, quvurning qolgan qismi o'zgarishsiz
ishlayveradi. Batafsil izoh fayl ichida.

---

## 8. P&ID topologiyasini to'ldirish

`process_topology.py` dagi `TOPOLOGY` lug'atini real zavodingizdagi
uskunalar va ularning bog'liqligi bilan to'ldiring. Bu AI Advisor va
Predictor'ga **sabab-oqibat** xulosalar chiqarishga yordam beradi
("Filter #4 to'xtagani uchun Combined Flow tushdi"). Bo'sh qoldirilsa
sokin o'tkazib yuboriladi.

---

## 9. Asosiy sozlamalar

Hammasi `config.py` da, ko'pchiligi `.env` orqali ham beriladi.

### Vaqt oraliqlari

| Sozlama | Standart | Ma'nosi |
|---|---|---|
| `SCREENSHOT_INTERVAL_SECONDS` | 45 | skrinshotlar orasidagi vaqt |
| `PREDICTION_INTERVAL_MIN/MAX_SECONDS` | 60 / 900 | bashorat oralig'i (o'zi moslashadi) |
| `PREDICTION_HORIZONS_MINUTES` | `[10, 20, 30]` | necha daqiqaga bashorat |
| `SHIFT_REPORT_INTERVAL_HOURS` | 12 | smena uzunligi |
| `ENABLE_SHIFT_REPORT` | `True` | smena hisobotini o'chirish/yoqish |

### Ko'rish (vision)

| Sozlama | Standart | Ma'nosi |
|---|---|---|
| `VISION_MODE` | `grid` | bo'lish usuli — [5-bo'lim](#5-istalgan-dashboardda-ishlashi) |
| `VISION_GRID_COLS` / `ROWS` | 2 / 2 | nechta bo'lakka bo'lish |
| `VISION_GRID_OVERLAP` | 0.06 | bo'laklar ustma-ust tushish ulushi |
| `IMAGE_MAX_WIDTH` | **960** | butun ekran rejimi uchun |
| `IMAGE_JPEG_QUALITY` | **80** | butun ekran rejimi uchun |
| `VISION_REGION_JPEG_QUALITY` | 88 | bo'laklar uchun |
| `VISION_MAX_TOKENS` | **3000** | javob uzunligi chegarasi |

> ⚠️ **`IMAGE_MAX_WIDTH` ni pasaytirmang.** 640 px da 1920×1080 ekran
> 640×360 ga tushadi, raqamlar 3–5 piksel balandlikda qoladi va model
> ularni **to'qib chiqara boshlaydi**. O'lchangan: aniqlik 14 %,
> uydirma 67 %. Xuddi shunday, `VISION_MAX_TOKENS` ni 1500 dan
> pasaytirsangiz javob **o'rtasidan kesiladi** va butun-butun panellar
> yo'qoladi.

### Anomaliya va bashorat

| Sozlama | Standart | Ma'nosi |
|---|---|---|
| `ANOMALY_Z_THRESHOLD` | 3.0 | necha sigma anomaliya hisoblanadi |
| `ANOMALY_LOOKBACK_MINUTES` | 30 | qancha orqaga qarash |
| `ANOMALY_REQUIRE_CONSECUTIVE` | `True` | ketma-ket ikki marta chiqsagina hisoblash |
| `PREDICTION_MIN_FIT_R2` | 0.5 | chiziq mos kelmasa bashorat cheklanadi |

### Modellar

| Sozlama | Standart |
|---|---|
| `LLM_PROVIDER` | `ollama` (yoki `vllm`) |
| `VISION_MODEL` | `qwen3-vl:8b` |
| `OLLAMA_TEXT_MODEL` | `qwen3:14b` |

---

## 10. Boshqa kompyuterga ko'chirish

1. **Python** o'rnatiladi.
2. `pip install -r requirements.txt`
3. `playwright install chromium` — **alohida**, requirements'da yo'q.
4. **`.env`** yaratiladi: baza manzili/paroli (endi `localhost` emas),
   SCADA manzili, model manzili, API kaliti.
5. **Tarmoq ruxsati:** yangi kompyuter SCADA'ga, LLM serveringizga
   (ngrok/vLLM) va internetga (o'rnatish uchun) kira olishi kerak.
6. Postgres'da `CREATE DATABASE chem_scada;` — qolgan jadvallar
   avtomatik yaratiladi.
7. `py main.py` → bir-ikki siklni kuting → interfeysning "Xom JSON"
   bo'limida qiymatlar chiqayotganini tekshiring.

---

## 11. Tez-tez uchraydigan muammolar

| Belgi | Sabab | Yechim |
|---|---|---|
| `python` ishlamaydi, Microsoft Store ochiladi | Windows'ning yorlig'i (alias) | `py` ishlating, yoki Settings → Apps → App execution aliases dan o'chiring |
| Interfeys ochiladi, lekin hamma bo'lim bo'sh | `main.py` ishlamayapti yoki hali birinchi sikl tugamagan | `main.py` terminalini tekshiring, 1–2 daqiqa kuting |
| Bosh sahifada "Interfeys fayli topilmadi" | `dashboard.html` yonida yo'q | Faylni `external_api.py` yoniga qo'ying |
| Qiymatlar chiqyapti, lekin noto'g'ri raqamlar | rasm juda kichraytirilgan | `IMAGE_MAX_WIDTH` ni 960 dan pasaytirmang |
| Javobning oxiri yo'q, panellar yetishmayapti | token chegarasi past | `VISION_MAX_TOKENS` ni oshiring |
| Bashorat manfiy yoki imkonsiz raqam beryapti | ma'lumot kam yoki sakrash bo'lgan | `PREDICTION_MIN_POINTS` / `PREDICTION_MIN_FIT_R2` ni oshiring |
| Baza ulanmayapti | `.env` da parol/manzil xato | `DB_CONFIG` qiymatlarini tekshiring |
