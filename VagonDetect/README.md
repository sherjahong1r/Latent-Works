# VagonDetect — vagon raqami, tonna va hajmni aniqlash

Kamera yoki videodan o'tayotgan har bir vagonning **8 xonali raqamini**, **yuk ko'tarishini (t)** va **kuzov hajmini (m³)** aniqlaydi va natijani matn hisobot va rasmlar ko'rinishida saqlaydi. Tizim 24/7 ishlashga mo'ljallangan: poyezd istalgan vaqtda (kechasi yoki kunduzi) kelishi mumkin.

## Uchta buyruq (Linux)

Terminalda loyiha papkasiga kiring (`cd VagonDetect`), keyin:

```bash
./install.sh              # 1) O'RNATISH -- bir marta; kerakli hamma narsani o'zi o'rnatadi
./run.sh IMG_2717.MOV     # 2) VIDEO BILAN SINOV -- video tugaganda dastur o'zi to'xtaydi
./run.sh 0                # 3) KAMERA -- o'zingiz to'xtatmaguningizcha uzluksiz ishlaydi
```

| Buyruq | Nima qiladi | Qachon to'xtaydi |
|---|---|---|
| `./install.sh` | `.venv` muhitini yaratadi, PyTorch va boshqa paketlarni o'rnatadi, GPU'ni tekshiradi | O'zi tugaydi (internet tezligiga qarab 5–20 daqiqa) |
| `./run.sh video.mp4` | Videoni o'z tezligida (real vaqtda) tahlil qiladi, hisobot va rasmlarni yozadi | Video tugaganda o'zi |
| `./run.sh 0` | USB kameradan uzluksiz o'qiydi | Faqat siz to'xtatganda |
| `./run.sh "rtsp://admin:parol@192.168.1.64:554/Streaming/Channels/101"` | IP-kameradan uzluksiz o'qiydi | Faqat siz to'xtatganda |

- **To'xtatish:** oynada `q` yoki terminalda `Ctrl+C`. Joriy poyezd hisoboti saqlanadi.
- **Kamera rejimida** poyezd istalgan paytda kelsa yoziladi; kamera uzilsa dastur o'zi qayta ulanadi; kutilmagan xato bo'lsa 5 soniyadan keyin o'zi davom etadi.
- `./run.sh` birinchi marta ishga tushsa va hali o'rnatilmagan bo'lsa, avval `./install.sh` ni o'zi chaqiradi.
- Terminal yopilsa dastur ham to'xtaydi. Kompyuter yoqilganda o'zi ishga tushadigan doimiy rejim uchun pastdagi **24/7 servis** bo'limiga qarang.
- Windows'da xuddi shular: `install.bat`, `run.bat video.mp4`, `run.bat 0`.

Qo'shimcha parametrlar:
- `--natijalar <papka>` — natijalarni `trains/` o'rniga boshqa papkaga yozadi (sinov uchun qulay);
- `--oynasiz` — oyna ochmasdan ishlaydi (server/servis uchun); `--oynali` — oyna bilan (standart holat);
- `--vaqt "2025-12-10 16:04:40"` — videoning haqiqiy boshlangan vaqti (faqat video fayl uchun);
- `--tez` — video faylni kutmasdan, imkon qadar tez tahlil qiladi.

## Fayllar va ularning vazifasi

**Dastur ishlashi uchun kerak** (boshqa kompyuterga faqat shular ko'chiriladi, jami ~51 MB):

| Fayl | Vazifasi |
|---|---|
| `logic_N_T_V.py` | Asosiy dastur: kamera yoki videoni o'qiydi, vagonlarni kuzatadi, raqam va tonna/hajmni o'qiydi, hisobot va rasmlarni yozadi |
| `detection4.pt` | Model: kadrda vagon raqami yozilgan joyni topadi |
| `classificationvagon.pt` | Model: topilgan joydagi 8 ta raqamni o'qiydi |
| `detect-t-v-small.pt` | Model: tonna/hajm plastinkasini topadi |
| `cllas-t-vsmall.pt` | Model: plastinkadagi belgilarni (raqamlar, "t", "m3") o'qiydi |
| `requirements.txt` | Kerakli Python paketlari ro'yxati (sinovdan o'tgan versiyalar) |
| `install.sh` | O'rnatuvchi: muhit va paketlarni o'rnatadi; `--servis` bilan 24/7 servis qiladi |
| `run.sh` | Ishga tushiruvchi: o'rnatilmagan bo'lsa avval o'rnatadi, keyin dasturni yurgizadi |
| `kamera_qidir.py` | Yordamchi: USB va tarmoqdagi IP-kameralarni topadi, ishlaydigan RTSP manzilni aniqlaydi |
| `README.md` | Shu qo'llanma |
| `install.bat`, `run.bat` | `install.sh` / `run.sh` ning Windows uchun varianti (Linuxda kerak emas) |

**Dastur yoki o'rnatuvchi o'zi yaratadi** (ko'chirilmaydi):

| Papka | Nima |
|---|---|
| `.venv/` | Python muhiti va paketlar. Shu kompyuterga bog'langan; `install.sh` qayta yaratadi |
| `engines/` | Modellarning shu kompyuter GPU'siga moslab tezlashtirilgan nusxalari (TensorRT). Birinchi ishga tushishda o'zi yaratiladi |
| `trains/` | Natijalar: kunlik hisobotlar va vagon rasmlari |
| `__pycache__/` | Python keshi |

Sinov videolari (`IMG_*.MOV`, `*.mp4`) va `_final_test/` (sinov jurnallari) dastur ishlashi uchun kerak emas.

## O'rnatish — bitta buyruq

```bash
cd VagonDetect
./install.sh
```

Windows 10/11 da: avval [Python 3.10+](https://www.python.org/downloads/) o'rnating ("Add to PATH" ni belgilang), keyin `install.bat` ni ikki marta bosing.

**Oldindan bo'lishi kerak** (o'rnatuvchi bularni o'rnatmaydi):
- Linux: Ubuntu yoki Debian (Ubuntu 22.04 da sinalgan), x86_64 yoki ARM64; Python 3.10 yoki yangiroq (Ubuntu'da tayyor turadi);
- internet (faqat o'rnatish paytida);
- NVIDIA GPU'li kompyuterda — NVIDIA drayveri (`nvidia-smi` buyrug'i ishlashi kerak);
- NVIDIA Jetson'da — JetPack 6 (`sudo apt install nvidia-jetpack`).

**Nimalar o'rnatiladi** (hammasi loyiha ichidagi `.venv` papkasiga; tizim Python'iga tegmaydi):

| Nima | Nima uchun kerak |
|---|---|
| PyTorch, torchvision | Modellarni ishlatadigan neyron tarmoq dvigateli. Kompyuterdagi GPU va CUDA versiyasiga mos varianti tanlanadi; NVIDIA GPU'li kompyuterda CUDA kutubxonalari bilan birga keladi (eng katta qism) |
| ultralytics | YOLO kutubxonasi: 4 ta modelni yuklaydi va ishlatadi |
| opencv-python | Kamera va videoni o'qish, tasvirga ishlov, ekrandagi oyna |
| lap | Vagonlarni kadrdan kadrga kuzatish (treker) uchun |
| numpy, matplotlib, pillow, polars va boshqalar | ultralytics talab qiladigan yordamchi paketlar (o'zi qo'shilib o'rnatiladi) |
| openvino | Faqat GPU'siz Intel/AMD kompyuterda: tonna/hajm detektorini CPU'da 2–3 barobar tezlatadi |
| nvidia-cudss, onnx, onnxslim, onnxruntime | Faqat Jetson'da: Jetson uchun PyTorch va modellarni TensorRT'ga o'tkazishga kerak. Tizimdagi TensorRT `.venv` ga ulanadi |
| Tizim paketlari (`apt`, faqat yo'q bo'lsa; `sudo` paroli so'raladi) | `python3-venv`, `python3-pip`, `libgl1`, `libglib2.0-0`; Jetson'da yana `libopenblas0`, `libnuma1`, `libgomp1` |

Hajmi: NVIDIA GPU'li kompyuterda taxminan 3 GB yuklanadi; Jetson'da ~0.5 GB yuklanadi va `.venv` 1.5 GB joy oladi. O'rnatilgach dastur internetsiz ishlaydi.

O'rnatish oxirida tekshiruv natijasi chiqadi, masalan:
```
  torch 2.11.0 | GPU: Orin
  GPU hisoblash testi: OK
```
`GPU: YOQ (CPU)` chiqsa, dastur ishlaydi, lekin real vaqt uchun sekin (~2 kadr/s).
`install.sh` ni qayta ishga tushirish xavfsiz: o'rnatilganiga tegmaydi, yetishmaganini qo'shadi.

## Boshqa kompyuterga ko'chirish

1. Eski kompyuterda kerakli fayllarni bitta arxivga yig'ing:
```bash
cd VagonDetect
tar czf ~/VagonDetect_kochirish.tar.gz logic_N_T_V.py detection4.pt classificationvagon.pt \
  detect-t-v-small.pt cllas-t-vsmall.pt requirements.txt install.sh run.sh README.md kamera_qidir.py
```
2. Arxivni yangi kompyuterga o'tkazing (fleshka, `scp` va h.k.) va oching:
```bash
mkdir VagonDetect && tar xzf VagonDetect_kochirish.tar.gz -C VagonDetect && cd VagonDetect
```
3. Yuqoridagi uchta buyruqdan foydalaning: `./install.sh`, keyin `./run.sh ...`.

`.venv`, `engines`, `__pycache__`, `trains`, `_final_test` ko'chirilmaydi: ular eski kompyuterga bog'langan yoki o'zi yaratiladi.

| Yangi kompyuter | Nima bo'ladi |
|---|---|
| NVIDIA GPU'li kompyuter (drayver o'rnatilgan) | `install.sh` CUDA'li PyTorch o'rnatadi, modellar GPU'da PyTorch rejimida ishlaydi. **Bu yo'l hali sinalmagan** (sinovlar faqat Jetson'da o'tkazilgan): birinchi ishga tushirishda `Qurilma: GPU` chiqishini tekshiring |
| NVIDIA Jetson (JetPack 6) | `install.sh` Jetson uchun PyTorch va TensorRT'ni o'zi sozlaydi. 2026-10-06 da Jetson Orin Nano'da toza papkada sinalgan: o'rnatish, GPU, TensorRT ishladi, video natijasi asl muhitdagi bilan bir xil chiqdi |
| GPU'siz kompyuter | Ishlaydi, lekin ~2 kadr/s: real vaqt uchun yetmaydi |

**Jetson'ga ko'chirganda `engines/` haqida.** Birinchi ishga tushishda 4 ta model TensorRT'ga o'tkaziladi (~20 daqiqa) va bu paytda ko'p xotira kerak. 8 GB xotirali Jetson'da shu vaqtda boshqa dasturlarni (brauzer, VS Code) yoping: xotira yetmasa model sekin PyTorch rejimida qoladi (jurnalda `TensorRT ga o'tkazib bo'lmadi`), bu holda dasturni qayta ishga tushiring. Yangi Jetson **xuddi shu model va xuddi shu JetPack versiyasida** bo'lsa, `engines` papkasini ham arxivga qo'shing — qayta qurish kerak bo'lmaydi. Boshqa turdagi kompyuterga `engines` ni ko'chirmang.

## Kamera bilan sinash

**USB kamera** (veb-kamera):
```bash
./run.sh 0 --natijalar kamera_test
```
`0` — birinchi USB kamera. 20–30 soniyada modellar yuklanadi va kamera tasviri bilan oyna ochiladi; modellar shu zahoti ishlay boshlaydi. `--natijalar kamera_test` sinov natijalarini `trains/` ga aralashtirmaslik uchun.

Haqiqiy vagon bo'lmasa, kamerani sinov videosi o'ynayotgan ekranga qarating: video to'liq ekranda bo'lsin va butun ekran kadrga sig'sin. 2026-10-06 dagi sinovda Logitech C920 veb-kamerasi orqali `IMG_2717.MOV` dagi 7 vagonning hammasi to'g'ri raqam bilan yozildi.

Oyna boshqa oynalar orqasida qolsa — `Alt+Tab` ("Wagon Number + TONNA/HAJM RealTime").

**IP-kamera.** Manzilini bilmasangiz, avval qidiring:
```bash
.venv/bin/python kamera_qidir.py --login admin --parol 12345
```
U ishlaydigan `rtsp://...` manzilni ko'rsatadi; keyin `./run.sh "rtsp://..."`.

## Jetson videosini Windowsda real vaqtda ko'rish

Jetsonda grafik ish stoli bo'lsa, VNC serverni bir marta o'rnating:

```bash
sudo apt update
sudo apt install -y x11vnc
x11vnc -display :0 -auth guess -forever -shared -rfbport 5900
```

Jetsonning Tailscale manzilini oling:

```bash
tailscale ip -4
```

Windowsga RealVNC Viewer o'rnating va Jetsonning shu manziliga, masalan
`100.x.x.x:5900`, ulang. Keyin Jetsonda videoni ishga tushiring:

```bash
cd ~/VagonDetect
./run.sh IMG_3032.MOV
```

GPU Jetsonda ishlaydi, belgilangan video oynasi Windowsda real vaqtda ko'rinadi.
Ekransiz Jetson bo'lsa, VNC o'rniga NoMachine virtual desktop ishlating.

## 24/7 servis (Linux) — kompyuter yoqilganda o'zi ishga tushadi

```bash
./install.sh --servis "rtsp://admin:parol@192.168.1.64:554/Streaming/Channels/101"     # IP-kamera
./install.sh --servis 0                                                                # USB kamera
```
Servis oynasiz ishlaydi; o'rnatishda `sudo` paroli so'raladi.

Servis bilan ishlash:
```bash
systemctl status vagon-detect        # holati
journalctl -u vagon-detect -f        # jonli jurnal (har 10 daqiqada "💓 ishlayapti" yozuvi)
sudo systemctl restart vagon-detect  # qayta ishga tushirish
sudo systemctl stop vagon-detect     # to'xtatish (joriy poyezd hisoboti saqlanadi)
```

### 24/7 ishonchliligi uchun nimalar qilingan
- **Kamera uzilsa** (tarmoq, elektr, kamera qayta yuklansa) — dastur to'xtamaydi, 1–30 s oralig'ida qayta ulanishga urinib turadi.
- **Oqim qotib qolsa** (kadr kelmay qolsa) — 20 s dan keyin avtomatik qayta ulanadi.
- **Kutilmagan xato bo'lsa** — 5 s dan keyin dastur o'zi davom etadi. Poyezd sessiyasi va yozilgan vagonlar yo'qolmaydi.
- **Kechikish to'planmaydi** — har doim kameradagi eng yangi kadr tahlil qilinadi.
- **Poyezd istalgan vaqtda kelishi mumkin** — har bir poyezd alohida sessiya. Oxirgi vagondan 5 daqiqa o'tgach sessiya yopilib, hisobot yoziladi.
- **Servis to'xtatilsa yoki kompyuter o'chirilsa** — joriy poyezd hisoboti saqlanib, keyin to'xtaydi. Kompyuter qayta yoqilganda servis o'zi ishga tushadi.
- **Xotira o'smaydi** — eski treklar tozalanadi, uzoq ishlashda RAM oshmaydi.

## Video fayl bilan ishlatish

```bash
./run.sh IMG_2710.MOV                                   # oyna bilan, video o'z tezligida (real vaqt)
./run.sh IMG_2710.MOV --vaqt "2025-12-10 16:04:40"      # hisobotda videoning HAQIQIY vaqti bo'lsin
./run.sh IMG_2710.MOV --tez --oynasiz                   # oynasiz, imkon qadar tez (tekshirish uchun)
```
`--vaqt` -- video boshlangan paytdagi kamera ekranidagi soat. Berilmasa, vaqtlar dastur ishga
tushgan paytdan hisoblanadi. Jonli kamerada vaqt har doim real soatdan olinadi.

Bir necha videoni ketma-ket tahlil qilsangiz, ular bitta kunlik hisobotga 1-, 2-, 3-poyezd
bo'lib yoziladi va poyezdlar orasidagi oraliq hisoblanadi.

## Natijalar

Har bir kun -- alohida papka. Ichida har bir poyezd rasmlari o'z papkasida, ularning tagida
esa o'sha kunning **bitta** hisobot fayli (shu kuni kelgan hamma poyezdlar). Keyingi kun uchun
yangi papka va yangi hisobot ochiladi.

```
trains/
  2026.09.26/
      01-poyezd_07.00.00/
          001_67338913_07.00.05.jpg     vagon rasmi: raqam + tonna + hajm kesimlari
          002_96290671_07.00.15.jpg
      02-poyezd_08.00.00/
          ...
      2026.09.26_hisobot.txt            kunning barcha poyezdlari: jadval + har bir vagon
  2026.09.27/
      ...
```

Hisobot boshida kunlik jadval, keyin har bir poyezdning vagonlari:
```
KUNLIK HISOBOT -- 2026-09-26
Jami poyezdlar: 2    Jami vagonlar: 20    t/v o'qilgan: 20/20

 No | Kelgan              | Ketgan              | Turgan vaqti     | Vagon |     t/v | Oldingi poyezddan keyin | Rasmlar papkasi
  1 | 2026-09-26 07:00:00 | 2026-09-26 07:04:55 | 4 daq 55 s       |    16 |   16/16 | --                      | 01-poyezd_07.00.00/
  2 | 2026-09-26 08:00:00 | 2026-09-26 08:04:10 | 4 daq 10 s       |     4 |     4/4 | 55 daq 5 s              | 02-poyezd_08.00.00/
```
- **Kelgan** -- birinchi vagon raqami kamera oldida ko'ringan vaqt, **ketgan** -- oxirgisi ko'ringan vaqt.
- Poyezd kamera oldida to'xtab tursa (yuk tushirish), raqam ko'rinib turgani uchun u ikkiga bo'linmaydi.
- Kamera oldida **to'xtab turgan vagon** ham kutmasdan yoziladi: raqami aniq o'qilgach ~4 soniyada ekrandagi
  ro'yxatga tushadi (`EARLY_COMMIT_SECONDS`). Vagon keyin ketganda takror yozilmaydi.
- Tonna/hajm vagon yozilgandan keyin ham o'qilishda davom etadi va yozuvga qo'shiladi; plastinka kadrdan
  chiqqach qiymat **yakuniy ovoz** bo'yicha tekshiriladi -- tasdiqlanmagan oraliq qiymat olib tashlanadi (`--`).
- Kun papkasidagi yashirin `.poyezdlar.json` -- hisobotning xom ma'lumoti: dastur hisobotni shundan qayta
  yozadi va poyezd raqamlarini shu bo'yicha davom ettiradi (o'chirmang).
- Oxirgi vagon ko'rinmay qolgandan **5 daqiqa** o'tgach poyezd "ketdi" deb hisoblanib, hisobot yoziladi
  (`TRAIN_SESSION_GAP_SECONDS`). Kamera oldida qoldirib ketilgan vagon sessiyani 1 soatdan ortiq ushlab turmaydi.
- Poyezdlar kun bo'yicha raqamlanadi. Oraliq dastur qayta ishga tushsa ham, kun almashsa ham to'g'ri hisoblanadi.

Hisobot namunasi:
```
  1) 65394207   [VALID]   TONNA:       70 t   HAJM:      92 m3   16:05:47
  2) 67142265   [VALID]   TONNA:       69 t   HAJM:        -- m3  16:06:12
```
`--` — qiymat ishonchli o'qilmadi, shuning uchun tizim taxmin qilmadi. Sabablari: plastinka yo'q, kuchli xiralashgan yoki juda kichik.

Eski natijalarni avtomatik o'chirish uchun `logic_N_T_V.py` da `KEEP_DAYS = 90` qiling (shundan eski kun papkalari o'chadi). Standart qiymat `0` — hech narsa o'chirilmaydi.

## GPU tezligi (TensorRT)

Jetson'da (va TensorRT o'rnatilgan boshqa NVIDIA GPU'li kompyuterda) birinchi ishga tushishda 4 ta model
TensorRT FP16 ga o'tkaziladi va `engines/` papkasida saqlanadi (Jetsonda ~20 daqiqa, faqat bir marta).
Jetson Orin Nano da: PyTorch bilan ~5 kadr/s edi (real vaqtda kadrlarning ~75% i tashlanib, vagonlar
tushib qolardi), TensorRT bilan ~20 kadr/s. `.pt` fayl almashtirilsa, engine o'zi qayta yaratiladi.

`engines/` dagi fayllar aynan shu kompyuterning GPU'si va TensorRT versiyasiga bog'langan ("Boshqa
kompyuterga ko'chirish" bo'limiga qarang). Oddiy kompyuterda `install.sh` TensorRT o'rnatmaydi: u yerda
modellar PyTorch GPU rejimida ishlaydi.

## Uskuna talablari

| | Minimal | Tavsiya etiladi |
|---|---|---|
| GPU | NVIDIA, 4 GB VRAM (GTX 1660 / T4 darajasi) | NVIDIA RTX 3060 / 4060 yoki yuqori |
| CPU | 4 yadro | 8+ yadro |
| RAM | 8 GB | 16 GB |
| Disk | 20 GB bo'sh | SSD; kuniga ~50–100 MB natija (1000 vagon) |

- **GPU shart.** Bitta 4MP kamera (25 kadr/s) uchun dastur GPU'da ~0.5 GB xotira oladi.
- O'lchovlar (4MP, 25 kadr/s): **GPU (NVIDIA GB10) — 46 kadr/s**, ya'ni kerakligidan 1.85 barobar zaxira; **faqat CPU (20 yadro) — 2.3 kadr/s**, bu real vaqt uchun yetmaydi.
- GPU'ni boshqa og'ir dasturlar (masalan LLM serveri) bilan bo'lishsangiz, kadrlar tashlanishi mumkin. Buning uchun alohida GPU yoki bo'sh GPU tavsiya etiladi.

## Kamera sozlamalari (aniqlikka eng katta ta'sir)

- **Shutter/ekspozitsiya qisqa bo'lsin** (1/500–1/1000 s). Harakat xiraligi tonna/hajm xatolarining asosiy sababi.
- Kechasi yoritish yoki IR bo'lsin, 2–4 MP, 25 kadr/s, H.264/H.265.
- Kamera vagon yon tomoniga qaragan bo'lsin, raqam kadr markazidan o'tsin.

## Muammolarni hal qilish

| Belgisi | Yechim |
|---|---|
| `Manbaga ulanib bo'lmadi` | Kamera IP'sini `ping` qiling, RTSP manzil/login/parolni tekshiring (VLC'da ochib ko'ring) |
| `GPU: YOQ (CPU)` | `nvidia-smi` ishlashini tekshiring, NVIDIA drayverini o'rnating, `./install.sh` ni qayta ishga tushiring |
| Oyna ochilmaydi | Ekransiz serverda bu normal; `--oynasiz` bilan ishlating |
| `topilmadi: detection4.pt` | 4 ta `.pt` fayl `logic_N_T_V.py` bilan bir papkada bo'lishi kerak |
| `./run.sh` faqat yo'riqnoma chiqaradi | Manba ko'rsatilmagan: `./run.sh video.mp4` yoki `./run.sh 0` deb yozing |
| USB kamera ochilmaydi | `ls /dev/video*` bilan kamera ko'rinishini tekshiring; uni boshqa dastur band qilmagan bo'lsin; foydalanuvchi `video` guruhida bo'lsin (`sudo usermod -aG video $USER`, keyin tizimga qayta kiring) |
| Kamera oynasi yo'qolib qoldi | Boshqa oyna orqasida qolgan: `Alt+Tab` |
| `TensorRT ga o'tkazib bo'lmadi` yoki `TensorRT ishlamadi` | Xotira yetmagan: boshqa dasturlarni yopib, dasturni qayta ishga tushiring |





alohida video bilan run qilish 
cmd
run.bat IMG_2722.MOV --vaqt "2026-09-22 11:30:27"

