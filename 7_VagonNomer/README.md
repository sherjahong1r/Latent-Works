# Vagon Raqami Aniqlash Tizimi — README

Ushbu dastur video (yoki kamera oqimi)dagi tovar poyezdlarini kuzatib, har bir
vagonning 8 xonali UIC raqamini avtomatik o'qiydi, tekshiradi va natijalarni
matn hisobot + rasm shaklida saqlaydi.

## 1. Umumiy arxitektura

Ikkita YOLOv8 modeli ishlatiladi:

| Model | Fayl | Vazifasi |
|---|---|---|
| Raqam-hudud detektori | `detection4.pt` | Freymda "raqam plastinkasi" qayerdaligini topadi |
| Raqam klassifikatori | `classificationvagon.pt` | Shu hudud ichidagi har bir raqamni (0-9) alohida taniydi |

Kuzatuv (tracking) uchun **ByteTrack** ishlatiladi — har bir vagonga freymlar
oralig'ida doimiy ID beriladi, shu orqali bitta vagonning ko'plab freymlaridagi
o'qishlari birlashtirib tahlil qilinadi.

## 2. Ishlash jarayoni (pipeline), bosqichma-bosqich

1. **Video o'qish + kuzatuv** — har freymda `detector.track()` orqali barcha
   vagonlarga ID beriladi.
2. **Markaziy zona filtri** — faqat ekran markazidagi (~32% kenglik) vagonlar
   tahlil qilinadi, chunki u yerda burchak eng tekis, sifat eng yuqori.
3. **Asosiy trek filtri** — orqa fondagi ikkinchi (uzoqroq) poyezd yoki
   begona ob'ektlarni chetlab o'tish uchun, oxirgi 200 o'lchamning medianasidan
   sezilarli past balandlikdagi box'lar rad etiladi.
4. **Raqam hududi kropi** — vagon atrofida kichik bo'shliq (padding) bilan
   qirqib olinadi.
5. **Noto'g'ri hudud filtri** (`MIN_PLATE_ASPECT_RATIO`) — haqiqiy 8 xonali
   raqam har doim ancha cho'ziq (keng/past) shaklda bo'ladi. Agar
   detektor bergan hudud bu nisbatga mos kelmasa (masalan logotip yoki
   boshqa yozuv bo'lsa), freym butunlay klassifikatorga yuborilmaydi.
6. **Kichik kroplarni kattalashtirish** — balandligi 70px dan kam bo'lgan
   (uzoqdagi vagon) kroplar 2.2x kattalashtiriladi (bicubic).
7. **O'tkirlashtirish (sharpen)** — chekkalar aniqroq bo'lishi uchun.
8. **Raqam klassifikatsiyasi + filtrlar**:
   - begona (raqam bo'lmagan) belgi topilsa — butun o'qish bekor qilinadi;
   - balandligi boshqalardan farq qiluvchi (outlier) raqamlar chiqarib
     tashlanadi;
   - bir xil gorizontal qatorda bo'lmagan raqamlar olib tashlanadi;
   - bir nechta ajratilgan guruh topilsa, 8 taga eng yaqin va markazga
     eng yaqin guruh tanlanadi;
   - raqamlar orasidagi bo'shliqlar notekis bo'lsa, butun o'qish rad etiladi.
9. **Checksum (UIC nazorat raqami) tekshiruvi** — 8-chi raqam birinchi 7
   tadan rasmiy formula bo'yicha hisoblanadigan nazorat raqami bilan mos
   kelishi shart.
10. **Ko'p-freymli konsensus** — bitta freymga HECH QACHON ishonilmaydi:
    - **Pozitsiya-ovoz**: har bir pozitsiya (1-8) uchun barcha freymlar
      "ovoz beradi", eng ko'p ovoz olgan raqam tanlanadi;
    - **Repair-fallback**: bir xil 8 xonali raqam kamida
      `FAST_MIN_READ_FRAMES` marta mustaqil freymda takrorlanishi va
      checksumga mos kelishi shart.
11. **Fragmentatsiya filtri** — agar kuzatuv vaqtincha uzilib, bitta
    vagon yangi ID bilan qayta boshlansa (juda tez ketma-ketlik —
    fizik jihatdan mumkin emas), faqat eng kuchli tasdiqlangan holat
    qabul qilinadi.
12. **Pozitsiya-outlier filtri** — sessiya yakunida, vagon balandligiga
    nisbatan noodatiy joyda (masalan pastroqdagi logotip) o'qilgan
    yozuvlar hisobotdan chiqarib tashlanadi.
13. **Takror va lokomotiv filtri** — bir xil raqam 120 soniya ichida qayta
    yozilmaydi; har bir poyezd sessiyasining birinchi treki (odatda
    lokomotiv) hisobga olinmaydi.
14. **Rasm va hisobot saqlash** — quyida batafsil.

## 3. Nima uchun "taxmin qilish" mexanizmlari o'chirilgan

Dastlab, agar faqat 7 ta raqam ko'rinsa (bittasi kesilib qolgan bo'lsa) yoki
checksum mos kelmasa, dastur yetishmagan/shubhali raqamni **taxmin qilib**
to'ldirar edi. Ko'plab real testlardan so'ng bu YONDASHUV ISHONCHSIZ ekani
aniqlandi:

- **Oxirgi raqamni taxmin qilish** — checksum shu 7 ta raqamning FUNKSIYASI,
  shuning uchun bu "taxmin" hech qanday haqiqiy tekshiruv bermaydi va har
  doim "muvaffaqiyatli" chiqadi — hatto ko'ringan 7 ta raqamning ichida
  bittasi xato o'qilgan bo'lsa ham.
- **Birinchi raqamni taxmin qilish** — qaysi tomondan raqam yetishmayotganini
  aniqlaydigan geometrik hisob (`guess_missing_side`) ko'pincha NOTO'G'RI
  tomonni tanlardi, natijada butunlay boshqa (lekin checksumga mos) raqam
  chiqib qolardi.
- **Bitta past-ishonchli raqamni "tuzatish"** (8 ta bor, checksum mos
  emas) — agar allaqachon boshqa (yuqoriroq ishonchli) raqam ham xato
  bo'lsa, bu mexanizm faqat bitta joyni "tuzatib", ikkinchisini
  ko'rmay qoldirar, va checksumga mos — lekin haligacha noto'g'ri —
  natija chiqarardi.

**Natija:** real testlarda uchala mexanizmni o'chirish xatolarni bir
nechta videoda **nolga** tushirdi (avval ~10-20% xato darajasidan). Buning
evaziga ba'zi vagonlar endi "aniqlanmadi" toifasiga o'tadi — bu qasddan
qilingan tanlov, chunki **noto'g'ri yozilgan raqam yo'qolgan raqamdan
yomonroq**.

## 4. Sozlamalar (asosiylari)

| Sozlama | Joriy qiymat | Ma'nosi |
|---|---|---|
| `DIGIT_CONF` | 0.34 | Klassifikatorning bitta raqamni "ko'rdim" deb hisoblashi uchun minimal ishonch darajasi |
| `WAGON_DETECTOR_CONF` | 0.35 | Raqam-hudud detektorining minimal ishonch darajasi |
| `MIN_PLATE_ASPECT_RATIO` | 2.2 | Hudud "raqam plastinkasi"ga o'xshashi uchun minimal kenglik/balandlik nisbati |
| `ENABLE_MISSING_LAST_DIGIT_GUESS` | `False` | Oxirgi raqamni taxmin qilish (o'chirilgan) |
| `ENABLE_MISSING_FIRST_DIGIT_GUESS` | `False` | Birinchi raqamni taxmin qilish (o'chirilgan) |
| `ENABLE_SINGLE_DIGIT_FIX` | `False` | Past-ishonchli bitta raqamni "tuzatish" (o'chirilgan) |
| `FAST_MIN_READ_FRAMES` | 2 | Repair-fallback uchun bir xil raqam kamida shuncha marta takrorlanishi kerak |
| `POSITION_VOTE_MIN_FRAMES_STRONG` | 2 | Pozitsiya-ovoz uchun kamida shuncha freym kerak |
| `MIN_INTER_WAGON_SECONDS` | 2.0 | Ikki vagon orasidagi minimal vaqt (fragmentatsiya filtri) |
| `TRAIN_SESSION_GAP_SECONDS` | 300 | Shuncha soniya harakatsizlikdan keyin poyezd sessiyasi yakunlanadi |
| `DUPLICATE_NUMBER_COOLDOWN_SECONDS` | 120 | Bir xil raqam shuncha soniya ichida qayta yozilmaydi |
| `IGNORE_FIRST_N_TRACKS_PER_SESSION` | 1 | Sessiyaning birinchi N treki (lokomotiv) hisobga olinmaydi |

### Aniqlik ↔ aniqlash foizi (recall) muvozanati

Bu ikki maqsad bir-biriga zid: qanchalik qattiq filtrlasangiz (yuqori
`FAST_MIN_READ_FRAMES`, yuqori `DIGIT_CONF`), xato shunchalik kam, lekin
kamroq vagon "aniqlangan" deb hisoblanadi. Agar natijalarda:

- **xato ko'p bo'lsa** → `FAST_MIN_READ_FRAMES` / `POSITION_VOTE_MIN_FRAMES_STRONG`
  ni oshiring (masalan 2 → 3), yoki `DIGIT_CONF`ni oshiring;
- **ko'p vagon o'tkazib yuborilsa** → `DIGIT_CONF`ni pasaytiring, yoki
  `MIN_PLATE_ASPECT_RATIO`ni yumshating (agar haqiqiy plastinkalar rad
  etilayotgan bo'lsa).

## 5. Chiqish (output) tuzilishi

Video saqlash o'rniga (`SAVE_RESULT = False`), har bir poyezd uchun:

```
trains/
├── <sana>_barcha_natijalar.txt       ← barcha poyezdlar uchun matnli hisobot
└── images/
    └── <sana>_<N>-poyezd/
        ├── 001_<raqam>_<vaqt>.jpg
        ├── 002_<raqam>_<vaqt>.jpg
        └── ...
```

Har bir vagon rasmi **2 qatordan** iborat, bir xil o'lchamda:
- **1-qator** — model to'liq oxirgi natija sifatida aniqlagan raqam (aniq,
  katta matn sifatida chiziladi — checksum bilan tasdiqlangan).
- **2-qator** — vagondagi asl raqam hududining xom kamera surati
  (o'zgarishsiz) — solishtirish/tekshirish uchun.

Agar o'qish "repair-fallback" orqali (ya'ni pozitsiya-ovozsiz, faqat
takrorlanish orqali) qabul qilingan bo'lsa, raqam oxiriga `*` belgisi
qo'shiladi.

Matnli hisobotda har bir poyezd uchun: boshlanish/tugash vaqti, jami
vagonlar soni, va agar pozitsiya-outlier filtri biror yozuvni chiqarib
tashlagan bo'lsa — alohida ro'yxatda ko'rsatiladi.

## 6. Ekrandagi ko'rinish

- Har bir kuzatilayotgan vagon atrofida ramka va ID raqami.
- Vagonning raqami aniqlansa, ekranda ustiga yashil ramkali label chiqadi.
- O'ng tomonda so'nggi aniqlangan raqamlar ro'yxati ko'rsatiladi.
- "Wagons counted" yozuvi o'chirilgan (foydalanuvchi so'rovi bo'yicha).

## 7. Konsolga chiqadigan xabarlar

Konsolda faqat **muvaffaqiyatli** aniqlangan vagonlar (`[EVENT] ✅ VALID`),
poyezd sessiyasi boshlanishi/yakunlanishi, va filtr statistikasi (masalan
pozitsiya-outlier, fragmentatsiya) chiqadi. "Vagon aniqlanmadi" va
"lokomotiv o'tkazib yuborildi" kabi ogohlantirishlar konsolga
chiqarilmaydi (foydalanuvchi so'rovi bo'yicha) — lekin ularning mantiqi
(filtrlash) o'zgarishsiz ishlayveradi.

## 8. Bilingan cheklovlar / keyingi qadamlar

- Repair mexanizmlari o'chirilgani sabab, ba'zi vagonlar (kamera hech
  qachon 8 ta raqamni to'liq va aniq ko'rsata olmagan) endi umuman
  "aniqlanmadi" bo'lib qoladi. Bu, xato yozishdan ko'ra afzal deb
  tanlangan.
- Agar aniqlash foizi (recall) hali ham past bo'lsa, quyidagilar sinab
  ko'rilishi mumkin: kamera parametrlarini yaxshilash (shutter speed,
  yoritish), `classificationvagon.pt`ni xira/blur namunalar bilan qayta
  o'qitish, yoki krop sifatini oshiruvchi qo'shimcha old-processing.
- Har bir video/kamera sharoiti farq qilishi mumkin — shuning uchun
  yuqoridagi sozlamalarni **o'z videongizga qarab** moslashtirish tavsiya
  etiladi.
