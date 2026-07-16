# Kimyo reaktori — kichik SCADA/PLC/AI/MES/ERP loyihasi

Bu — kimyoviy reaktorni boshqarish uchun to'liq zanjirni ko'rsatuvchi o'quv/demo loyihasi:

```
Datchik → PLC → SCADA (Flask HMI) → PostgreSQL (Historian) → AI → MES → ERP
```

## Fayllar tuzilmasi va vazifasi

| Fayl | Vazifasi |
|---|---|
| `sensors.py` | 11 ta datchikni simulyatsiya qiladi (harorat, bosim, issiqlik, tezlik, pH, sarf, sath, tebranish, namlik, kuchlanish, tok) |
| `plc.py` | PLC boshqaruv mantig'i — chegaralarga qarab aktuatorlarni yoqadi/o'chiradi, alarm/trip chiqaradi |
| `config.py` | Baza ulanish parametrlari va PLC chegaralari |
| `db/schema.sql` | PostgreSQL jadval sxemasi (6 ta jadval) |
| `database.py` | PostgreSQL bilan ishlash (yozish/o'qish funksiyalari) |
| `ai_analysis.py` | Z-score asosida anomaliya aniqlash (AI qatlami) |
| `mes.py` | Ishlab chiqarish partiyasini kuzatish (MES qatlami) |
| `erp.py` | Xomashyo/energiya xarajati va foyda hisob-kitobi (ERP qatlami) |
| `scada_dashboard.py` | Flask asosidagi SCADA HMI veb-server |
| `templates/dashboard.html` | Brauzerda ko'rinadigan real-vaqt monitoring sahifasi |
| `main.py` | Barcha qatlamlarni bog'lovchi asosiy sikl |

## Nima uchun shu texnologiyalar tanlandi

- **Python** — barcha qatlamni (simulyatsiya, mantiq, AI, veb) bitta tilda yozish imkonini beradi, o'rganish va tez prototip qilish uchun qulay
- **PostgreSQL** — haqiqiy sanoat SCADA tizimlarida ham eng ko'p ishlatiladigan Historian bazalaridan biri
- **Flask** — SCADA HMI o'rnini bosuvchi yengil veb-server (haqiqiy loyihada bu o'rinda Ignition/WinCC/AVEVA turadi)
- **Z-score** — sodda va tez tushuniladigan statistik anomaliya aniqlash usuli (haqiqiy loyihada scikit-learn Isolation Forest yoki LLM-asosidagi tahlil qo'shilishi mumkin)

## O'rnatish va ishga tushirish

### 1. PostgreSQL o'rnatish (agar bo'lmasa)

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install postgresql postgresql-contrib

# PostgreSQL xizmatini ishga tushirish
sudo service postgresql start

# Baza yaratish
sudo -u postgres createdb chem_scada
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'postgres';"
```

`config.py` faylida `DB_CONFIG` qiymatlarini o'zingizning PostgreSQL sozlamalaringizga moslang.

### 2. Python muhitini tayyorlash

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Asosiy simulyatsiyani ishga tushirish

```bash
python main.py
```

Bu: datchik → PLC → PostgreSQL → AI → MES → ERP zanjirini ishga tushiradi va terminalda har sikl natijasini chiqaradi.

### 4. SCADA dashboardni ishga tushirish (alohida terminalda)

```bash
python scada_dashboard.py
```

Brauzerda oching: `http://localhost:5000`

Real vaqt rejimida barcha 11 ta datchik qiymati va alarmlar ko'rinadi (2 soniyada bir yangilanadi).

## Keyingi qadamlar (loyihani kengaytirish uchun)

1. `sensors.py` o'rniga haqiqiy PLC'dan **Modbus TCP** yoki **OPC UA** orqali o'qish (masalan `pymodbus` kutubxonasi bilan)
2. `plc.py` mantig'ini haqiqiy PLC'ga (Siemens/Allen-Bradley) **Structured Text** sifatida ko'chirish
3. `ai_analysis.py`ni **scikit-learn Isolation Forest** yoki **LLM-asosidagi operator assistant**ga kengaytirish
4. Dashboardga **tarixiy grafik** (Chart.js) qo'shish — `/api/trend/<sensor_name>` endpoint allaqachon tayyor
5. Foydalanuvchi huquqlari (operator/muhandis) va parol bilan himoyalangan sozlamalar ekranini qo'shish

## Muhim eslatma

Bu — **o'quv/demo** loyihasi. Haqiqiy sanoat obyektida ishga tushirishdan oldin:
- PLC mustaqil (SCADA'siz ham) ishlashi kerak — xavfsizlik uchun kritik
- Litsenziyalangan muhandis tomonidan HAZOP/LOPA tahlili o'tkazilishi shart
- Alohida xavfsizlik tizimi (SIS) kerak bo'lishi mumkin
