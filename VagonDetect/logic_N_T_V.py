import cv2
import os
import sys
import numpy as np
import torch
import pathlib
import datetime
from ultralytics import YOLO
from collections import defaultdict, deque
import warnings
import time
import threading
import signal
import shutil
import traceback
import platform
import importlib.util
import json
import gc

# VIDEO_SOURCE = './IMG_2085.MP4'
VIDEO_SOURCE = './IMG_2719.MOV'

# ============ VIDEO O'RNIGA -- HAR BIR VAGON UCHUN RASM SAQLASH ============
# Ramkalar va yozuvlar chizilgan videoni ham saqlash.
# JONLI KAMERADA EHTIYOT BO'LING: dastur 24/7 ishlaydi va har qayta
# ulanishda yangi fayl ochiladi — disk to'lib qolishi mumkin.
# Shuning uchun standart holat o'chiq; video fayl sinovida buyruq
# satridan yoqing:  py logic_N_T_V.py video.MOV --video
SAVE_RESULT = False
OUTPUT_FILENAME = 'IMG_3031.MOV'
SAVE_RESIZE_WIDTH = None
SHOW_WINDOW = True
# Fayl videosi o'z tezligida (real vaqtda) o'tadi: 5 daqiqalik video roppa-rosa
# 5 daqiqada. Ishlov tez bo'lsa kutiladi, orqada qolsa eskirgan kadrlar tashlab
# yuboriladi -- jonli kameradagi kabi. False (yoki --tez) -- fayl imkon qadar tez ishlanadi.
# Jonli manbaga (kamera, RTSP) ta'sir qilmaydi: u o'zi real vaqtda keladi.
REALTIME_PLAYBACK = True

# ================== 24/7 ISHLASH (jonli kamera) ==================
# Kamera/RTSP uzilsa -- o'zi qayta ulanadi (1 s dan 30 s gacha oshib boruvchi kutish bilan).
LIVE_RECONNECT_MAX_WAIT = 30
# Kamera ulangan, lekin shuncha soniya yangi kadr bermasa -- oqim qotgan deb qayta ulanadi.
LIVE_STALL_SECONDS = 20
# FFMPEG ulanish/o'qish timeout'lari (ms) -- aks holda uzilgan RTSP da read() abadiy qotadi.
LIVE_OPEN_TIMEOUT_MS = 10000
LIVE_READ_TIMEOUT_MS = 10000
# Qayta ulanish urinishi shuncha soniya "jim" qolsa (ochish/o'qish timeout'i ishlamay qotib qolsa),
# u tashlab yuborilib, yangisi boshlanadi. Sog'lom urinish har 30-40 s da bir marta belgi beradi.
LIVE_CONNECT_HANG_SECONDS = 90
# Jurnalga har shuncha soniyada holat yoziladi (ishlayaptimi, fps, qayta ulanishlar).
HEARTBEAT_SECONDS = 600
# Kutilmagan xatodan keyin dastur shuncha soniyadan so'ng o'zi qayta ishga tushadi.
RESTART_DELAY_SECONDS = 5
# Natijalarni avtomatik tozalash: shuncha kundan eski rasm/hisobotlar o'chiriladi. 0 -- o'chirilmaydi.
KEEP_DAYS = 0

# ================== QURILMA (GPU / CPU) ==================
# "auto" -- NVIDIA GPU bo'lsa GPU, bo'lmasa CPU. Majburlash uchun: "cuda" yoki "cpu" (yoki --cpu).
DEVICE = "auto"
# GPU da modellar TensorRT FP16 ga o'tkaziladi (engines/ papkasi). Jetson Orin Nano da
# PyTorch bilan bir kadr ~180 ms edi (5 kadr/s) -- real vaqtda kadrlarning 80% i tashlanib,
# vagonlar tushib qolardi. TensorRT bilan -- ~3-4 barobar tez.
USE_TENSORRT = True
TRT_LOAD_ATTEMPTS = 5       # xotira vaqtincha yetmasa, TensorRT ni necha marta qayta yuklab ko'rish
ENGINE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "engines")
NUMBER_IMGSZ = 640          # vagon raqami detektori va raqam o'quvchi modelning kirish o'lchami
# CPU da video fayl: har bir kadr tahlil qilinadi (aniqlik GPU dagidek), real vaqt kutilmaydi --
# CPU ulgurmaydi va real vaqt rejimida kadrlarning ko'pi tashlanib, aniqlik tushardi.
CPU_PROCESS_EVERY_FRAME = True

SAVE_WAGON_IMAGES = True
COMBINED_IMAGE_MAX_WIDTH = 700
# =====================================================================

warnings.filterwarnings("ignore", category=FutureWarning)
temp = pathlib.PosixPath
if os.name != "nt":
    # Windows'da o'qitilgan .pt fayllar Linux'da ochilishi uchun. Windows'ning o'zida bu
    # almashtirish yo'l bilan ishlashni buzadi -- shuning uchun faqat Linux/macOS'da.
    pathlib.WindowsPath = pathlib.PosixPath

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VAGON_NUMBER_DETECTION = os.path.join(BASE_DIR, 'detection4.pt')
VAGON_NUMBER_CLASSIFICATION = os.path.join(BASE_DIR, 'classificationvagon.pt')

# =====================================================================
# ==================  t / v  (TONNA / M.KUB) BLOKI  ===================
# =====================================================================
# Raqam oqimi bilan BIR VAQTNING O'ZIDA ishlaydi, lekin undan MUTLAQO
# MUSTAQIL: raqam mantig'iga hech qanday ta'sir qilmaydi.
#
# MUHIM: bu blokda HECH QANDAY QIYMAT CHEGARASI YO'Q.
# Model nimani o'qisa -- o'sha ko'rsatiladi (75.0, 92, 24.5, 120 -- farqi yo'q).
TV_ENABLED = True
TV_DETECTION = os.path.join(BASE_DIR, 'detect-t-v-small.pt')
# 2026-10-02: classmodel.pt o'rniga yangi o'qitilgan model (arxitektura, 320 px, klasslar bir xil)
TV_CLASSIFICATION = os.path.join(BASE_DIR, 'cllas-t-vsmall.pt')

# O'nlik nuqta (belgi modelida vergul/nuqta klassi yo'q) -- tv_apply_decimal ga qarang.
# 3 xonali o'qish shu qiymatdan oshsa, o'nlik son deb talqin qilinadi.
# Chegaralar haqiqiy vagon xususiyatlaridan: eng katta yuk ko'tarish 125 t
# (8 o'qli polуvagon 12-508), eng katta kuzov hajmi ~250 m3 (krytyy vagon 11-1709),
# odatdagi hajmlar 73..158 m3.
TV_TONNAGE_MAX_WHOLE = 125     # t:  695 -> 69.5,  266 -> 26.6;  120 -> 120
TV_VOLUME_MAX_WHOLE = 265      # m3: 101, 120, 138, 158, 250 -- butun;  856 -> 85.6
# Arifmetika ikkiga bo'lina olmaydigan tor oraliq (t: 100..125, m3: 200..265) --
# faqat shu yerda vergul o'rni belgilar geometriyasidan aniqlanadi.
TV_AMBIGUOUS_MIN = {"t": 100, "v": 200}
# Fizik chegaralar: bulardan tashqaridagi qiymat vagonniki bo'lishi mumkin emas
# (eng kichik kuzov hajmi ~20 m3). Chala o'qilgan plastinkadan chiqadigan "5 m3", "6 t" kabi
# qiymatlarni to'sadi.
# Tonna pastki chegarasi 30 (20 edi): 20..30 t -- yuk ko'tarish emas, vagonning TARASI
# ("ТАРА 23 т", "ТАРА 24,50 т" har bir vagonda yozilgan va t detektori ba'zan uni ham topadi).
# vide_new_3.mp4 da 61082053 ning tarasi "23.0 t" bo'lib TONNA ga tushgan (2026-10-05).
# Yuk vagonlarining yuk ko'tarishi 60..125 t; yengilroq vagon kelsa -- shu sonni kamaytiring.
TV_VALUE_RANGE = {"t": (30.0, 125.0), "v": (20.0, 265.0)}
# Plastinkada doim "т" yoki "м³" belgisi bo'ladi. Uni ko'rmasdan qilingan o'qish
# qabul qilinmaydi: aks holda vagondagi oddiy yozuvlar ("25 12 35", "ДР 25 12 27")
# ham qiymat bo'lib ketadi -- qidiruv oynasi butun vagonni qamragani uchun bu muhim.
TV_REQUIRE_UNIT = True
# Vergul turgan joyda kengroq bo'shliq qoladi. 361 ta haqiqiy plastinkada o'lchangan:
# vergulli qiymatlarda bo'shliq raqam kengligining 0.50-0.57 qismi, butunlarda 0.05.
TV_DOT_GAP_MIN = 0.35
TV_DOT_GAP_MARGIN = 0.20       # boshqa bo'shliqlardan shuncha kengroq bo'lishi shart
TV_DOT_HEIGHT_MAX = 0.85       # yoki o'nlik qism shu nisbatdan past bo'lsa

TV_DET_CONF = 0.45          # blur/yarim ko'ringan plastinkalar garbage qiymat beradi
# Quyidagi to'rttasi 159 ta haqiqiy cropda to'liq qidiruv bilan tanlangan.
# imgsz=640 ni O'ZGARTIRMANG: model 320 da o'qitilgan, 640 da aniqlik
# 77% dan 20% ga tushadi.
TV_CLS_CONF = 0.25
# Belgi modeli bu ikki chegara ORASIDAGI ishonch bilan ko'rgan raqam -- "nimadir bor, lekin aniq emas".
# Ilgari bunday raqam jimgina tashlanib, qolgani to'liq o'qishdek ovoz berardi: "65,5т" ning birinchi
# "6" si 0.14-0.22 ishonch bilan ko'ringan kadrlarda o'qish "55" bo'lib, to'g'ri qiymatga QARSHI
# ovozga aylanardi (video_new_6.mp4, 96290671: "655" x24, "55" x12 -> 63% -> "--").
# Endi qiymat qatorida shunday raqam bo'lsa, o'sha kadrdagi o'qish umuman hisobga olinmaydi
# (tv_unsure_digit): chala o'qish hech qaysi qiymatga ovoz bermaydi. Raqamning o'rni (boshi,
# o'rtasi, oxiri) va qiymatning o'zi ahamiyatsiz.
TV_CLS_WEAK_CONF = 0.10
TV_CLS_IOU = 0.45
TV_CLS_AGNOSTIC = True
TV_DET_IMGSZ = 1024
TV_CLS_IMGSZ = 320
# t/v detektori (1024 px, har kadrda) eng og'ir qism: i5-1135G7 da PyTorch CPU 740 ms,
# OpenVINO + Intel iGPU 111 ms/kadr, natijasi bir xil. None -- oddiy PyTorch CPU.
TV_DET_OPENVINO_DEVICE = None   # avtomatik: setup_device() GPU yo'q Intel/AMD kompyuterda "intel:cpu" qiladi

# Tezlik: plastinka detektori (1024 px) + har bir plastinkani o'qish eng og'ir qism.
# Bir vagon kadrda 100+ marta o'qiladi, holbuki qiymat uchun o'nga yaqini yetarli.
TV_FRAME_STRIDE = 1         # har kadrda qidiriladi. 2 da 96291976 vagonining "81,64 m3"
                            # plastinkasi yo'qolardi: u butun videoda atigi 5 kadrda
                            # aniqlangan. Asosiy tejamkorlik TV_ENOUGH_READS da.
TV_READ_MIN_H = 11          # bundan past plastinka o'qilmaydi. 640x360 videolarda
                            # plastinkalar 10-14 px bo'ladi va ba'zilari o'qiladi;
                            # axlat o'qishlarni birlik va qiymat filtrlari to'sadi.
# Slotda shuncha tiniq o'qish bo'lsa, yangilari o'qilmaydi. 25 edi: ketma-ket kadrlarda xato
# takrorlanadi -- IMG_2091 da birinchi 25 ta o'qishning 17 tasi "69.3" chiqib, keyingi 280 ta
# to'g'ri "69.0" hisobga kirmay qolardi.
TV_ENOUGH_READS = 60
# "Yaxshi" o'qish -- plastinka shu slotda ko'rilgan eng katta balandligining shu ulushidan
# kichik bo'lmagan kadrdan. Plastinka keyinroq sezilarli kattalashsa (TV_REGROW_RATIO), hisob
# qaytadan boshlanadi. Aks holda teskari yo'nalishda 25 ta o'qish plastinka kadr chetidan
# kirib kelayotgan (xira, kichik) paytga to'g'ri kelib, "69" -> "65" bo'lib qolardi va
# plastinka aniq ko'ringan kadrlar umuman o'qilmasdi.
TV_GOOD_READ_RATIO = 0.0     # 0 -- hamma o'qish "yaxshi" (birinchi TV_ENOUGH_READS ta)
# Harakatdan xiralashgan plastinka ovoz bermaydi (tv_sharpness ga qarang): xira plastinkadan
# noto'g'ri qiymat ("69" -> "65", "92" -> "52") chiqqandan ko'ra "--" yaxshi. Xira o'qishlar
# faqat zaxira hisobiga kiradi (tv_slot_value). 2026-09-28 da 20 video, 23 000+ o'qishda
# kalibrlangan. Oldingi Laplasian o'lchovi qorong'i kadrdagi tiniq plastinkani ham tashlardi
# (IMG_2722 da 167 ta to'g'ri "69"), siqish shovqinini esa tiniqlik deb o'tkazardi (IMG_3033
# da "59.0"). Yangi o'lchovda qiyin videolarda chegaradan pastdagi o'qishlar 47-61%, yuqorisi
# 84-100% to'g'ri; oddiy videolarda o'qishlarning ~2% i tushadi.
TV_MIN_SHARPNESS = 0.2
TV_ALL_MIN_SHARE = 0.65     # tiniq o'qishlar g'olibi BARCHA o'qishlarning shu ulushidan kam bo'lmasin
TV_FALLBACK_MIN_READS = 20  # tiniq o'qish yetmasa: barcha o'qishlarda shuncha marta va
TV_FALLBACK_SHARE = 0.8     # shu ulush bilan o'qilgan qiymat olinadi. 0.9 edi: asosiy xavf "92" -> "52" edi,
                            # u endi TV_BLUR_LOOKALIKE_PREFIX bilan to'silgan; 0.9 da to'g'ri "76" (x54/63, x64/72)
                            # va "92" (x19/22) yo'qolardi (IMG_3033, IMG_2716, 2026-10-05 sinovi)
# G'olib barcha o'qishlarda shundan kam uchragan VA unga zid o'qishlar bo'lsa -- "--". vagon_new.mp4 da
# kadr chetidan kirayotgan xira "70т" 3-5 marta "76" (tiniqlik chegarasida) va 1-2 marta "70" o'qilib,
# 76 t yozilardi; to'g'ri qiymatlar esa jami o'qishlarda 20+ marta uchragan.
TV_CONFLICT_MIN_READS = 8
# Xira plastinkada belgi modeli 9 va 8 ni izchil 5 deb o'qiydi (raqamning tepasi "ochilib" qoladi):
# vagon_new.mp4 da 65480758 -- 52 x31/31 (haqiqiysi 92, IMG_2712), IMG_3033 da 65955171 -- 52 x53/63,
# IMG_2723 da 65452336 -- 52 x58 / 92 x8, IMG_2716 da 67649103 -- 55 x17 (haqiqiysi 85).
# Shuning uchun "5" bilan boshlanadigan hajm faqat yetarlicha TINIQ o'qish bilan olinadi.
TV_BLUR_LOOKALIKE_PREFIX = {"v": ("5",)}
TV_LOOKALIKE_MIN_SHARP = 5
# ---- 70 / 79 juftligi (faqat TONNA, faqat shu ikki qiymat) ----
# Belgi modeli harakatdan xiralashgan trafaret "0" ni "9" deb o'qiydi va bunga ISHONADI: IMG_2717 da
# 64473283 ning plastinkasi 137 o'qishdan 136 tasida "79" (belgi ishonchi 0.95), aslida 70 t. Ovoz berish
# buni ushlay olmaydi. Barcha sinovlarda "79" 78 vagondan 14 tasida ozchilik o'qish bo'lib uchragan va
# ularning hammasi 70 t vagonlar; teskari xato (69 -> 60) bir marta ham uchramagan.
# 79 t li vagon haqiqatan bor (19-9550 sement xopperi), lekin yarim vagonlarda (raqami 6 bilan
# boshlanadi; ular 69-77 t) yo'q. Shuning uchun:
#   * raqami TV_PAIR_NEVER_PREFIX bilan boshlanadigan vagonda "79" o'qishlari "70" deb hisoblanadi;
#   * boshqa vagonda "79" faqat deyarli bir ovozdan o'qilsa qabul qilinadi: "70" ham kamida
#     TV_PAIR_MIN_READS marta o'qilgan va "79" ning shu juftlikdagi ulushi TV_PAIR_STRICT_SHARE dan
#     past bo'lsa -- ikkalasi "70" deb hisoblanadi (70 ga pastroq talab, 79 ga yuqori).
TV_PAIRS = {"t": (("79", "70"),)}     # (shubhali o'qish, asl qiymat)
TV_PAIR_NEVER_PREFIX = ("6",)
TV_PAIR_STRICT_SHARE = 0.90
TV_PAIR_MIN_READS = 5
TV_REGROW_RATIO = 1e9       # o'chiq: sinovda xira plastinkada xato qiymatlarni ko'paytirdi
TV_FULL_BOX = False         # kadr chetida kesilgan raqam qutisini tiklash (sinovda foyda bermadi)
TV_MAX_READS = 75           # bitta slotdagi jami o'qishlarning qat'iy chegarasi (tezlik uchun)
# Zaxira yo'lning ikkinchi qoidasi -- faqat MAYDA plastinka uchun (o'qishlarining o'rtacha balandligi
# TV_BIG_PLATE_H dan past): barcha o'qishlarning TINIQROQ YARMI deyarli bir ovozdan bo'lsa, qiymat olinadi.
# Mayda plastinka TV_MIN_SHARPNESS ga yeta olmaydi (kattalashtirilganda baribir yumshoq chiqadi), shuning
# uchun u mutlaq chegara bilan emas, o'z o'qishlari orasidagi nisbiy tiniqlik bilan baholanadi.
# test_1.MP4 (640x352, plastinka ~35x12 px): 65891988 ning "92м³" plastinkasi birorta ham tiniq o'qish
# bermadi (tiniqligi eng ko'pi 0.15); real vaqtda 81 o'qishdan birinchi 30 tasi -- plastinka kadr
# chetidan kirayotgan, eng xira payt -- "92"/"32" aralash, qolgani toza "92": birinchi 75 tasi 76-79%
# (TV_FALLBACK_SHARE dan o'tmaydi), tiniqroq yarmi esa 38/40 = 95%.
# Katta plastinkaga QO'LLANMAYDI: u xira bo'lsa -- haqiqatan harakatdan xira, tiniqroq yarmi ham xato
# qiymatga 71-73% beradi (IMG_2724 da 67142216 "69.5", IMG_3033 da 65955171 "52").
# Eski qoida (birinchi TV_MAX_READS ta o'qish) O'ZGARMAGAN: qiymat ikkalasidan BIRI o'tsa olinadi;
# ikkalasi o'tib, qiymatlari har xil bo'lsa -- "--".
TV_SHARPEST_FALLBACK = True
# Birinchi TV_MAX_READS tadan keyin mayda plastinkaning xira kadri faqat shu paytgacha o'qilganlarning
# o'rtachasidan tiniqroq bo'lsa o'qiladi, va ko'pi bilan shuncha marta (tezlik uchun).
TV_SHARPEST_EXTRA_READS = 75
# Plastinka vagon raqamidan OLDIN kadrga kirsa (teskari yo'nalish), kadrda uning egasi hali
# yo'q. Bunday plastinkalar shuncha kadr saqlab turiladi; yangi vagon treki paydo bo'lganda
# uning qutisi tezlik bo'yicha plastinka ko'ringan paytga orqaga siljitilib biriktiriladi.
TV_PENDING_MAX_FRAMES = 0   # o'chiq (sinovda foyda bermadi); yoqish uchun ~120
TV_PENDING_READS_PER_FRAME = 4  # bir kadrda buferdan ko'pi bilan shuncha o'qish (real vaqt uchun)
# Vagon raqami kadrda topilmagan paytda ham plastinka o'z vagoniga biriktirilsin:
# trekning oxirgi qutisi o'lchangan tezlik bo'yicha shuncha kadrgacha oldinga siljitiladi.
# (Plastinka eng katta ko'ringan payt -- ko'pincha raqam kadrdan chiqib ketgan payt.)
TV_PREDICT_MAX_FRAMES = 120
# Vagon raqami kadrdan chiqib ketgach trek FRAMES_TO_FORGET dan keyin yopiladi va vagon
# hisobotga yoziladi. Plastinka esa ko'pincha shundan keyin kadrga kiradi (u raqamdan
# o'ngroqda). Shuning uchun yopilgan vagonga ham shuncha kadr davomida qiymat qo'shiladi.
TV_LATE_VALUE_FRAMES = 200
# Plastinka vagon raqamidan O'NGDA, shu balandlikda joylashadi. O'lchov:
# to'g'ri biriktirishlarda dx=+1.1..+2.2, dy<0.2; xatolarida dx manfiy, dy>0.65.
TV_ASSOC_MAX_DX = 3.0       # raqam qutisi kengligining ulushi -- o'ngga. 3.0 edi: teskari
                            # yo'nalishdagi videoda (IMG_2716) hajm plastinkasi 3.2 da turgan.
                            # Qo'shni vagonning plastinkasi ~8+ quti kengligi naridan boshlanadi.
TV_ASSOC_MIN_DX = -1.0      # chapga: plastinka raqamning ostida/tepasida ham bo'lishi mumkin
TV_ASSOC_MAX_DY = 3.00      # raqam qutisi balandligining ulushi -- butun vagon bo'ylab
                            # (plastinka vagonning tepasida yoki eng pastida ham
                            # bo'lishi mumkin; vertikal yo'nalishda raqib vagon yo'q)
# Zaxira oyna: oddiy oynada egasi topilmagan plastinka raqamdan CHAPDA ham bo'lishi mumkin --
# vagon_new.mp4 (tepadan yozilgan raqam) da 64226806 ning "70т 78м³" plastinkalari raqamdan
# 1.6..2.8 quti eni chapda, deyarli bir balandlikda (|dy| < 0.65). Eski videolardagi xato
# biriktirishlar dy > 0.65 bo'lgan -- shuning uchun zaxira oyna faqat bir balandlikdagilarga.
TV_ASSOC_LEFT_MIN_DX = -3.0
TV_ASSOC_LEFT_MAX_DY = 0.65
# Bitta tasodifiy o'qish qiymat bo'lib qolmasin: 2 687 kadrlik yozuvda bitta vagonda
# tonna 77 marta, hajm esa atigi 1 marta o'qilgan va o'sha yolg'on "68 m3" hisobotga tushgan.
TV_MIN_READS = 2
# Yakka o'qish ham shu balldan yuqori bo'lsa qabul qilinadi (ball = belgi ishonchi x
# plastinka ishonchi). Yozuvda haqiqiy o'qishlar 0.83-0.90 oralig'ida, yolg'on
# "68 m3" esa 0.76 bo'lgan -- shuning uchun chegara 0.82.
TV_SINGLE_READ_MIN_SCORE = 0.82
# G'olib qiymat AYNAN shu ko'rinishda kamida shuncha marta o'qilgan bo'lsin va o'z
# uzunligidagi o'qishlarning shu ulushini egallasin. Past sifatli (640x360) videoda
# mayda plastinka bir-ikki marta xato o'qilib, "70,0т" -> "100" yoki "20.0" bo'lib
# ketardi: bunday o'qishlar bir-biriga o'xshamaydi, shuning uchun ulushi past bo'ladi.
TV_MIN_SAME_READS = 2
TV_MIN_SHARE = 0.6          # 0.75 edi; kalibrlashda 0.6 bir xil 0 xato bilan ko'proq o'qidi
# G'olib satr o'qishlarining o'rtacha ishonchi (belgi modeli x plastinka detektori) shundan
# past bo'lsa -- qiymat xira kadrlardan yig'ilgan, ishonchsiz: chiqarilmaydi ("--").
TV_MIN_AVG_SCORE = 0.4
TV_BIG_PLATE_H = 25            # shundan baland plastinka aniq hisoblanadi (yakka o'qishga ruxsat)

# Birlik ("t"/"m3") qutisi ichidagi raqamni soxta deb tashlash (tv_suppress_inside_unit).
# Eski cllas-detect.pt "М" shtrixini "1" deb o'qigani uchun kerak edi. classmodel.pt da
# O'CHIQ: haqiqiy 419 kesimda u 30 ta to'g'ri o'qishni buzdi (856 -> 85, 92 -> 9,
# 731 -> 73) -- raqam aniqligi 95.5% dan 88.3% ga tushdi.
TV_SUPPRESS_INSIDE_UNIT = False
# Raqam qutisi shu ulushdan ko'prog'i bilan birlik ("t"/"m3") qutisi ichida
# yotsa -- u birlik glifidan chiqqan soxta raqam deb tashlanadi.
TV_UNIT_OVERLAP_DISCARD = 0.55
# Birlik qutisi tekshiruvdan oldin chapga shu ulushda kengaytiriladi: model
# kirill "М" ning chap shtrixini "1" deb o'qiydi, lekin "m3" qutisini shtrixdan
# KEYIN boshlaydi -- shuning uchun shtrix quti tashqarisida qolib ketadi.
TV_UNIT_LEFT_MARGIN_RATIO = 0.40
# Kesilgan o'qish ("52" o'rniga "5") o'rniga uzunrog'i olinishi uchun
# uzunroq variant shu ulushda ovoz to'plagan bo'lishi kerak.
TV_LONGER_PREFIX_MIN_SHARE = 0.50

TV_CROP_TARGET_HEIGHT = 96  # kichik croplar shu balandlikka cho'ziladi

# Plastinka qiymati -- birlik belgisining ("t", "m3") CHAP tomonidagi, bir-biriga
# yopishgan raqamlar guruhi. Kesimga tushib qolgan chetdagi begona raqamlar
# ("59 74 m3" -> 5974 -> 59.74) va birlikdan o'ngdagilar olinmaydi.
TV_GROUP_GAP_MAX = 1.2          # raqamlar orasidagi bo'shliq, raqam kengligi ulushida
TV_UNIT_GAP_MAX = 3.0           # oxirgi raqam bilan birlik orasidagi bo'shliq
TV_SUMMARY = False          # True: har vagon uchun t/v ovozlari jamlanmasi jurnalga yoziladi ([TV-OVOZ], [TV-YAKUN]) -- sozlash uchun
TV_DEBUG = False            # har bir o'qishni konsolga chiqarish (True = debug uchun)

# Belgi modelidagi nomlar -> ma'no
TV_DOT_NAMES = {"nuqta", "dot", "point", "."}
TV_UNIT_T_NAMES = {"t", "т", "tonna"}
TV_UNIT_M3_NAMES = {"m3", "м3", "m³", "v", "mkub"}
# =====================================================================

# ============ SOZLAMALAR ============
DIGIT_CONF = 0.38
# detection4.pt da bitta obyekt ikki nomda o'qitilgan ("number_zone" va "Wagon-number",
# qutilari deyarli bir xil). Klass bo'yicha NMS ikkalasini qoldiradi -- har plastinkaga
# ikki quti, ikki trek. Klassdan qat'i nazar NMS bitta quti qoldiradi.
WAGON_DETECTOR_AGNOSTIC_NMS = True
# Raqam modeli bitta belgiga ikki xil klass qutisini qo'yadi ("2" va "9") -- 9 xonali
# o'qish chiqadi. Klassdan qat'i nazar NMS + boshqa qutining ichida qolgan quti
# (masalan "7" ning vertikal chizig'i alohida "1" bo'lib) olib tashlanadi.
DIGIT_AGNOSTIC_NMS = True
DIGIT_CONTAIN_RATIO = 0.60      # kichik qutining shuncha qismi kattasining ichida -- takror
WAGON_DETECTOR_CONF = 0.35
ZONE_TOLERANCE = 0.32

CROP_PADDING_RATIO_V = 0.12
CROP_PADDING_RATIO_H = 0.05
CROP_PADDING_MIN = 8
CROP_PADDING_MAX = 40
HEIGHT_OUTLIER_RATIO = 0.55
DIGIT_GAP_RATIO = 1.9
REPAIRED_SCORE_MULTIPLIER = 0.5

MIN_FRAMES_TO_SURVIVE = 3
MIN_CONF_TO_FIX = 0.60
SHOW_LIVE_LABEL = True
FRAMES_TO_FORGET = 45
SHOW_WAGON_COUNTER = False
SHOW_RECOGNIZED_LIST = True
SHOW_CLOCK = True                   # pastki chap burchakda sana va soat (jonli kamerada -- real soat)
RECOGNIZED_LIST_ON_RIGHT = True     # ro'yxat kadrning o'ng tomonida
RECOGNIZED_LIST_MARGIN_RIGHT = 28   # o'ng chetdan bo'shliq
RECOGNIZED_LIST_DIM = 0.25          # yozuv ortidagi fon shu darajada qoraytiriladi
RECOGNIZED_LIST_FONT_SCALE = 0.62
RECOGNIZED_LIST_LINE_HEIGHT = 26
RECOGNIZED_LIST_MARGIN_LEFT = 14
RECOGNIZED_LIST_MARGIN_TOP = 25
RECOGNIZED_LIST_MARGIN_BOTTOM = 20
# Yozuv o'lchovlari 1280 px kenglikka nisbatan beriladi va kadr kengligiga
# mutanosib o'zgaradi (ui_scale_of). Shunda 640x360 va 2688x1520 videolarda ham
# oynada bir xil ko'rinadi: oyna kadrni 1280 px ga keltiradi.
DISPLAY_MIN_WIDTH = 1280
DEBUG_RAW_DETECTIONS = False

ADAPTIVE_HEIGHT_RATIO = 0.55
MIN_SAMPLES_FOR_ADAPTIVE = 15
HEIGHT_HISTORY_MAXLEN = 200
PRINT_BOX_HEIGHT_DEBUG = False

ROW_Y_TOLERANCE_RATIO = 0.6

DIGIT_CHARS = set("0123456789")
NON_DIGIT_DISCARD_THRESHOLD = 1

MISSING_SIDE_GAP_RATIO = 0.55
# 7 raqam o'qilib, ikki qo'shni raqam orasidagi qadam odatdagidan shuncha barobar katta bo'lsa --
# tushib qolgan raqam O'RTADA (bo'yoq bilan qisman o'chgan). Ilgari bunday o'qish "chapda yetishmaydi"
# deb to'ldirilardi: vagon_new.mp4 da 53187597 ning "5" i ko'rinmay, "5318797" -> 45318797 chiqardi
# (har qanday o'ringa qo'shilgan raqam nazorat sonidan o'tadi -- joyni faqat geometriya aniqlaydi).
MIDDLE_GAP_PITCH_RATIO = 1.75
MIDDLE_GAP_OTHERS_MAX = 1.6     # qolgan qadamlar bundan katta bo'lsa -- bo'shliq noaniq, tegilmaydi
MIDDLE_INSERT_CONF = 0.3        # qo'yilgan raqamning ovozdagi og'irligi (haqiqiy o'qishdan past)
# Trekda o'rtaga qo'yilgan o'qish bo'lsa, g'olib ular orasida ham ustun va kelishuv yuqori bo'lishi
# shart, aks holda vagon yozilmaydi: raqami bo'yalgan vagonda tartibsiz o'qishlar yig'ilib, nazorat
# sonidan tasodifan o'tgan 52398054 (kelishuv 85%) yozilardi; to'g'ri 53187597 da kelishuv 95%.
MIDDLE_VOTE_MIN_AGREEMENT = 0.88   # to'g'ri 53187597: 92-95%, bo'yalgan vagon: 85%
MIDDLE_VOTE_MIN_TOP_SHARE = 0.5

ENABLE_MISSING_LAST_DIGIT_GUESS = False

MIN_PLATE_ASPECT_RATIO = 2.2

FAST_INSTANT_ACCEPT_CONF = 0.62
FAST_MIN_READ_FRAMES = 3
# Trekda raqam shuncha kadrda 8 xonali o'qilib, pozitsiyalar bo'yicha kelishuv shundan
# yuqori bo'lsa -- raqam aniq: keyin faqat har DIGIT_SETTLED_EVERY kadrda qayta o'qiladi.
DIGIT_ENOUGH_READS = 40
DIGIT_SETTLED_AGREEMENT = 0.95
DIGIT_SETTLED_EVERY = 10
# To'xtab turgan vagon: raqam kadrdan chiqmaydi, trek yopilmaydi -- ilgari bunday vagon ro'yxatga
# va hisobotga faqat poyezd ketganda (videoda -- video tugaganda) tushardi (video_new_4.mp4:
# 67650655 70 soniya ko'rinib turgan, ekranda esa chiqmagan). Endi raqam aniq o'qilgan
# (yuqoridagi "settled" sharti) va trek shuncha soniya yashagan bo'lsa -- kutmasdan yoziladi.
# Trek keyin yopilganda vagon takror yozilmaydi (sessiya ro'yxati bo'yicha), t/v qiymatlari qo'shiladi.
EARLY_COMMIT_SECONDS = 4.0
# Real vaqtda (kamera, Jetson) tez o'tgan vagon faqat 1-2 kadrda to'g'ri o'qilishi mumkin.
# Ilgari bunday vagon butunlay tashlab yuborilardi. Endi checksumdan o'tgan va shu
# ishonchdan yuqori o'qilgan raqam 1-2 kadr bo'lsa ham qabul qilinadi (oxirgi topilgani).
FEW_READS_MIN_AVG_CONF = 0.70
# Pozitsiya ovozi yetakchisi checksumdan o'tmasa, zaxira nomzod trekdagi 8 xonali
# o'qishlarning kamida shuncha ulushini olgan bo'lishi shart. Aks holda plastinka
# izchil ravishda boshqa narsa deb o'qilgan -- masalan lokomotivdagi "ТЭМ2-059"
# (harflar raqam deb o'qiladi: 73112059), va 6% tasodifiy o'qish vagon bo'lib ketardi.
FALLBACK_MIN_SHARE = 0.30
# Zaxira (repair-fallback) g'olibi nazorat sonidan o'tgan BARCHA nomzod o'qishlarning shundan ko'prog'ini
# olishi shart. vagon_new.mp4 da birinchi raqami yarim ko'ringan 59726836 xira o'qilib, 8 ta bir-biriga zid
# nomzoddan 4 tasi bilan 89726830 yozildi.
FALLBACK_WINNER_MIN_SHARE = 0.5
# Pozitsiya ovozi yetakchisi nazorat sonidan o'tmadi (demak unda xato ANIQ bor), lekin o'qishlar izchil:
# 7 ta pozitsiya deyarli bir xil o'qilgan, faqat BITTASI ikki raqam orasida bo'lingan va ozchilikdagi raqam
# bilan nazorat soni to'g'ri chiqadi -- o'sha raqam olinadi (single_digit_candidate), FALLBACK_MIN_SHARE ga
# yetmasa ham. test_2.MP4: 61826483 -- qalin trafaret shriftdagi oxirgi "3" raqam kadrning o'ng yarmida (qiya
# ko'rinishda) 0.85-0.96 ishonch bilan "8" deb o'qiladi, to'g'ri o'qish faqat raqam kadr o'rtasidan o'tgach
# chiqadi (112 o'qishdan 19 tasi = 17%) -- vagon t/v si bilan birga butunlay tashlanardi.
ONE_DIGIT_STABLE_SHARE = 0.95   # qolgan 7 pozitsiyada yetakchi raqam ulushi; beqaror pozitsiyada -- ikki raqam birgalikda
ONE_DIGIT_MIN_SHARE = 0.10      # beqaror pozitsiyada to'g'rilovchi raqamning eng kam ulushi
ONE_DIGIT_MIN_READS = 5         # to'g'rilangan raqam shuncha kadrda to'liq (8 xona) o'qilgan bo'lishi shart
POSITION_VOTE_MIN_FRAMES_STRONG = 3

SPACING_UNIFORMITY_MAX_RATIO = 2.2
# Ba'zi vagonlarda (masalan yopiq vagonlar) raqam ikki guruhda yoziladi: "2358 8106".
# Bunday raqamda 4- va 5-raqam orasida bitta katta bo'shliq bo'ladi.
SPLIT_NUMBER_GROUPS = True
# 9 ta raqamdan qaysi biri ortiqcha -- bir nechta to'g'ri variant bo'lsa, eng tekis
# qadamli variant keyingisidan shuncha barobar tekis bo'lishi shart.
EXTRA_DIGIT_GEOMETRY_MARGIN = 1.25
# Och rangli vagonlarda (sisterna, kumush/sariq kuzov) raqam QORA bo'yoqda yoziladi, raqam
# modeli esa asosan to'q fondagi oq raqamlarda o'qitilgan. Oddiy o'qish 8 ta raqam
# bermasa, kesim invertlanib (oq<->qora) qayta o'qiladi. Normal plastinkada qo'shimcha
# xarajat yo'q -- faqat o'qish muvaffaqiyatsiz bo'lganda ishlaydi.
DIGIT_TRY_INVERTED = True
SPLIT_GROUP_HEIGHT_TOL = 0.25   # ikki guruh balandliklari shu ulushdan ko'p farq qilmasin

DIAGNOSTIC_LOG_ENABLED = False

# Sessiyaning birinchi N treki hisobga olinmaydi ("odatda lokomotiv").
# 1 dan 0 ga tushirildi: real sinovda bu filtr HAQIQIY vagonni yo'q qildi
# (IMG_2723 dagi 62624739). Sababi -- sessiya noto'g'ri joyda yopilib, keyingi
# vagon "yangi sessiyaning birinchi treki" bo'lib qolgan edi. Lokomotivdan
# himoya uchun checksum va ko'p-freymli ovoz berish allaqachon yetarli:
# lokomotiv korpusida 8 xonali UIC raqami yo'q. Zarur bo'lsa 1 ga qaytariladi.
IGNORE_FIRST_N_TRACKS_PER_SESSION = 0

KNOWN_FALSE_POSITIVE_NUMBERS = {
    # "XXXXXXXX",
}

ENABLE_POSITION_OUTLIER_FILTER = True
POSITION_OUTLIER_THRESHOLD = 0.18
MIN_WAGONS_FOR_POSITION_MEDIAN = 3

MIN_INTER_WAGON_SECONDS = 2.0
FRAGMENTATION_STRONG_VOTE_MIN = 3

TRAINS_OUTPUT_DIR = os.path.join(BASE_DIR, "trains")
TRAIN_SESSION_GAP_SECONDS = 300   # oxirgi vagon ko'rinmay qolgandan shuncha soniya o'tsa -- poyezd ketdi
# Video fayl yozib olingan real vaqt (kamera ekranidagi soatdan): "2025-12-10 16:05:00" yoki --vaqt.
# Berilmasa -- dastur ishga tushgan vaqtdan hisoblanadi. Jonli kamerada har doim real soat.
VIDEO_START_TIME = None
# Poyezd to'xtab turib, raqam ko'rinib tursa ham -- shuncha vaqt yangi vagon qo'shilmasa sessiya yopiladi
# (kamera oldida qoldirib ketilgan vagon keyingi poyezdni o'ziga qo'shib olmasin).
TRAIN_MAX_STOP_SECONDS = 3600
DUPLICATE_NUMBER_COOLDOWN_SECONDS = 120

CROP_MIN_HEIGHT_FOR_UPSCALE = 70
CROP_UPSCALE_FACTOR = 2.2


def sharpen_crop(image):
    blurred = cv2.GaussianBlur(image, (0, 0), sigmaX=3)
    sharpened = cv2.addWeighted(image, 1.8, blurred, -0.8, 0)
    return sharpened


def maybe_upscale_crop(crop):
    """Kichik (uzoqdagi vagon) croplarni klassifikatordan oldin kattalashtiradi."""
    h = crop.shape[0]
    if h > 0 and h < CROP_MIN_HEIGHT_FOR_UPSCALE:
        new_crop = cv2.resize(crop, None, fx=CROP_UPSCALE_FACTOR, fy=CROP_UPSCALE_FACTOR,
                               interpolation=cv2.INTER_CUBIC)
        return new_crop, CROP_UPSCALE_FACTOR
    return crop, 1.0


# =====================================================================
# ====================  t / v  YORDAMCHI FUNKSIYALARI  ================
# =====================================================================

def ui_scale_of(width):
    """Yozuv va chiziqlar o'lchovi uchun koeffitsient: 1280 px kenglik -- birlik."""
    return max(0.35, width / 1280.0)


def check_gui_support():
    """
    cv2.imshow ishlay oladimi -- oldindan tekshiradi.
    opencv-python-headless o'rnatilgan bo'lsa oyna umuman ochilmaydi,
    shuning uchun buni BOSHIDA aniqlab, foydalanuvchiga aytamiz.
    """
    if not SHOW_WINDOW:
        return False
    if os.name != "nt" and sys.platform != "darwin" and not (
            os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        # Ekransiz server/servis: Qt oynasi ochilmoqchi bo'lsa jarayonni butunlay o'ldiradi.
        print("ℹ️  Ekran (DISPLAY) yo'q -- oynasiz rejimda ishlaydi, natijalar saqlanaveradi.")
        return False
    try:
        info = cv2.getBuildInformation()
        has_gui = ("GUI: " in info and "NONE" not in info.split("GUI:")[1][:60])
        test = np.zeros((10, 10, 3), np.uint8)
        cv2.imshow("__gui_test__", test)
        cv2.waitKey(1)
        cv2.destroyWindow("__gui_test__")
        return True
    except Exception as e:
        print("\n" + "!" * 68)
        print("⚠️  REAL-TIME OYNA OCHILMAYDI -- cv2.imshow ishlamayapti.")
        print(f"   Sabab: {e}")
        print("   Eng ko'p uchraydigan sabab: 'opencv-python-headless' o'rnatilgan")
        print("   (u serverlar uchun, GUIsiz versiya). Tuzatish:")
        print("       pip uninstall opencv-python-headless opencv-python -y")
        print("       pip install opencv-python")
        print("   Vaqtinchalik yechim: yuqorida SAVE_RESULT = True qiling --")
        print("   natija video fayl sifatida saqlanadi.")
        print("!" * 68 + "\n")
        return False


def tv_upscale(crop):
    """t/v kropini aniq balandlikka cho'zadi (juda kichik bo'lgani uchun)."""
    h = crop.shape[0]
    if h <= 0:
        return crop, 1.0
    if h < TV_CROP_TARGET_HEIGHT:
        f = TV_CROP_TARGET_HEIGHT / h
        return cv2.resize(crop, None, fx=f, fy=f,
                          interpolation=cv2.INTER_CUBIC), f
    return crop, 1.0


def tv_suppress_inside_unit(items):
    """
    Birlik glifi ("t" / "m3") ichidan chiqqan soxta raqamlarni olib tashlaydi.

    Model "92 m3" plastinkasida muntazam ravishda kirill "М" ning chap vertikal
    shtrixini "1" deb o'qiydi (ishonchi 0.86 gacha chiqadi -- conf chegarasi
    yordam bermaydi) va qiymat 92 o'rniga 921 bo'lib ketadi.

    Birlik qutisi esa o'sha shtrixdan KEYIN boshlanadi, shuning uchun quti
    tekshiruvdan oldin chapga kengaytiriladi -- aks holda shtrix tashqarida
    qolib ketadi. Haqiqiy raqamlar birlikdan sezilarli bo'shliq bilan ajralgan,
    shuning uchun kengaytirilgan hudud ularga tegmaydi.
    """
    unit_boxes = [it for it in items
                  if it[4] in TV_UNIT_T_NAMES or it[4] in TV_UNIT_M3_NAMES]
    if not unit_boxes:
        return items

    zones = []
    for ux1, uy1, ux2, uy2, _, _ in unit_boxes:
        zones.append((ux1 - (ux2 - ux1) * TV_UNIT_LEFT_MARGIN_RATIO, uy1, ux2, uy2))

    kept = []
    for it in items:
        x1, y1, x2, y2, nm, _ = it
        if not (len(nm) == 1 and nm.isdigit()):
            kept.append(it)
            continue
        area = max(1.0, (x2 - x1) * (y2 - y1))
        swallowed = False
        for ux1, uy1, ux2, uy2 in zones:
            iw = min(x2, ux2) - max(x1, ux1)
            ih = min(y2, uy2) - max(y1, uy1)
            if iw > 0 and ih > 0 and (iw * ih) / area >= TV_UNIT_OVERLAP_DISCARD:
                swallowed = True
                break
        if not swallowed:
            kept.append(it)
    return kept


def tv_dot_position(digit_boxes):
    """Vergul nechta raqamdan keyin turganini belgilar geometriyasidan topadi.
    Belgi modelida vergul klassi yo'q, lekin vergul turgan joyda kengroq bo'shliq
    qoladi va o'nlik qism ko'pincha kichikroq yoziladi. Topilmasa -- None."""
    if len(digit_boxes) < 3:
        return None
    ws = sorted(b[2] - b[0] for b in digit_boxes)
    mw = ws[len(ws) // 2]
    if mw <= 0:
        return None
    gaps = [(digit_boxes[i + 1][0] - digit_boxes[i][2]) / mw
            for i in range(len(digit_boxes) - 1)]
    i = max(range(len(gaps)), key=lambda k: gaps[k])
    others = [g for k, g in enumerate(gaps) if k != i]
    wide = gaps[i] >= TV_DOT_GAP_MIN and (not others or gaps[i] - max(others) >= TV_DOT_GAP_MARGIN)
    hs = [b[3] - b[1] for b in digit_boxes]
    head, tail = hs[:i + 1], hs[i + 1:]
    head_h = sorted(head)[len(head) // 2]
    tail_h = sorted(tail)[len(tail) // 2]
    small = head_h > 0 and tail_h / head_h <= TV_DOT_HEIGHT_MAX
    return i + 1 if (wide or small) else None


def tv_value_group(items, prefer=None):
    """Birlik belgisidan chapga qarab, bir-biriga yopishgan raqamlar guruhini qaytaradi
    (birlik bilan birga). Birlik topilmasa -- o'zgarishsiz."""
    is_unit = lambda nm: nm in TV_UNIT_T_NAMES or nm in TV_UNIT_M3_NAMES
    is_digit = lambda nm: len(nm) == 1 and nm.isdigit()
    units = [i for i, it in enumerate(items) if is_unit(it[4])]
    if not units:
        return items
    digit_w = sorted(it[2] - it[0] for it in items if is_digit(it[4]))
    if not digit_w:
        return items
    mw = max(1.0, digit_w[len(digit_w) // 2])
    if prefer in ("t", "v"):
        # Tonna va hajm bitta qatorda yonma-yon yozilgan bo'lsa ("69т 74м³") ikkala
        # plastinka qutisi ham butun qatorni oladi -- detektor aytgan turdagi birlik olinadi.
        names = TV_UNIT_T_NAMES if prefer == "t" else TV_UNIT_M3_NAMES
        same = [u for u in units if items[u][4] in names]
        if same:
            units = same
    best = None
    for u in units:
        group, right_x1 = [], items[u][0]
        limit = TV_UNIT_GAP_MAX
        for it in reversed(items[:u]):
            if not (is_digit(it[4]) or it[4] in TV_DOT_NAMES):
                break
            if (right_x1 - it[2]) / mw > limit:
                break
            group.append(it)
            right_x1, limit = it[0], TV_GROUP_GAP_MAX
        if group and (best is None or len(group) > len(best[0])):
            best = (group, items[u])
    if best is None:
        return items
    return list(reversed(best[0])) + [best[1]]


def tv_unsure_digit(group, weak):
    """Qiymat qatorida (birinchi raqamdan bir o'rin chaproqdan birlikkacha) belgi modeli
    ISHONCHSIZ ko'rgan raqam bormi. `group` -- ishonchli raqamlar + birlik (chapdan o'ngga),
    `weak` -- ishonchi TV_CLS_WEAK_CONF..TV_CLS_CONF oralig'idagi raqam qutilari."""
    digits = [it for it in group if len(it[4]) == 1 and it[4].isdigit()]
    unit = next((it for it in group if it[4] in TV_UNIT_T_NAMES or it[4] in TV_UNIT_M3_NAMES), None)
    if not digits or unit is None:
        return False
    mh = sorted(d[3] - d[1] for d in digits)[len(digits) // 2]
    mw = max(1.0, sorted(d[2] - d[0] for d in digits)[len(digits) // 2])
    top, bottom = min(d[1] for d in digits), max(d[3] for d in digits)
    left = digits[0][0] - (TV_GROUP_GAP_MAX + 0.5) * mw
    for x1, y1, x2, y2, _, _ in weak:
        if y2 - y1 < 0.5 * mh or min(y2, bottom) - max(y1, top) < 0.5 * (y2 - y1):
            continue                             # mayda dog' yoki boshqa qatordagi yozuv
        if not (left < (x1 + x2) / 2.0 < unit[0]):
            continue                             # qiymatdan tashqarida
        covered = sum(max(0.0, min(x2, g[2]) - max(x1, g[0])) for g in group)
        if covered > 0.5 * (x2 - x1):
            continue                             # ishonchli o'qilgan belgining o'zi (ikkinchi nomzod)
        return True
    return False


def tv_read_chars(tv_classifier, crop, prefer=None):
    """
    t/v plastinkasi kropini o'qiydi -- HECH QANDAY QIYMAT CHEGARASI YO'Q.
    Model nimani ko'rsa, chapdan o'ngga tartiblab qaytaradi.

    Qaytaradi: (belgilar_ro'yxati, birlik, o'rtacha_ishonch, vergul_o'rni)
      (["7","5","0"], "t", 0.83, 2)    (["9","2"], "m3", 0.79, None)
    Hech narsa o'qilmasa: (None, None, 0.0, None)
    """
    if crop is None or crop.size == 0:
        return None, None, 0.0, None

    work, _ = tv_upscale(crop)
    try:
        res = tv_classifier.predict(work, conf=TV_CLS_WEAK_CONF, iou=TV_CLS_IOU,
                                    imgsz=TV_CLS_IMGSZ, agnostic_nms=TV_CLS_AGNOSTIC,
                                    verbose=False, device=dev())[0]
    except Exception:
        return None, None, 0.0, None

    if res.boxes is None or len(res.boxes) == 0:
        return None, None, 0.0, None

    names = tv_classifier.names
    items = []
    for (bx1, by1, bx2, by2), ci, cf in zip(res.boxes.xyxy.cpu().numpy(),
                                            res.boxes.cls.cpu().numpy().astype(int),
                                            res.boxes.conf.cpu().numpy()):
        nm = names[int(ci)] if isinstance(names, list) else names.get(int(ci), str(int(ci)))
        items.append((float(bx1), float(by1), float(bx2), float(by2),
                      str(nm).strip().lower(), float(cf)))

    weak = [it for it in items if it[5] < TV_CLS_CONF and len(it[4]) == 1 and it[4].isdigit()]
    items = [it for it in items if it[5] >= TV_CLS_CONF]
    if not items:
        return None, None, 0.0, None

    if TV_SUPPRESS_INSIDE_UNIT:
        items = tv_suppress_inside_unit(items)
    items.sort(key=lambda it: (it[0] + it[2]) / 2.0)
    items = tv_value_group(items, prefer)
    if weak and tv_unsure_digit(items, weak):
        return None, None, 0.0, None            # chala o'qish -- ovoz bermaydi
    dot_pos = tv_dot_position([it[:4] for it in items
                               if len(it[4]) == 1 and it[4].isdigit()])
    digits, unit, confs = [], None, []
    for _, _, _, _, nm, cf in items:
        if nm in TV_DOT_NAMES:
            digits.append(".")
            confs.append(cf)
        elif nm in TV_UNIT_T_NAMES:
            unit = "t"
            confs.append(cf)
        elif nm in TV_UNIT_M3_NAMES:
            unit = "m3"
            confs.append(cf)
        elif len(nm) == 1 and nm.isdigit():
            digits.append(nm)
            confs.append(cf)
        else:
            # noma'lum belgi -- shunchaki e'tiborsiz qoldiriladi,
            # butun o'qish BEKOR QILINMAYDI
            continue

    if not any(ch.isdigit() for ch in digits):
        return None, None, 0.0, None

    avg_conf = sum(confs) / len(confs) if confs else 0.0
    return digits, unit, avg_conf, dot_pos


def load_tv_detector():
    """t/v detektorini yuklaydi: iloji bo'lsa OpenVINO (Intel iGPU), bo'lmasa PyTorch.
    Qaytaradi: (model, predict uchun device yoki None)."""
    if TV_DET_OPENVINO_DEVICE:
        ov_dir = os.path.splitext(TV_DETECTION)[0] + "_openvino_model"
        try:
            if not os.path.isdir(ov_dir) or os.path.getmtime(TV_DETECTION) > os.path.getmtime(ov_dir):
                print("   OpenVINO formatiga o'tkazilmoqda (bir marta)...")
                YOLO(TV_DETECTION).export(format="openvino", imgsz=TV_DET_IMGSZ, verbose=False)
            model = YOLO(ov_dir, task="detect")
            model.predict(np.zeros((64, 64, 3), np.uint8), imgsz=TV_DET_IMGSZ,
                          device=TV_DET_OPENVINO_DEVICE, verbose=False)
            print(f"   t/v detektori OpenVINO ({TV_DET_OPENVINO_DEVICE}) da ishlaydi")
            return model, TV_DET_OPENVINO_DEVICE
        except Exception as e:
            print(f"   OpenVINO ishlamadi ({e}) -- PyTorch CPU ishlatiladi")
    return load_model(TV_DETECTION, TV_DET_IMGSZ), None


def load_model(pt_path, imgsz):
    """NVIDIA GPU (Jetson ham) da modelni TensorRT FP16 ko'rinishida yuklaydi -- 3-5 barobar tez.
    Engine birinchi ishga tushishda bir marta yaratiladi (Jetsonda har model ~5 daqiqa) va
    engines/ papkasida saqlanadi. Imkoni bo'lmasa -- oddiy PyTorch modeli."""
    name = os.path.splitext(os.path.basename(pt_path))[0]
    if DEVICE == "cuda" and USE_TENSORRT and importlib.util.find_spec("tensorrt") is not None:
        eng = os.path.join(ENGINE_DIR, f"{name}_{imgsz}_fp16.engine")
        try:
            if not os.path.exists(eng) or os.path.getmtime(pt_path) > os.path.getmtime(eng):
                print(f"   {name}: TensorRT FP16 ga o'tkazilmoqda (faqat bir marta, bir necha daqiqa)...",
                      flush=True)
                os.makedirs(ENGINE_DIR, exist_ok=True)
                made = YOLO(pt_path).export(format="engine", half=True, imgsz=imgsz, device=0,
                                            workspace=1, verbose=False)
                shutil.move(made, eng)
                onnx = os.path.splitext(pt_path)[0] + ".onnx"
                if os.path.exists(onnx):
                    os.remove(onnx)
        except Exception as e:
            print(f"   {name}: TensorRT ga o'tkazib bo'lmadi ({e}) -- PyTorch ishlatiladi")
            return YOLO(pt_path)
        # Jetsonda GPU va tizim bitta xotirani bo'lishadi: qurilma endi yoqilganda (servis
        # ishga tushayotganda) xotira vaqtincha yetmay qolishi mumkin. Darhol sekin PyTorch'ga
        # o'tib ketmaslik uchun xotirani bo'shatib, bir necha marta qayta urinamiz.
        for attempt in range(1, TRT_LOAD_ATTEMPTS + 1):
            try:
                model = YOLO(eng, task="detect")
                model.predict(np.zeros((imgsz, imgsz, 3), np.uint8), imgsz=imgsz, device=0, verbose=False)
                print(f"   {name}: TensorRT FP16 ({imgsz} px)")
                return model
            except Exception as e:
                model = None
                gc.collect()
                torch.cuda.empty_cache()
                if attempt == TRT_LOAD_ATTEMPTS:
                    print(f"   ⚠️  {name}: TensorRT ishlamadi ({e}) -- PyTorch ishlatiladi. "
                          f"Tezlik ancha past bo'ladi -- dasturni qayta ishga tushiring!")
                else:
                    wait = 5 * attempt
                    print(f"   {name}: TensorRT yuklanmadi ({e}) -- {wait} s dan keyin qayta urinish "
                          f"({attempt}/{TRT_LOAD_ATTEMPTS})", flush=True)
                    time.sleep(wait)
    return YOLO(pt_path)


def tv_detect_plates(tv_detector, frame, device=None):
    """Butun freymdan barcha t/v plastinkalarini topadi."""
    try:
        kw = {"device": device if device else dev()}
        res = tv_detector.predict(frame, conf=TV_DET_CONF, iou=0.5,
                                  imgsz=TV_DET_IMGSZ, verbose=False, **kw)[0]
    except Exception:
        return []

    if res.boxes is None or len(res.boxes) == 0:
        return []

    names = tv_detector.names
    out = []
    for (x1, y1, x2, y2), ci, cf in zip(res.boxes.xyxy.cpu().numpy(),
                                        res.boxes.cls.cpu().numpy().astype(int),
                                        res.boxes.conf.cpu().numpy()):
        nm = names[int(ci)] if isinstance(names, list) else names.get(int(ci), str(int(ci)))
        nm = str(nm).strip().lower()
        kind = "t" if nm in ("t", "т") else ("v" if nm in ("v", "м3", "m3") else None)
        if kind is None:
            continue
        out.append({
            "kind": kind,
            "x1": int(x1), "y1": int(y1), "x2": int(x2), "y2": int(y2),
            "cx": (x1 + x2) / 2.0, "cy": (y1 + y2) / 2.0,
            "conf": float(cf),
        })
    return out


def tv_assign_to_tracks(tv_plates, boxes, track_ids):
    """
    Har bir t/v plastinkasini O'Z vagonining trekiga biriktiradi.

    Oyna butun vagon bo'ylab: plastinka har doim raqamning yonida turmaydi --
    vagonning tepasida yoki eng pastida ham bo'lishi mumkin. Shuning uchun
    VERTIKAL oyna keng (kadrda bir vaqtda bitta vagon bo'lgani uchun tepada yoki
    pastda raqib vagon yo'q), GORIZONTAL oyna esa cheklangan: aks holda qo'shni
    vagonning plastinkasi yopishib, qiymatlar aralashib ketadi.

    O'lchov (7 525 kadrlik yozuv): haqiqiy plastinkalar raqamdan 0.9..2.5 quti
    kengligi o'ngda, 32% i esa raqam markazidan tepada turgan.
    """
    assigned = defaultdict(list)
    if not tv_plates or not boxes:
        return assigned

    centers = []
    for (bx1, by1, bx2, by2) in boxes:
        centers.append(((bx1 + bx2) / 2.0, (by1 + by2) / 2.0,
                        max(1.0, bx2 - bx1), max(1.0, by2 - by1)))

    for p in tv_plates:
        best_i, best_d = None, None
        for i, (cx, cy, w, h) in enumerate(centers):
            dx = (p["cx"] - cx) / w
            dy = abs(p["cy"] - cy) / h
            if not (TV_ASSOC_MIN_DX <= dx <= TV_ASSOC_MAX_DX) or dy > TV_ASSOC_MAX_DY:
                continue
            if best_d is None or abs(dx) < best_d:
                best_d, best_i = abs(dx), i
        if best_i is None:
            for i, (cx, cy, w, h) in enumerate(centers):
                dx = (p["cx"] - cx) / w
                dy = abs(p["cy"] - cy) / h
                if not (TV_ASSOC_LEFT_MIN_DX <= dx < TV_ASSOC_MIN_DX) or dy > TV_ASSOC_LEFT_MAX_DY:
                    continue
                if best_d is None or abs(dx) < best_d:
                    best_d, best_i = abs(dx), i
        if best_i is not None:
            assigned[track_ids[best_i]].append(p)
    return assigned


def draw_plate_label(frame, text, x1, y1, color, ui=2.1):
    """t/v qiymatini o'z plastinkasining ustiga yozadi (vagon raqami kabi).
    `ui` -- kadr kengligiga mutanosib koeffitsient (ui_scale_of)."""
    scale = 0.43 * ui
    thick = max(1, round(0.95 * ui))
    pad = max(2, int(3.3 * ui))
    (tw, th), base = cv2.getTextSize(text, cv2.FONT_HERSHEY_DUPLEX, scale, thick)
    ty = max(th + pad, y1 - 8)
    bx1, by1 = x1 - pad, ty - th - pad
    bx2, by2 = x1 + tw + pad, ty + base
    cv2.rectangle(frame, (bx1, by1), (bx2, by2), (0, 0, 0), -1)
    cv2.rectangle(frame, (bx1, by1), (bx2, by2), color, 2)
    cv2.putText(frame, text, (x1, ty), cv2.FONT_HERSHEY_DUPLEX,
                scale, color, thick, cv2.LINE_AA)


def tv_apply_decimal(value, kind, dot_pos=None):
    """
    Belgi modelida vergul klassi yo'q: plastinkadagi o'nlik qism oddiy raqamlar
    bo'lib o'qiladi ("69,5т" -> "695", "85,6м³" -> "856"). Qiymat ikki yo'l bilan
    tiklanadi.

    1) ARIFMETIKA -- haqiqiy vagon chegaralaridan. Eng katta yuk ko'tarish 125 t,
       eng katta kuzov hajmi ~250 m3; shundan oshgan o'qish vergulli bo'lishi shart.
       Belgilar datasetidagi 2 145 ta asl plastinkada o'nlik qism doim 2 xonali
       butun qismdan keyin kelgan.

           t:  69 -> 69     102 -> 102    695 -> 69.5   266 -> 26.6   2500 -> 25.00
           m3: 92 -> 92     138 -> 138    250 -> 250    856 -> 85.6   7238 -> 72.38

    2) GEOMETRIYA (`dot_pos`) -- faqat arifmetika ikkiga bo'lina olmaydigan tor
       oraliqda: t 100..125, m3 200..265. Masalan "250" o'qishi ham haqiqiy 250 m3,
       ham "25,0" bo'lishi mumkin -- bunda vergul o'rnidagi bo'shliq hal qiladi.
    """
    if not value.isdigit() or len(value) not in (3, 4) or value[0] == "0":
        return value
    max_whole = TV_TONNAGE_MAX_WHOLE if kind == "t" else TV_VOLUME_MAX_WHOLE
    head = int(value[:3])
    if head > max_whole:                        # arifmetika o'zi hal qiladi
        return value[:2] + "." + value[2:]
    if len(value) == 4:                         # 1385 -> 138.5,  2500 -> 250.0
        return value[:3] + "." + value[3]
    if dot_pos and 0 < dot_pos < len(value) and head >= TV_AMBIGUOUS_MIN.get(kind, 10 ** 9):
        return value[:dot_pos] + "." + value[dot_pos:]
    return value


def tv_plausible(value, kind):
    """Qiymat haqiqiy vagonnikiga o'xshaydimi (TV_VALUE_RANGE ga qarang)."""
    # Haqiqiy t/v hech qachon 0 bilan boshlanmaydi. vagon_new.mp4 da ta'mir sanasi trafaretlari
    # ("09 07", "09 10 27") yuzlab marta "090t" / "070t" o'qilgan -- 90 / 70 bo'lib o'tib ketardi.
    if isinstance(value, str) and value[:1] == "0":
        return False
    try:
        v = float(value)
    except (TypeError, ValueError):
        return False
    lo, hi = TV_VALUE_RANGE.get(kind, (0.0, float("inf")))
    return lo <= v <= hi


def make_tv_slot():
    """Bitta plastinka turi (t yoki v) uchun ovoz idishi."""
    return {"len": defaultdict(float), "cnt": defaultdict(int), "best": defaultdict(float),
            "dot": defaultdict(float), "pos": {}, "crop": None, "best_conf": 0.0,
            # aynan o'qilgan satrlar: ball, soni va plastinkaning eng katta balandligi
            "str": defaultdict(float), "strn": defaultdict(int), "strh": defaultdict(int),
            "maxh": 0, "good": 0, "total": 0,
            # xira kadrlarni ham qo'shgan BARCHA o'qishlar (tv_slot_value ga qarang)
            "raw": defaultdict(int), "rawn": 0, "raw_crop": {},
            # barcha qiymatli o'qishlar: (tiniqlik, qiymat, plastinka balandligi) -- TV_SHARPEST_FALLBACK
            "top": [], "top_crop": {}, "extra": 0}


def tv_sharpness(crop):
    """Plastinka kesimining tiniqligi: tik chiziqlar (x-gradient) energiyasi / kontrast^2,
    60 px balandlikda. Poyezd gorizontal harakatlanadi -- harakat xiraligi aynan raqamlarning
    tik chiziqlarini yoyadi. Kontrastga bo'lingani uchun qorong'i (kechki) kadrdagi tiniq
    plastinka ham xira hisoblanib qolmaydi (oddiy Laplasian shunday xato qilardi)."""
    g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    w = max(1, int(g.shape[1] * 60 / g.shape[0]))
    sx = cv2.Sobel(cv2.resize(g, (w, 60)), cv2.CV_64F, 1, 0)
    small = cv2.resize(g, (w, 60), interpolation=cv2.INTER_AREA)
    contrast = max(float(np.percentile(small, 95) - np.percentile(small, 5)), 10.0)
    return float(np.mean(sx * sx)) / (contrast * contrast)


def tv_slot_full(slot, h):
    """Bu balandlikdagi plastinka shu slot uchun endi o'qilmasinmi."""
    if slot["total"] >= TV_MAX_READS:
        return True
    if h > slot["maxh"] * TV_REGROW_RATIO:
        return False                        # plastinka sezilarli kattalashdi -- o'qiladi
    return slot["good"] >= TV_ENOUGH_READS


def tv_note_read(slot, h):
    """O'qishga urinish hisobi (natija ovozga kirdimi-yo'qmi, farqi yo'q)."""
    slot["total"] += 1
    if h > slot["maxh"] * TV_REGROW_RATIO:
        slot["good"] = 0                    # kichik kadrlardagi o'qishlar "yaxshi" hisobidan chiqadi
    slot["maxh"] = max(slot["maxh"], h)
    if h >= slot["maxh"] * TV_GOOD_READ_RATIO:
        slot["good"] += 1


def tv_add_vote(slot, chars, score, crop, dot_pos=None):
    """
    Butun satr o'rniga HAR BIR POZITSIYA alohida ovoz to'playdi
    (vagon raqamidagi POSITION-VOTE bilan bir xil mantiq).

    "65", "69", "66" kabi o'qishlar endi bir-birini kuchaytiradi:
    0-pozitsiya 6,6,6 -> "6", 1-pozitsiya 5,9,6 -> ko'pchilik yutadi.
    Uzunligi boshqacha (tushib qolgan raqamli) o'qishlar aralashib ketmaydi.
    """
    n = len(chars)
    if n == 0:
        return
    slot["len"][n] += score
    slot["cnt"][n] += 1
    slot["best"][n] = max(slot["best"][n], score)
    slot["dot"][(n, dot_pos)] += score
    text = "".join(chars)
    slot["str"][text] += score
    slot["strn"][text] += 1
    if crop is not None and crop.size:
        slot["strh"][text] = max(slot["strh"][text], crop.shape[0])
    pv = slot["pos"].setdefault(n, [defaultdict(float) for _ in range(n)])
    for i, ch in enumerate(chars):
        pv[i][ch] += score
    if crop is not None and crop.size > 0:
        # Hisobot rasmiga tushadigan krop faqat ishonch bo'yicha tanlansa, harakatdan
        # xiralashgan kadr tushib qolardi. Tiniqlik (Laplasian dispersiyasi) va
        # plastinkaning kattaligi ham hisobga olinadi.
        g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        quality = (score * min(1.0, cv2.Laplacian(g, cv2.CV_64F).var() / 150.0)
                   * min(1.0, crop.shape[0] / 40.0))
        if quality > slot["best_conf"]:
            slot["best_conf"] = quality
            slot["crop"] = crop.copy()


def tv_pick_winner(slot):
    """Eng ko'p ovoz olgan uzunlikni tanlab, o'sha uzunlikdagi o'qishlar
    bo'yicha har bir pozitsiyaning g'olib belgisini yig'adi."""
    if not slot or not slot["len"]:
        return None, None, None

    def voted(n):
        pv = slot["pos"].get(n)
        if not pv or any(not d for d in pv):
            return None
        return "".join(max(d.items(), key=lambda kv: kv[1])[0] for d in pv)

    # Kamida TV_MIN_READS marta o'qilgan, YOKI bir marta bo'lsa ham yuqori ballik
    # uzunliklar. Shunda tez o'tgan vagonning yagona, lekin ishonchli o'qishi yo'qolmaydi,
    # past ballik tasodifiy o'qish esa o'tmaydi.
    enough = {n: sc for n, sc in slot["len"].items()
              if slot["cnt"].get(n, 0) >= TV_MIN_READS
              or slot["best"].get(n, 0.0) >= TV_SINGLE_READ_MIN_SCORE}
    if not enough:
        return None, None, None
    best_n = max(enough.items(), key=lambda kv: kv[1])[0]
    val = voted(best_n)
    if val is None:
        return None, None, None

    # Uzoqdagi mayda plastinkada oxirgi raqam tez-tez tushib qoladi ("52" -> "5").
    # Qisqa o'qish uzunrog'ining aynan boshlanishi bo'lsa -- u kesilgan variant,
    # shuning uchun yetarlicha ovoz to'plagan uzunrog'i afzal ko'riladi.
    for n in sorted(enough, reverse=True):
        if n <= best_n:
            break
        longer = voted(n)
        if (longer and longer.startswith(val)
                and enough[n] >= enough[best_n] * TV_LONGER_PREFIX_MIN_SHARE):
            val = longer
            break

    # G'olib qiymat haqiqatan shunday o'qilganmi va o'z uzunligidagi o'qishlar
    # ichida ustunmi -- aks holda bu bir-biriga zid o'qishlardan yig'ilgan qiymat.
    same_len = {t: sc for t, sc in slot["str"].items() if len(t) == len(val)}
    if sum(same_len.values()) > 0 and same_len.get(val, 0.0) / sum(same_len.values()) < TV_MIN_SHARE:
        return None, None, None
    if slot["strn"].get(val, 0) and slot["str"].get(val, 0.0) / slot["strn"][val] < TV_MIN_AVG_SCORE:
        return None, None, None
    if slot["strn"].get(val, 0) < TV_MIN_SAME_READS:
        big_and_sure = (slot["strh"].get(val, 0) >= TV_BIG_PLATE_H
                        and slot["best"].get(len(val), 0.0) >= TV_SINGLE_READ_MIN_SCORE)
        if not big_and_sure:
            return None, None, None

    # vergul o'rni ham xuddi belgilar kabi ovoz bilan tanlanadi
    dots = {dp: sc for (n, dp), sc in slot["dot"].items() if n == len(val)}
    dot_pos = max(dots.items(), key=lambda kv: kv[1])[0] if dots else None
    if dot_pos is not None and dots[dot_pos] < 0.5 * sum(dots.values()):
        dot_pos = None
    return val, slot["crop"], dot_pos


def tv_note_raw(slot, chars, unit, dot_pos, kind, crop):
    """Tiniq-xiraligidan qat'i nazar, har bir o'qishni zaxira hisobiga yozadi."""
    if not chars or not unit:
        return
    val = tv_apply_decimal("".join(chars), kind, dot_pos)
    if not tv_plausible(val, kind):
        return
    slot["raw"][val] += 1
    old = slot["raw_crop"].get(val)
    if crop is not None and crop.size and (old is None or crop.shape[0] > old.shape[0]):
        slot["raw_crop"][val] = crop.copy()


def tv_note_top(slot, sharpness, chars, unit, dot_pos, kind, crop):
    """O'qishni tiniqligi bilan birga yozib qo'yadi (TV_SHARPEST_FALLBACK ga qarang)."""
    if not chars or not unit:
        return
    val = tv_apply_decimal("".join(chars), kind, dot_pos)
    if not tv_plausible(val, kind):
        return
    h = crop.shape[0] if crop is not None and crop.size else 0
    slot["top"].append((sharpness, val, h))
    old = slot["top_crop"].get(val)
    if h and (old is None or h > old.shape[0]):
        slot["top_crop"][val] = crop.copy()


def tv_top_small(slot):
    """Slotdagi plastinka maydami: o'qishlarining o'rtacha (median) balandligi TV_BIG_PLATE_H dan past."""
    hs = sorted(h for _, _, h in slot["top"])
    return bool(hs) and hs[len(hs) // 2] < TV_BIG_PLATE_H


def tv_top_counts(slot):
    """Barcha o'qishlarning tiniqroq yarmidagi qiymatlar: {qiymat: soni}."""
    reads = sorted(slot["top"], key=lambda r: -r[0])
    counts = defaultdict(int)
    for _, val, _ in reads[:len(reads) // 2]:
        counts[val] += 1
    return counts


def tv_fallback_pick(counts, lookalike):
    """Zaxira qoida: o'qishlar deyarli bir ovozdan bo'lsa -- (qiymat, soni), aks holda None."""
    n = sum(counts.values())
    if not n:
        return None
    top, c = max(counts.items(), key=lambda kv: kv[1])
    if (c >= TV_FALLBACK_MIN_READS and c / n >= TV_FALLBACK_SHARE
            and not (lookalike and top.startswith(lookalike))):
        return top, c
    return None


def tv_slot_remap(slot, sus, real):
    """`sus` deb o'qilgan hamma narsa `real` deb hisoblangan slot NUSXASI (asl slot o'zgarmaydi)."""
    s = dict(slot)
    for key in ("str", "strn", "raw"):
        d = slot[key].copy()
        if sus in d:
            d[real] += d.pop(sus)
        s[key] = d
    d = slot["strh"].copy()
    if sus in d:
        d[real] = max(d.get(real, 0), d.pop(sus))
    s["strh"] = d
    rc = dict(slot["raw_crop"])
    if sus in rc:
        rc.setdefault(real, rc.pop(sus))
    s["raw_crop"] = rc
    s["top"] = [(sh, real if v == sus else v, h) for sh, v, h in slot["top"]]
    tc = dict(slot["top_crop"])
    if sus in tc:
        tc.setdefault(real, tc.pop(sus))
    s["top_crop"] = tc
    # pozitsiya ovozlari: `sus` satrlarining hissasi farq qiladigan o'rinlarda `real` belgisiga ko'chadi
    n, moved = len(sus), slot["str"].get(sus, 0.0)
    pv = slot["pos"].get(n)
    if pv and moved and len(real) == n:
        pv2 = [d.copy() for d in pv]
        for i, (a, b) in enumerate(zip(sus, real)):
            if a != b:
                left = pv2[i].get(a, 0.0) - moved
                if left > 1e-9:
                    pv2[i][a] = left
                else:
                    pv2[i].pop(a, None)
                pv2[i][b] += moved
        pos = dict(slot["pos"])
        pos[n] = pv2
        s["pos"] = pos
    return s


def tv_pair_slot(slot, kind, number=None):
    """70/79 juftligi qoidasi (TV_PAIRS ga qarang). Kerak bo'lsa "shubhali" o'qishlar "asl" qiymatga
    qo'shilgan slot nusxasini, aks holda slotning o'zini qaytaradi."""
    for sus, real in TV_PAIRS.get(kind, ()):
        n_sus, n_real = slot["raw"].get(sus, 0), slot["raw"].get(real, 0)
        if not n_sus and not slot["strn"].get(sus, 0):
            continue
        never = bool(number) and str(number).startswith(TV_PAIR_NEVER_PREFIX)
        mixed = n_real >= TV_PAIR_MIN_READS and n_sus / (n_sus + n_real) < TV_PAIR_STRICT_SHARE
        if never or mixed:
            slot = tv_slot_remap(slot, sus, real)
    return slot


def tv_slot_value(slot, kind, number=None, sharpest=None):
    """Slotning yakuniy qiymati: (qiymat yoki None, tasdiqlagan o'qishlar soni, krop).
    `number` -- vagon raqami (ma'lum bo'lsa): 70/79 juftligi qoidasi uchun (tv_pair_slot).
    `sharpest` -- "eng tiniq" zaxira qoidasini majburan yoqish/o'chirish (None -- TV_SHARPEST_FALLBACK).
    20 ta videoning 23 000+ o'qishida kalibrlangan (to'g'ri qiymat bir necha videoda
    takrorlangan vagonlar va ko'z bilan tekshiruv bo'yicha):
      1) tiniq o'qishlar ovozi (tv_pick_winner);
      2) u qiymat BARCHA o'qishlar (xiralari ham) orasida ham ustun bo'lishi shart --
         tiniq deb o'tib qolgan ozchilik ko'pchilikka qarshi chiqa olmaydi
         (qorong'i plastinkada "76" x44 ga qarshi "70" x14 chiqib qolardi);
      3) tiniq o'qishdan natija chiqmasa -- barcha o'qishlar deyarli bir ovozdan bo'lsa
         (teskari yo'nalishdagi tez poyezdda "70" x80 va "78" x4) shu qiymat olinadi.
         Xira "92" 5 ga o'xshab, "52" x85 / "92" x14 bo'lib qoladi -- shuning uchun "5" bilan
         boshlanadigan hajm bu yo'l bilan olinmaydi (TV_BLUR_LOOKALIKE_PREFIX)."""
    if not slot:
        return None, 0, None
    slot = tv_pair_slot(slot, kind, number)
    raw_val, crop, dot = tv_pick_winner(slot)
    val, support = None, 0
    if raw_val:
        val = tv_apply_decimal(raw_val, kind, dot)
        support = slot["strn"].get(raw_val, 0)
        if not tv_plausible(val, kind):
            val = None
    raw = slot["raw"]
    n = sum(raw.values())
    lookalike = TV_BLUR_LOOKALIKE_PREFIX.get(kind, ())
    if val and lookalike and val.startswith(lookalike) and support < TV_LOOKALIKE_MIN_SHARP:
        val = None
    if val and n >= 5 and raw.get(val, 0) / n < TV_ALL_MIN_SHARE:
        val = None
    if val and raw.get(val, 0) < TV_CONFLICT_MIN_READS and n > raw.get(val, 0):
        val = None
    if not val and (n or slot["top"]):
        # ikki zaxira qoida: birinchi TV_MAX_READS ta o'qish YOKI (mayda plastinkada) o'qishlarning tiniqroq yarmi
        first = tv_fallback_pick(raw, lookalike)
        best = None
        if (TV_SHARPEST_FALLBACK if sharpest is None else sharpest) and tv_top_small(slot):
            best = tv_fallback_pick(tv_top_counts(slot), lookalike)
        if first and best and first[0] != best[0]:
            return None, 0, None                # ikki qoida ikki xil qiymat beradi -- ishonchsiz
        if first:
            return first[0], first[1], slot["raw_crop"].get(first[0])
        if best:
            best_crop = slot["top_crop"].get(best[0])
            return best[0], best[1], best_crop if best_crop is not None else slot["raw_crop"].get(best[0])
    return (val, support, crop) if val else (None, 0, None)
# =====================================================================


def draw_number_label(frame, label, x1, y1, color, ui):
    """Vagon raqamini uning qutisi ustiga yozadi."""
    font_scale = 0.62 * ui
    thickness = max(1, round(1.4 * ui))
    padding = max(3, int(5.7 * ui))
    (text_w, text_h), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_DUPLEX, font_scale, thickness)
    text_y = max(text_h + padding, y1 - 20)
    p1 = (x1 - padding, text_y - text_h - padding)
    p2 = (x1 + text_w + padding, text_y + baseline + padding // 2)
    cv2.rectangle(frame, p1, p2, (0, 0, 0), -1)
    cv2.rectangle(frame, p1, p2, color, max(1, round(ui)))
    cv2.putText(frame, label, (x1, text_y), cv2.FONT_HERSHEY_DUPLEX, font_scale, color, thickness, cv2.LINE_AA)


def combine_wagon_image(number_text, raw_view_crop,
                         max_width=COMBINED_IMAGE_MAX_WIDTH, min_width=400,
                         extra_rows=None):
    """
    Qatorlar, hammasi bir xil kenglikda:
        [ 50889386 ]        <- model aniqlagan RAQAM (matn)
        [ kamera kropi ]    <- vagondagi ASL raqam hududi
        [ TONNA: 75.0 t ]   <- ixtiyoriy
        [ t kropi ]
        [ HAJM: 92 m3 ]     <- ixtiyoriy
        [ v kropi ]

    extra_rows = None bo'lsa -- rasm AYNAN eski (2 qatorli) ko'rinishda.
    """
    def resize_to_width(img, target_w):
        h, w = img.shape[:2]
        if w <= 0 or h <= 0:
            return img
        scale = target_w / w
        new_h = max(1, int(round(h * scale)))
        interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
        return cv2.resize(img, (target_w, new_h), interpolation=interp)

    def text_band(text, target_w, band_h, font_scale_limit=0.90):
        band = np.full((band_h, target_w, 3), 255, dtype=np.uint8)
        if not text:
            return band
        (bw, bh), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_DUPLEX, 1.0, 2)
        scale_w = (target_w * font_scale_limit) / bw if bw > 0 else 1.0
        scale_h = (band_h * 0.65) / bh if bh > 0 else 1.0
        font_scale = max(0.4, min(scale_w, scale_h))
        thickness = max(2, int(round(font_scale * 1.8)))
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_DUPLEX, font_scale, thickness)
        tx = max(0, (target_w - tw) // 2)
        ty = (band_h + th) // 2
        cv2.putText(band, text, (tx, ty), cv2.FONT_HERSHEY_DUPLEX,
                    font_scale, (0, 0, 0), thickness, cv2.LINE_AA)
        return band

    raw_view_crop = raw_view_crop.copy()
    target_w = min(max_width, max(raw_view_crop.shape[1], min_width))
    bottom = resize_to_width(raw_view_crop, target_w)
    top_h = max(60, bottom.shape[0])

    top = text_band(number_text, target_w, top_h)
    divider = np.full((4, target_w, 3), 255, dtype=np.uint8)
    parts = [top, divider, bottom]

    if extra_rows:
        sep = np.full((3, target_w, 3), 150, dtype=np.uint8)
        for label_text, crop_img in extra_rows:
            if crop_img is None or crop_img.size == 0:
                continue
            row_img = resize_to_width(crop_img, target_w)
            band_h = max(44, min(80, row_img.shape[0]))
            parts.append(sep)
            parts.append(text_band(label_text, target_w, band_h, font_scale_limit=0.80))
            parts.append(np.full((3, target_w, 3), 255, dtype=np.uint8))
            parts.append(row_img)

    combined = np.vstack(parts)
    return cv2.copyMakeBorder(combined, 2, 2, 2, 2,
                              cv2.BORDER_CONSTANT, value=(120, 120, 120))


def filter_height_outliers(detections):
    if len(detections) < 3:
        return detections
    heights = sorted([d[3] for d in detections])
    n = len(heights)
    median_h = heights[n // 2] if n % 2 == 1 else (heights[n // 2 - 1] + heights[n // 2]) / 2
    filtered = []
    for d in detections:
        h = d[3]
        if median_h > 0 and abs(h - median_h) / median_h <= HEIGHT_OUTLIER_RATIO:
            filtered.append(d)
    return filtered


def filter_same_row(detections):
    if len(detections) < 3:
        return detections
    ys = sorted(d[4] for d in detections)
    n = len(ys)
    median_y = ys[n // 2] if n % 2 == 1 else (ys[n // 2 - 1] + ys[n // 2]) / 2
    avg_h = sum(d[3] for d in detections) / len(detections)
    tolerance = max(avg_h * ROW_Y_TOLERANCE_RATIO, 5)
    filtered = [d for d in detections if abs(d[4] - median_y) <= tolerance]
    if DEBUG_RAW_DETECTIONS and len(filtered) != len(detections):
        removed = len(detections) - len(filtered)
        print(f"[ROW-FILTER] {removed} ta boshqa qatordagi begona raqam chiqarib tashlandi")
    return filtered if filtered else detections


def cluster_digits_by_gap(detections, target_center_x, gap_ratio=DIGIT_GAP_RATIO):
    if len(detections) < 2:
        return detections
    dets = sorted(detections, key=lambda d: d[0])
    avg_h = sum(d[3] for d in dets) / len(dets)
    max_gap = max(avg_h * gap_ratio, 10)
    clusters = [[dets[0]]]
    for prev, curr in zip(dets, dets[1:]):
        gap = curr[0] - prev[0]
        if gap > max_gap:
            clusters.append([curr])
        else:
            clusters[-1].append(curr)
    if len(clusters) == 1:
        return clusters[0]

    def cluster_key(c):
        count_penalty = abs(8 - len(c))
        cx = sum(d[0] for d in c) / len(c)
        dist_penalty = abs(cx - target_center_x)
        return (count_penalty, dist_penalty)

    best_cluster = min(clusters, key=cluster_key)
    if SPLIT_NUMBER_GROUPS and len(best_cluster) != 8:
        # 8 xonali guruh yo'q -- yonma-yon ikki guruh birgalikda 8 ta bo'lsa va bir xil
        # balandlikda yozilgan bo'lsa, bu ikki guruhda yozilgan bitta raqam.
        def med_h(c):
            hs = sorted(d[3] for d in c)
            return hs[len(hs) // 2]
        pairs = [a + b for a, b in zip(clusters, clusters[1:])
                 if len(a) + len(b) == 8 and min(len(a), len(b)) >= 3
                 and abs(med_h(a) - med_h(b)) <= SPLIT_GROUP_HEIGHT_TOL * max(med_h(a), med_h(b))]
        if len(pairs) == 1:
            best_cluster = pairs[0]
    if DEBUG_RAW_DETECTIONS and len(clusters) > 1:
        dropped = sum(len(c) for c in clusters) - len(best_cluster)
        print(f"[CLUSTER] {len(clusters)} ta guruh topildi, {dropped} ta belgi begona guruh(lar)dan chiqarib tashlandi")
    return best_cluster


def check_spacing_uniform(detected_digits):
    if len(detected_digits) < 3:
        return True, 0.0
    xs = sorted(d[0] for d in detected_digits)
    gaps = [b - a for a, b in zip(xs, xs[1:]) if (b - a) > 0]
    if not gaps:
        return True, 0.0
    sorted_gaps = sorted(gaps)
    median_gap = sorted_gaps[len(sorted_gaps) // 2]
    if median_gap <= 0:
        return True, 0.0
    max_gap = max(gaps)
    ratio = max_gap / median_gap
    is_uniform = ratio <= SPACING_UNIFORMITY_MAX_RATIO
    if not is_uniform and SPLIT_NUMBER_GROUPS and len(detected_digits) == 8 and len(gaps) == 7:
        # "XXXX XXXX": yagona katta bo'shliq aynan 4- va 5-raqam orasida bo'lsa --
        # qolgan bo'shliqlar tekis bo'lishi sharti bilan -- bu ikki guruhli raqam.
        others = gaps[:3] + gaps[4:]
        om = sorted(others)[len(others) // 2]
        if om > 0 and max(others) / om <= SPACING_UNIFORMITY_MAX_RATIO and gaps[3] == max_gap:
            is_uniform, ratio = True, max(others) / om
    if DEBUG_RAW_DETECTIONS and not is_uniform:
        print(f"[SPACING-REJECT] Bo'shliqlar notekis (max/median={ratio:.2f} > {SPACING_UNIFORMITY_MAX_RATIO})")
    return is_uniform, ratio


def calculate_checksum(number_str_7):
    if len(number_str_7) != 7: return -1
    digits = [int(d) for d in number_str_7]
    weights = [2, 1, 2, 1, 2, 1, 2]
    total_sum = 0
    for d, w in zip(digits, weights):
        res = d * w
        total_sum += (res // 10) + (res % 10)
    next_ten = (total_sum + 9) // 10 * 10
    return next_ten - total_sum


def validate_wagon_number(number_str):
    if len(number_str) != 8 or not number_str.isdigit(): return False
    target = int(number_str[-1])
    calc = calculate_checksum(number_str[:7])
    return target == calc


def guess_missing_side(detected_digits, box_x1, box_x2):
    xs = [d[0] for d in detected_digits]
    avg_width = sum(d[3] for d in detected_digits) / len(detected_digits)
    if avg_width <= 0:
        return None
    leftmost_x = min(xs)
    rightmost_x = max(xs)
    left_gap = leftmost_x - box_x1
    right_gap = box_x2 - (rightmost_x + avg_width)
    left_is_empty = left_gap > (avg_width * MISSING_SIDE_GAP_RATIO)
    right_is_empty = right_gap > (avg_width * MISSING_SIDE_GAP_RATIO)
    if left_is_empty and not right_is_empty:
        return "left"
    if right_is_empty and not left_is_empty:
        return "right"
    return None


def middle_gap_index(detected_digits):
    """7 ta raqamda ichki bo'shliq bor bo'lsa -- tushib qolgan raqamning o'rni (1..6), aks holda None."""
    if len(detected_digits) != 7:
        return None
    xs = sorted(d[0] for d in detected_digits)
    pitch = [xs[i + 1] - xs[i] for i in range(6)]
    med = sorted(pitch)[3]
    if med <= 0:
        return None
    i = max(range(6), key=lambda k: pitch[k])
    others = [pitch[k] / med for k in range(6) if k != i]
    if pitch[i] / med >= MIDDLE_GAP_PITCH_RATIO and max(others) <= MIDDLE_GAP_OTHERS_MAX:
        return i + 1
    return None


def insert_missing_middle(detected_digits):
    """"5318797" + bo'shliq 7 va 9 orasida -> 53187597 (nazorat soni bo'yicha yagona raqam).
    Qaytaradi: 8 ta raqam ro'yxati (qo'yilgani past ishonch bilan) yoki None."""
    pos = middle_gap_index(detected_digits)
    if pos is None:
        return None
    srt = sorted(detected_digits, key=lambda d: d[0])
    s = "".join(d[1] for d in srt)
    found = [str(d) for d in range(10) if validate_wagon_number(s[:pos] + str(d) + s[pos:])]
    if len(found) != 1:
        return None
    x = (srt[pos - 1][0] + srt[pos][0]) // 2
    h = (srt[pos - 1][3] + srt[pos][3]) / 2.0
    return srt[:pos] + [(x, found[0], MIDDLE_INSERT_CONF, h)] + srt[pos:]


def repair_number(detected_digits, box_x1=None, box_x2=None):
    detected_digits.sort(key=lambda x: x[0])

    if len(detected_digits) == 7:
        if middle_gap_index(detected_digits) is not None:
            # raqam o'rtada tushib qolgan -- chetdan to'ldirish noto'g'ri bo'ladi
            return "".join(d[1] for d in detected_digits), False, "7 digits - o'rtada bo'shliq"
        side = guess_missing_side(detected_digits, box_x1, box_x2) if (box_x1 is not None and box_x2 is not None) else None

        if side == "right" and ENABLE_MISSING_LAST_DIGIT_GUESS:
            prefix_str = "".join([d[1] for d in detected_digits])
            guessed_last = calculate_checksum(prefix_str)
            if guessed_last != -1:
                candidate = prefix_str + str(guessed_last)
                return candidate, True, f"Completed missing LAST digit (geometriya): {guessed_last}"

        elif side == "left":
            rest_str = "".join([d[1] for d in detected_digits])
            known_last = rest_str[-1]
            middle6 = rest_str[:-1]
            candidates_found = []
            for d in range(10):
                trial_prefix7 = str(d) + middle6
                if str(calculate_checksum(trial_prefix7)) == known_last:
                    candidates_found.append(str(d) + rest_str)
            if len(candidates_found) == 1:
                return candidates_found[0], True, f"Completed missing FIRST digit (geometriya): {candidates_found[0][0]}"

        original_str = "".join([d[1] for d in detected_digits])
        return original_str, False, "7 digits - missing side noaniq"

    original_str = "".join([d[1] for d in detected_digits])
    if len(original_str) != 8: return original_str, False, "Len!=8"
    if validate_wagon_number(original_str): return original_str, False, "Valid"

    min_conf_val = 1.0
    min_conf_idx = -1
    for i in range(8):
        if detected_digits[i][2] < min_conf_val:
            min_conf_val = detected_digits[i][2]
            min_conf_idx = i

    if min_conf_val < MIN_CONF_TO_FIX and min_conf_idx != -1:
        candidates_found = []
        for d in range(10):
            temp = list(original_str)
            temp[min_conf_idx] = str(d)
            temp_str = "".join(temp)
            if validate_wagon_number(temp_str):
                candidates_found.append(temp_str)
        if len(candidates_found) == 1:
            fixed = candidates_found[0]
            return fixed, True, f"Fixed pos {min_conf_idx} (yagona yechim): {original_str[min_conf_idx]}->{fixed[min_conf_idx]}"

    return original_str, False, "No Fix"


def suppress_contained(predictions):
    """Boshqa (ishonchliroq) qutining ichida qolgan qutini olib tashlaydi: "7" ning
    vertikal chizig'i alohida "1" bo'lib topilishi kabi. Qo'shni haqiqiy raqamlar
    bunchalik ustma-ust tushmaydi."""
    kept = []
    for pr in sorted(predictions, key=lambda r: -r[4]):
        x1, y1, x2, y2 = pr[:4]
        area = max(1e-6, (x2 - x1) * (y2 - y1))
        inside = False
        for k in kept:
            iw = min(x2, k[2]) - max(x1, k[0])
            ih = min(y2, k[3]) - max(y1, k[1])
            if iw > 0 and ih > 0 and (iw * ih) / area >= DIGIT_CONTAIN_RATIO:
                inside = True
                break
        if not inside:
            kept.append(pr)
    return kept


def drop_extra_digit(dets):
    """9 ta raqam o'qilgan bo'lsa (chetdagi begona belgi yoki qo'shaloq quti),
    bittasini olib tashlab checksum bo'yicha tekshiradi. Faqat YAGONA to'g'ri raqam
    chiqsa qabul qilinadi: haqiqiy raqam har doim nomzodlar ichida bo'lgani uchun
    yagona yechim -- aynan u."""
    if len(dets) != 9:
        return dets
    dets = sorted(dets, key=lambda d: d[0])
    found = {}
    for i in range(9):
        rest = dets[:i] + dets[i + 1:]
        s = "".join(d[1] for d in rest)
        if validate_wagon_number(s):
            found.setdefault(s, rest)
    if len(found) == 1:
        return next(iter(found.values()))
    if len(found) > 1:
        # Bir nechta to'g'ri raqam chiqdi. Haqiqiy raqamlar bir tekis qadamda yozilgan,
        # chetdagi begona belgi esa qadamni buzadi -- qolgan 8 tasi eng tekis bo'lgan
        # variant boshqalardan aniq ustun bo'lsagina tanlanadi.
        def unevenness(rest):
            xs = [d[0] for d in rest]
            g = [b - a for a, b in zip(xs, xs[1:])]
            m = sorted(g)[len(g) // 2]
            if m <= 0 or min(g) <= 0:
                return float('inf')
            return max(max(g) / m, m / min(g))
        scored = sorted((unevenness(r), num) for num, r in found.items())
        if (scored[0][0] <= SPACING_UNIFORMITY_MAX_RATIO
                and scored[1][0] >= scored[0][0] * EXTRA_DIGIT_GEOMETRY_MARGIN):
            return found[scored[0][1]]
    return dets


def detect_digits_in_crop(classifier, crop_img, x_offset, y_offset, box_center_x, track_id=None, scale_factor=1.0):
    results_v8 = classifier.predict(crop_img, conf=DIGIT_CONF, iou=0.45,
                                    agnostic_nms=DIGIT_AGNOSTIC_NMS, verbose=False, device=dev())
    predictions = suppress_contained(results_v8[0].boxes.data.cpu().numpy())
    raw_detections = []

    for pred in predictions:
        dx1, dy1, dx2, dy2, d_conf, d_cls = pred
        dx1, dy1, dx2, dy2 = dx1 / scale_factor, dy1 / scale_factor, dx2 / scale_factor, dy2 / scale_factor
        class_id = int(d_cls)
        if hasattr(classifier, 'names'):
            names = classifier.names
            digit_str = names[class_id] if isinstance(names, list) else names.get(class_id, str(class_id))
        else:
            digit_str = str(class_id)
        digit_height = float(dy2 - dy1)
        digit_y_center = float(y_offset + (dy1 + dy2) / 2)
        raw_detections.append((int(x_offset + dx1), digit_str, float(d_conf), digit_height, digit_y_center))

    any_digit_seen = bool(raw_detections)

    non_digit = [d for d in raw_detections if d[1] not in DIGIT_CHARS]
    if len(non_digit) >= NON_DIGIT_DISCARD_THRESHOLD:
        if DEBUG_RAW_DETECTIONS:
            bad = ",".join(d[1] for d in non_digit)
            print(f"[LETTER-DISCARD] ID:{track_id} | {len(non_digit)} ta begona belgi ({bad})")
        raw_detections = []

    height_filtered = filter_height_outliers(raw_detections)
    row_filtered = filter_same_row(height_filtered)
    detected_full = cluster_digits_by_gap(row_filtered, box_center_x)
    detected_full = drop_extra_digit(detected_full)

    is_uniform, spacing_ratio = check_spacing_uniform(detected_full)
    if DIAGNOSTIC_LOG_ENABLED and len(detected_full) in (7, 8):
        confs = [d[2] for d in detected_full]
        avg_c = sum(confs) / len(confs)
        min_c = min(confs)
        raw_str = "".join(d[1] for d in sorted(detected_full, key=lambda x: x[0]))
        print(f"[DIAG] ID:{track_id} | str={raw_str} | n={len(detected_full)} | "
              f"spacing_ratio={spacing_ratio:.2f} | avg_conf={avg_c:.2f} | min_conf={min_c:.2f} | "
              f"uniform={'HA' if is_uniform else 'YOQ'}")

    if not is_uniform:
        return [], any_digit_seen, None

    avg_y_center = sum(d[4] for d in detected_full) / len(detected_full) if detected_full else None
    detected_digits = [(x, s, c, h) for (x, s, c, h, y) in detected_full]

    return detected_digits, any_digit_seen, avg_y_center


def make_position_votes():
    return [defaultdict(float) for _ in range(8)]


def add_position_votes(position_votes, detected_digits):
    if len(detected_digits) != 8:
        return False
    sorted_digits = sorted(detected_digits, key=lambda d: d[0])
    for i, (x, digit_str, conf, h) in enumerate(sorted_digits):
        position_votes[i][digit_str] += conf
    return True


def build_voted_number(position_votes):
    if any(len(pv) == 0 for pv in position_votes):
        return None, 0.0
    digits = []
    agreement_scores = []
    for pv in position_votes:
        total = sum(pv.values())
        best_digit, best_weight = max(pv.items(), key=lambda kv: kv[1])
        digits.append(best_digit)
        agreement_scores.append(best_weight / total if total > 0 else 0.0)
    avg_agreement = sum(agreement_scores) / len(agreement_scores)
    return "".join(digits), avg_agreement


def single_digit_candidate(position_votes, scores_dict, candidate_frames):
    """Pozitsiya ovozi yetakchisi nazorat sonidan o'tmaganda: yagona beqaror pozitsiyadagi ikkinchi raqam
    bilan nazorat soni to'g'ri chiqsa -- o'sha raqam (ONE_DIGIT_* shartlari), aks holda None."""
    if not position_votes or any(len(pv) == 0 for pv in position_votes):
        return None
    digits, split = [], None
    for i, pv in enumerate(position_votes):
        total = sum(pv.values())
        ranked = sorted(pv.items(), key=lambda kv: kv[1], reverse=True)
        digits.append(ranked[0][0])
        if ranked[0][1] >= ONE_DIGIT_STABLE_SHARE * total:
            continue
        if split is not None or len(ranked) < 2:
            return None                 # ikki pozitsiya beqaror -- o'qishlar tartibsiz
        if (ranked[0][1] + ranked[1][1] < ONE_DIGIT_STABLE_SHARE * total
                or ranked[1][1] < ONE_DIGIT_MIN_SHARE * total):
            return None
        split = (i, ranked[1][0])
    if split is None:
        return None
    digits[split[0]] = split[1]
    number = "".join(digits)
    n = candidate_frames.get(number, 0)
    if not validate_wagon_number(number) or n < ONE_DIGIT_MIN_READS:
        return None
    # har o'qish balli = o'rtacha ishonch x 3 (tuzatilgan o'qishda x 1.5) -- taxminiy tuzatishlar hisobga kirmaydi
    if (scores_dict or {}).get(number, 0.0) / n < 3.0 * FEW_READS_MIN_AVG_CONF:
        return None
    return number


# =====================================================================
# ====================  VAQT MANBAI (MEDIA SOATI)  ====================
# =====================================================================
# Vaqtga bog'liq BARCHA qarorlar shu soatdan o'qiydi: takror vagon to'sig'i,
# poyezd sessiyasining yakunlanishi, vagonlar orasidagi eng kichik oraliq.
#
# Nega kerak. Fayldan video o'qilganda ishlov real vaqtdan bir necha barobar
# sekin ketadi (bu mashinada ~5x). Real soatga bog'langan filtr videoda
# shuncha barobar kuchsizlanadi: 120 soniyalik takror to'sig'i videoda atigi
# ~24 soniyaga aylanadi va to'xtab turgan poyezdda bitta vagon ikki marta
# yozilib qoladi; 300 soniyalik sessiya oralig'i esa bitta poyezdni bir necha
# "poyezd"ga bo'lib yuboradi. Jonli kamerada real soat aynan to'g'ri o'lchov,
# shuning uchun u yerda hech narsa o'zgarmaydi.
class MediaClock:
    """Jonli manbada -- real soat; fayldan o'qilganda -- video vaqti."""

    def __init__(self):
        self.live = True
        self.fps = 25.0
        self.base = datetime.datetime.now()
        self.frame = 0

    def configure(self, live, fps):
        self.live = live
        self.fps = fps if (fps and fps > 0) else 25.0
        self.base = datetime.datetime.now()
        if not live and VIDEO_START_TIME:
            self.base = datetime.datetime.strptime(str(VIDEO_START_TIME).strip(), "%Y-%m-%d %H:%M:%S")
        self.frame = 0
        if live:
            print("   Vaqt manbai: real soat (jonli manba)")
        else:
            print("   Vaqt manbai: video vaqti (%.2f fps), boshlanishi %s%s" % (
                self.fps, self.base.strftime("%Y-%m-%d %H:%M:%S"),
                "" if VIDEO_START_TIME else "  (real yozilgan vaqt uchun: --vaqt \"YYYY-MM-DD HH:MM:SS\")"))

    def tick(self, frame_index):
        self.frame = frame_index

    def now(self):
        if self.live:
            return datetime.datetime.now()
        return self.base + datetime.timedelta(seconds=self.frame / self.fps)


clock = MediaClock()


def fmt_duration(sec):
    """3725 -> '1 soat 2 daq 5 s'"""
    sec = int(round(max(0, sec)))
    h, rem = divmod(sec, 3600)
    m, s_ = divmod(rem, 60)
    parts = ([f"{h} soat"] if h else []) + ([f"{m} daq"] if (m or h) else []) + [f"{s_} s"]
    return " ".join(parts)


# ====================  KUNLIK NATIJALAR  ====================
# Har bir kun -- bitta papka. Ichida har bir poyezdning rasmlari o'z papkasida,
# ularning tagida esa o'sha kunning BITTA hisobot fayli (hamma poyezdlar):
#   trains/2026.09.26/
#       01-poyezd_15.09.36/001_67338913_15.09.41.jpg ...
#       02-poyezd_18.40.02/...
#       2026.09.26_hisobot.txt       <- kunning barcha poyezdlari: jadval + vagonlar
# Hisobot har poyezd yopilganda .poyezdlar.json dan to'liq qayta yoziladi --
# fayl hech qachon yarim yozilgan holda qolmaydi, poyezd raqamlari ham adashmaydi.
TIME_FMT = "%Y-%m-%d %H:%M:%S"


def _day_dir(date_str):
    return os.path.join(TRAINS_OUTPUT_DIR, date_str)


def _day_report_path(date_str):
    return os.path.join(_day_dir(date_str), f"{date_str}_hisobot.txt")


def _day_data_path(date_str):
    return os.path.join(_day_dir(date_str), ".poyezdlar.json")


def load_day_trains(date_str):
    try:
        with open(_day_data_path(date_str), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _atomic_write(path, text):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def render_day_report(date_str, trains):
    """Kunlik hisobot matni: umumiy jadval, keyin har bir poyezdning vagonlari."""
    total_w = sum(len(t["wagons"]) for t in trains)
    total_tv = sum(t["tv_found"] for t in trains)
    day = datetime.datetime.strptime(date_str, "%Y.%m.%d")
    L = [f"KUNLIK HISOBOT -- {day:%Y-%m-%d}",
         f"Jami poyezdlar: {len(trains)}    Jami vagonlar: {total_w}    "
         f"t/v o'qilgan: {total_tv}/{total_w}", "",
         f"{'No':>3} | {'Kelgan':<19} | {'Ketgan':<19} | {'Turgan vaqti':<16} | "
         f"{'Vagon':>5} | {'t/v':>7} | {'Oldingi poyezddan keyin':<23} | Rasmlar papkasi",
         "-" * 128]
    for t in trains:
        n = len(t["wagons"])
        L.append(f"{t['n']:>3} | {t['start']} | {t['end']} | {t['duration']:<16} | {n:>5} | "
                 f"{str(t['tv_found']) + '/' + str(n):>7} | {t.get('gap') or '--':<23} | {t['folder']}/")
    for t in trains:
        L += ["", "=" * 78,
              f"{t['n']}-POYEZD   (rasmlar: {t['folder']}/)",
              f"Video manba            : {t.get('source', '')}",
              f"Poyezd kelgan vaqt     : {t['start']}",
              f"Poyezd ketgan vaqt     : {t['end']}",
              f"Turgan vaqti           : {t['duration']}",
              f"Oldingi poyezddan keyin: " + (f"{t['gap']} (oldingisi {t['prev_end']} da ketgan)"
                                              if t.get("gap") else "-- (birinchi qayd etilgan poyezd)"),
              f"Jami vagonlar          : {len(t['wagons'])}"]
        if TV_ENABLED:
            L.append(f"t/v o'qilgan vagonlar  : {t['tv_found']}/{len(t['wagons'])}")
        L.append("-" * 78)
        for i, w in enumerate(t["wagons"], 1):
            t_txt = f"{w['t']} t" if w.get("t") else "--"
            v_txt = f"{w['v']} m3" if w.get("v") else "--"
            if TV_ENABLED:
                L.append(f"{i:>3}) {w['number']}   TONNA: {t_txt:>10}   HAJM: {v_txt:>10}   {w['time']}")
            else:
                L.append(f"{i:>3}) {w['number']}   {w['time']}")
        if t.get("removed"):
            L.append("-" * 78)
            L.append("Chetga chiqarilgan (ehtimol begona yozuv, pozitsiya mos kelmadi):")
            for r in t["removed"]:
                L.append(f"     {r['number']}   pozitsiya={r['rel_y']:.2f} (median={r['median']:.2f})   {r['time']}")
    return "\n".join(L) + "\n"


def save_day_trains(date_str, trains):
    os.makedirs(_day_dir(date_str), exist_ok=True)
    _atomic_write(_day_data_path(date_str), json.dumps(trains, ensure_ascii=False, indent=1))
    _atomic_write(_day_report_path(date_str), render_day_report(date_str, trains))


def last_train_end_from_tables(now):
    """Dastur qayta ishga tushsa ham oraliq to'g'ri bo'lsin: bugungi/kechagi hisobotdan oxirgi ketish vaqti."""
    best = None
    for d in (now, now - datetime.timedelta(days=1)):
        for t in load_day_trains(d.strftime("%Y.%m.%d")):
            try:
                end = datetime.datetime.strptime(t["end"], TIME_FMT)
            except (KeyError, ValueError):
                continue
            if end <= now and (best is None or end > best):
                best = end
    return best


def source_label(src):
    s = mask_source(src)
    return os.path.basename(s) if isinstance(src, str) and os.path.isfile(src) else s


class TrainSessionManager:
    def __init__(self):
        self.session_start = None
        self.wagons = []
        self.last_number_time = {}
        self.last_event_time = None
        self.last_accept_time = None
        self.total_tv_found = 0
        self.first_activity = None      # poyezdning birinchi vagoni kamera oldida ko'ringan vaqt
        self.last_activity = None       # oxirgi marta vagon raqami ko'ringan vaqt
        self.prev_train_end = None      # oldingi poyezd ketgan vaqt (oraliqni hisoblash uchun)

    def activity(self, now):
        """Kadrda vagon raqami ko'rindi: poyezd shu yerda (to'xtab turgan bo'lsa ham)."""
        if self.first_activity is None:
            self.first_activity = now
        self.last_activity = now

    def add_wagon(self, number_str, rel_y=None, image=None, tv_info=None, already_written=False):
        # takror trek birlashtirilsa -- qaysi yozuvga borgani (kech qiymat uchun)
        self.last_merge_index = None
        if number_str in KNOWN_FALSE_POSITIVE_NUMBERS:
            print(f"       ↳ [BLOCKLIST-SKIP] {number_str} -- ma'lum lokomotiv/begona yozuv, hisoblanmadi")
            self.last_event_time = clock.now()
            return None

        now = clock.now()

        # Bitta poyezdda bir xil vagon raqami IKKI MARTA bo'lishi mumkin emas.
        # Ilgari bu vaqt bo'yicha tekshirilardi ("120 soniya ichida takrorlanmasin")
        # va to'xtab turgan poyezdda ishlamay qolardi: treker bitta vagonga bir
        # nechta ID ochadi (qutilarning IoU si ~0.98), uzun va qisqa treklar esa
        # to'siq muddatidan uzoqroq farq bilan yakunlanib, vagon ikki marta
        # yozilardi. Endi tekshiruv vaqtga emas, SESSIYA RO'YXATIGA tayanadi.
        existing_idx = None
        for i in range(len(self.wagons) - 1, -1, -1):
            if self.wagons[i][0] == number_str:
                existing_idx = i
                break

        if existing_idx is not None:
            # Raqam qisqa trekda tasdiqlanib, t/m3 qiymatlari uzunrog'ida to'planib
            # qolishi mumkin -- yetishmayotgan qiymatlar avvalgi yozuvga qo'shiladi.
            num, ts, ry, img, tv = self.wagons[existing_idx]
            merged = []
            new_tv = dict(tv)
            info = tv_info or {}
            if new_tv.get("_numcrop") is None and info.get("_numcrop") is not None:
                new_tv["_numcrop"] = info["_numcrop"]
            for k in ("t", "v"):
                v, sup = info.get(k), info.get("_n_" + k, 0)
                # yetishmasa -- qo'shiladi; bor bo'lsa -- faqat ko'proq o'qish bilan tasdiqlangan bo'lsa almashadi
                if v and (not new_tv.get(k) or (v != new_tv.get(k) and sup > new_tv.get("_n_" + k, 0))):
                    old = new_tv.get(k)
                    new_tv[k], new_tv["_n_" + k] = v, sup
                    new_tv["_src_" + k] = info.get("_src_" + k)
                    if info.get("_crop_" + k) is not None:
                        new_tv["_crop_" + k] = info["_crop_" + k]
                    merged.append(f"{'TONNA' if k == 't' else 'HAJM'} {v}" + (f" (oldin {old})" if old else ""))
            if merged:
                image = self._rebuild_image(num, image if image is not None else img, new_tv)
            self.last_merge_index = existing_idx
            if merged or (img is None and image is not None):
                self.wagons[existing_idx] = (num, ts, ry if ry is not None else rel_y,
                                             image if (merged and image is not None) else img,
                                             new_tv)
            if merged:
                print(f"       ↳ [BIRLASHTIRILDI] {number_str} -- takror trekdan olindi: "
                      f"{'  '.join(merged)}")
            elif already_written:
                print(f"       ↳ [KADRDAN CHIQDI] {number_str} -- {(now - ts).total_seconds():.0f}s oldin "
                      f"yozilgan (kutmasdan yozilgan vagon), endi ko'rinmay qoldi")
            else:
                print(f"       ↳ [SKIP] {number_str} -- shu poyezdda "
                      f"{(now - ts).total_seconds():.0f}s oldin yozilgan, takror hisoblanmadi")
            self.last_event_time = now
            if already_written:
                # MIN_INTER_WAGON_SECONDS tekshiruvi avvalgidek "oldingi vagon treki yopilgan"
                # vaqtdan sanalsin (erta yozilgan vaqtdan emas)
                self.last_accept_time = now
            return None

        # Sessiya chegarasidan o'tgan takror (masalan manyovr qilib qaytgan vagon):
        # bu yerda vaqt to'sig'i o'z kuchida qoladi, endi u media soati bo'yicha.
        last_time = self.last_number_time.get(number_str)
        if last_time is not None and (now - last_time).total_seconds() < DUPLICATE_NUMBER_COOLDOWN_SECONDS:
            print(f"       ↳ [SKIP] {number_str} -- oldingi sessiyada "
                  f"{(now - last_time).total_seconds():.0f}s oldin yozilgan, takror hisoblanmadi")
            self.last_event_time = now
            return None
        if self.session_start is None:
            self.session_start = now
            print(f"\n🚂 YANGI POYEZD SESSIYASI BOSHLANDI: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        self.wagons.append((number_str, now, rel_y, image, tv_info or {}))
        self.last_number_time[number_str] = now
        self.last_event_time = now
        self.last_accept_time = now
        return len(self.wagons) - 1          # keyin qiymat qo'shish uchun yozuv indeksi

    def _rebuild_image(self, num, image, tv):
        """Hisobot rasmini joriy t/v qiymatlari bilan qayta chizadi (qiymat yangilanganda)."""
        if not SAVE_WAGON_IMAGES or tv.get("_numcrop") is None:
            return image
        rows = [(f"{title}: {tv[k]} {unit}", tv["_crop_" + k])
                for k, title, unit in (("t", "TONNA", "t"), ("v", "HAJM", "m3"))
                if tv.get(k) and tv.get("_crop_" + k) is not None]
        if not rows:
            return image
        try:
            return combine_wagon_image(num, tv["_numcrop"], extra_rows=rows)
        except Exception:
            return image

    def settle_wagon_value(self, idx, kind, value, support=0, crop=None, src=None):
        """Trekning t/v o'qishi TUGAGANDA chaqiriladi: yozuvdagi qiymat shu trekning YAKUNIY
        ovoziga keltiriladi. Qiymat vagon yozilgandan keyin har o'qishda oraliq ovoz bo'yicha
        qo'shiladi (update_wagon_value); ilgari u keyingi o'qishlar bilan rad bo'lsa ham
        hisobotda qolardi: IMG_3033 da 65955171 "52 m3" x20 paytida yozilgan, yakunda esa
        52 x53 / 92 x6 / 32 x4 (ulush 84% < 90%) -- qiymat yo'q bo'lishi kerak edi."""
        if not (0 <= idx < len(self.wagons)):
            return
        num, ts, rel_y, image, tv = self.wagons[idx]
        if tv.get("_src_" + kind) != src or not tv.get(kind):
            if value:                        # boshqa trekdan kelgan qiymat -- odatdagi qoida bilan
                self.update_wagon_value(idx, kind, value, support, crop, src=src)
            return
        if value == tv.get(kind):
            return
        old = tv[kind]
        tv = dict(tv)
        what = "TONNA" if kind == "t" else "HAJM"
        if value:
            tv[kind], tv["_n_" + kind] = value, support
            if crop is not None:
                tv["_crop_" + kind] = crop
            print(f"       ↳ [YAKUNIY OVOZ] {num} -- {what} {value} (oraliq qiymat {old} edi)")
        else:
            for k in (kind, "_n_" + kind, "_crop_" + kind, "_src_" + kind):
                tv.pop(k, None)
            print(f"       ↳ [BEKOR QILINDI] {num} -- {what} {old}: yakuniy ovozda tasdiqlanmadi")
        if SAVE_WAGON_IMAGES and tv.get("_numcrop") is not None:
            rebuilt = self._rebuild_image(num, None, tv)
            if rebuilt is None:              # qiymat qolmadi -- faqat raqamli rasm
                try:
                    rebuilt = combine_wagon_image(num, tv["_numcrop"])
                except Exception:
                    rebuilt = image
            image = rebuilt
        self.wagons[idx] = (num, ts, rel_y, image, tv)

    def update_wagon_value(self, idx, kind, value, support=0, crop=None, src=None):
        """Vagon hisobotga yozilgandan KEYIN kelgan t/m3 qiymatini qo'shadi.
        Plastinka raqamdan o'ngroqda joylashgani uchun u ko'pincha vagon raqami
        kadrdan chiqib, trek yopilgandan keyin o'qiladi."""
        if not (0 <= idx < len(self.wagons)):
            return False
        num, ts, rel_y, image, tv = self.wagons[idx]
        old, old_sup = tv.get(kind), tv.get("_n_" + kind, 0)
        if old == value:
            if support > old_sup:
                tv = dict(tv)
                tv["_n_" + kind] = support
                self.wagons[idx] = (num, ts, rel_y, image, tv)
            return False
        if old and support <= old_sup:
            return False                     # mavjud qiymat kuchliroq tasdiqlangan
        tv = dict(tv)
        tv[kind], tv["_n_" + kind] = value, support
        tv["_src_" + kind] = src
        if crop is not None:
            tv["_crop_" + kind] = crop
        image = self._rebuild_image(num, image, tv)
        self.wagons[idx] = (num, ts, rel_y, image, tv)
        what = f"{'TONNA' if kind == 't' else 'HAJM'} {value}"
        if old:
            print(f"       ↳ [YANGILANDI] {num} -- {what} (oldin {old}; {support} ta o'qish bilan tasdiqlandi)")
        else:
            print(f"       ↳ [KEYIN QO'SHILDI] {num} -- {what}")
        return True

    def should_close(self):
        marks = [t for t in (self.last_event_time, self.last_activity) if t is not None]
        if not marks:
            return False
        elapsed = (clock.now() - max(marks)).total_seconds()
        if self.session_start is None:
            # vagon yozilmagan faollik (lokomotiv, begona yozuv) -- uzoq vaqt o'tsa unutiladi
            if elapsed > TRAIN_SESSION_GAP_SECONDS:
                self.first_activity = self.last_activity = None
            return False
        # Poyezd kamera oldida turgan bo'lsa (raqam ko'rinib tursa) sessiya yopilmaydi -- yuk
        # tushirish uchun uzoq turgan poyezd ikkita "poyezd" bo'lib qolmasin.
        if (self.last_event_time is not None and
                (clock.now() - self.last_event_time).total_seconds() > TRAIN_MAX_STOP_SECONDS):
            return True
        return elapsed > TRAIN_SESSION_GAP_SECONDS

    def close(self):
        if self.session_start is None or not self.wagons:
            self._reset()
            return
        fa = self.first_activity
        if fa is not None and (self.session_start - fa).total_seconds() > TRAIN_SESSION_GAP_SECONDS:
            fa = None                     # bu faollik oldingi (qoldirilgan) vagondan -- kelish vaqti emas
        start_dt = min(t for t in (self.session_start, fa) if t is not None)
        last_seen = self.last_activity
        cap = self.wagons[-1][1] + datetime.timedelta(seconds=TRAIN_MAX_STOP_SECONDS)
        if last_seen is not None and last_seen > cap:
            last_seen = cap
        end_dt = max(t for t in (self.wagons[-1][1], last_seen) if t is not None)
        if self.prev_train_end is None:
            self.prev_train_end = last_train_end_from_tables(start_dt)
        gap_txt = (fmt_duration((start_dt - self.prev_train_end).total_seconds())
                   if self.prev_train_end is not None and self.prev_train_end <= start_dt else None)

        final_wagons = list(self.wagons)
        removed_as_outlier = []

        if ENABLE_POSITION_OUTLIER_FILTER:
            wagons_with_pos = [w for w in self.wagons if w[2] is not None]
            if len(wagons_with_pos) >= MIN_WAGONS_FOR_POSITION_MEDIAN:
                rel_ys = sorted(w[2] for w in wagons_with_pos)
                n = len(rel_ys)
                median_rel_y = rel_ys[n // 2] if n % 2 == 1 else (rel_ys[n // 2 - 1] + rel_ys[n // 2]) / 2
                kept = []
                for w in self.wagons:
                    number_str, ts, rel_y, image, tv_info = w
                    if rel_y is not None and abs(rel_y - median_rel_y) > POSITION_OUTLIER_THRESHOLD:
                        removed_as_outlier.append((number_str, ts, rel_y, median_rel_y))
                    else:
                        kept.append(w)
                final_wagons = kept
                if removed_as_outlier:
                    print(f"\n📍 POZITSIYA-OUTLIER FILTRI: median joylashuv={median_rel_y:.2f} "
                          f"(0=tepa,1=tag), {len(removed_as_outlier)} ta yozuv chetga chiqarib tashlandi:")
                    for number_str, ts, rel_y, med in removed_as_outlier:
                        print(f"     ✗ {number_str} (pozitsiya={rel_y:.2f}, mediandan farq={abs(rel_y-med):.2f}) "
                              f"[{ts.strftime('%H:%M:%S')}]")

        date_str = start_dt.strftime('%Y.%m.%d')
        trains = load_day_trains(date_str)
        train_number = max([t.get("n", 0) for t in trains] + [0]) + 1
        folder = f"{train_number:02d}-poyezd_{start_dt:%H.%M.%S}"

        tv_found = sum(1 for w in final_wagons if w[4].get("t") or w[4].get("v"))
        self.total_tv_found += tv_found

        trains.append({
            "n": train_number, "folder": folder, "source": source_label(VIDEO_SOURCE),
            "start": start_dt.strftime(TIME_FMT), "end": end_dt.strftime(TIME_FMT),
            "duration": fmt_duration((end_dt - start_dt).total_seconds()),
            "gap": gap_txt, "prev_end": self.prev_train_end.strftime(TIME_FMT) if gap_txt else None,
            "tv_found": tv_found,
            "wagons": [{"number": number, "t": tv_info.get("t"), "v": tv_info.get("v"),
                        "time": ts.strftime('%H:%M:%S')}
                       for number, ts, rel_y, image, tv_info in final_wagons],
            "removed": [{"number": number, "rel_y": rel_y, "median": med, "time": ts.strftime('%H:%M:%S')}
                        for number, ts, rel_y, med in removed_as_outlier],
        })

        # Avval rasmlar, keyin hisobot: hisobotda ko'rsatilgan papka doim mavjud bo'lsin.
        if SAVE_WAGON_IMAGES and final_wagons:
            train_folder = os.path.join(_day_dir(date_str), folder)
            os.makedirs(train_folder, exist_ok=True)
            saved_count = 0
            for i, (number, ts, rel_y, image, tv_info) in enumerate(final_wagons, 1):
                if image is None or image.size == 0:
                    continue
                img_filename = f"{i:03d}_{number}_{ts.strftime('%H.%M.%S')}.jpg"
                cv2.imwrite(os.path.join(train_folder, img_filename), image)
                saved_count += 1
            print(f"🖼️  Vagon rasmlari saqlandi: {train_folder} ({saved_count}/{len(final_wagons)} ta)")

        save_day_trains(date_str, trains)
        print(f"\n🚂 {train_number}-POYEZD: kelgan {start_dt:%H:%M:%S}, ketgan {end_dt:%H:%M:%S}, "
              f"turgan vaqti {fmt_duration((end_dt - start_dt).total_seconds())}, {len(final_wagons)} vagon"
              + (f", oldingi poyezddan {gap_txt} keyin" if gap_txt else ""))
        self.prev_train_end = end_dt
        print(f"💾 Kunlik hisobot yangilandi: {_day_report_path(date_str)}")
        if TV_ENABLED:
            print(f"   t/v o'qilgan: {tv_found}/{len(final_wagons)}\n")

        self._reset()

    def _reset(self):
        cleanup_old_results()
        self.first_activity = None
        self.last_activity = None
        self.last_merge_index = None
        self.session_start = None
        self.wagons = []
        # last_number_time TOZALANMAYDI: sessiya chegarasidan sakrab o'tgan takrorni
        # to'sish uchun kerak. 24/7 ishlaganda cheksiz o'smasligi uchun to'siq
        # muddatidan eskirgan yozuvlar olib tashlanadi.
        if self.last_number_time:
            edge = clock.now() - datetime.timedelta(seconds=DUPLICATE_NUMBER_COOLDOWN_SECONDS)
            self.last_number_time = {k: v for k, v in self.last_number_time.items() if v > edge}
        self.last_event_time = None
        self.last_accept_time = None


train_session = TrainSessionManager()


def process_finished_track(track_id, scores_dict, candidate_frames, position_votes, position_vote_frames,
                            lifespan, stats, any_digit_seen, rel_positions, session_ordinal,
                            best_image=None, raw_number_crop=None, tv_votes=None, middle_reads=None,
                            already_written=False):
    def dropped(reason):
        # Raqam ko'rilgan, lekin vagon yozilmagan trek -- nima uchun, logda ko'rinsin.
        if position_vote_frames or scores_dict:
            best = max(scores_dict.items(), key=lambda kv: kv[1])[0] if scores_dict else "-"
            print(f"       ↳ [QABUL QILINMADI] ID:{track_id} | {reason} | 8 xonali o'qish x{position_vote_frames}, "
                  f"eng yaxshi nomzod {best} x{candidate_frames.get(best, 0)}")

    if lifespan < MIN_FRAMES_TO_SURVIVE:
        # Kadrlar ko'p tashlanganda (GPU band) vagon 1-2 kadrda ko'rinishi mumkin: ishonchli
        # o'qilgan, checksumdan o'tgan raqam bo'lsa -- quyidagi kam-kadr qoidasiga o'tadi.
        if not any(validate_wagon_number(num) and sc / max(1, candidate_frames.get(num, 0))
                   >= 3.0 * FEW_READS_MIN_AVG_CONF for num, sc in (scores_dict or {}).items()):
            dropped(f"trek juda qisqa ({lifespan} kadr)")
            return

    if session_ordinal is not None and session_ordinal < IGNORE_FIRST_N_TRACKS_PER_SESSION:
        # Ilgari bu yerda jimgina `return` bor edi va yo'qotilgan vagon
        # hech qayerda ko'rinmasdi. Endi har bir tashlab yuborish yoziladi.
        print(f"       ↳ [LOKOMOTIV-SKIP] ID:{track_id} -- sessiyaning "
              f"{session_ordinal + 1}-treki, hisobga olinmadi")
        return

    winner = None
    source_tag = ""

    if position_vote_frames >= POSITION_VOTE_MIN_FRAMES_STRONG:
        voted_number, avg_agreement = build_voted_number(position_votes)
        if voted_number and validate_wagon_number(voted_number):
            winner = voted_number
            source_tag = f" [POSITION-VOTE x{position_vote_frames}, kelishuv={avg_agreement:.0%}]"
            n_mid = sum(middle_reads.values()) if middle_reads else 0
            if n_mid:
                top, c = max(middle_reads.items(), key=lambda kv: kv[1])
                # Tiklangan o'qishlar g'olibga zid, lekin g'olibni to'liq (tiklanmagan) o'qishlar
                # ko'proq tasdiqlagan -- bo'shliq notekis bo'lib, tiklash ortiqcha raqam qo'shgan:
                # IMG_2715 da 63928014 (x21, kelishuv 89%) shu tufayli rad bo'lgan (63926414 x8/12).
                full_reads_win = candidate_frames.get(winner, 0) >= n_mid
                if (avg_agreement < MIDDLE_VOTE_MIN_AGREEMENT
                        or (top != winner and not full_reads_win)
                        or (top == winner and c < MIDDLE_VOTE_MIN_TOP_SHARE * n_mid)):
                    # raqam qisman o'chgan va o'qishlar tartibsiz -- zaxira nomzodlarga ham ishonib bo'lmaydi
                    dropped(f"raqam qisman o'chgan, o'qishlar izchil emas ({voted_number}, "
                            f"kelishuv {avg_agreement:.0%}, o'rtasi tiklangan {top} x{c}/{n_mid})")
                    return
                if top == winner:
                    source_tag += f" [o'rtasi tiklangan x{c}]"

    if winner is None:
        if not scores_dict:
            dropped("checksumdan o'tgan o'qish yo'q")
            return

        min_frames = max(FAST_MIN_READ_FRAMES, int(FALLBACK_MIN_SHARE * position_vote_frames))
        valid_repeated_candidates = {
            num: sc for num, sc in scores_dict.items()
            if validate_wagon_number(num) and candidate_frames.get(num, 0) >= min_frames
        }
        if not valid_repeated_candidates and position_vote_frames < POSITION_VOTE_MIN_FRAMES_STRONG * 2:
            # Kam kadrda ko'ringan vagon: har o'qish balli = o'rtacha ishonch x 3 (x1.5 tuzatilgan bo'lsa).
            valid_repeated_candidates = {
                num: sc for num, sc in scores_dict.items()
                if validate_wagon_number(num) and candidate_frames.get(num, 0) >= 1
                and sc / candidate_frames[num] >= 3.0 * FEW_READS_MIN_AVG_CONF
            }
        one_digit = None
        if not valid_repeated_candidates:
            one_digit = single_digit_candidate(position_votes, scores_dict, candidate_frames)
            if one_digit:
                valid_repeated_candidates = {one_digit: scores_dict[one_digit]}
        if not valid_repeated_candidates:
            dropped("nomzodlar yetarli tasdiqlanmadi")
            return

        sorted_candidates = sorted(valid_repeated_candidates.items(), key=lambda item: item[1], reverse=True)
        winner, _ = sorted_candidates[0]
        all_valid = sum(c for num, c in candidate_frames.items() if validate_wagon_number(num))
        if candidate_frames.get(winner, 0) <= FALLBACK_WINNER_MIN_SHARE * all_valid:
            dropped(f"nomzodlar bir-biriga zid ({winner} x{candidate_frames.get(winner, 0)}/{all_valid})")
            return
        source_tag = f" [repair-fallback x{candidate_frames[winner]}]"
        if one_digit:
            source_tag = (f" [bitta raqam nazorat soni bo'yicha x{candidate_frames[winner]}/{position_vote_frames}, "
                          f"ovoz yetakchisi {build_voted_number(position_votes)[0]}]")

    if winner is None:
        return

    if train_session.last_accept_time is not None:
        elapsed_since_last = (clock.now() - train_session.last_accept_time).total_seconds()
        if elapsed_since_last < MIN_INTER_WAGON_SECONDS:
            is_strong_position_vote = position_vote_frames >= FRAGMENTATION_STRONG_VOTE_MIN
            if not is_strong_position_vote:
                print(f"       ↳ [FRAGMENTATION-REJECT] ID:{track_id} | {winner} -- oldingi vagondan "
                      f"{elapsed_since_last:.1f}s dan keyin keldi (juda tez, ehtimol trek bo'linib ketgan "
                      f"bitta vagon) -- yetarli kuchli tasdiq yo'q, rad etildi")
                return

    median_rel_y = None
    if rel_positions:
        median_rel_y = sorted(rel_positions)[len(rel_positions) // 2]

    # ---- shu vagon uchun t/v yakuniy qiymatlari (chegarasiz) ----
    tv_info = {}
    extra_rows = []
    if TV_ENABLED and tv_votes:
        for kind, title, forced_unit in (("t", "TONNA", "t"), ("v", "HAJM", "m3")):
            val, support, crop = tv_slot_value(tv_votes.get(kind), kind, winner)
            _sl = tv_votes.get(kind)
            if TV_SUMMARY and _sl and (_sl["raw"] or _sl["strn"]):
                print(f"       [TV-OVOZ] {winner} {kind}: tanlandi={val} | tiniq={dict(_sl['strn'])} | "
                      f"barcha={dict(_sl['raw'])} | bal={ {k: round(v, 1) for k, v in _sl['str'].items()} } | "
                      f"baland={dict(_sl['strh'])}")
            if val:
                tv_info[kind] = val
                tv_info["_n_" + kind] = support      # qiymatni tasdiqlagan o'qishlar soni
                tv_info["_src_" + kind] = track_id   # qiymat qaysi trekdan kelgani (tv_settle uchun)
                tv_info["_crop_" + kind] = crop
                extra_rows.append((f"{title}: {val} {forced_unit}", crop))
    if raw_number_crop is not None and raw_number_crop.size > 0:
        tv_info["_numcrop"] = raw_number_crop

    final_image = best_image
    if SAVE_WAGON_IMAGES and extra_rows and raw_number_crop is not None and raw_number_crop.size > 0:
        try:
            final_image = combine_wagon_image(winner, raw_number_crop, extra_rows=extra_rows)
        except Exception:
            final_image = best_image

    wagon_idx = train_session.add_wagon(winner, rel_y=median_rel_y,
                                        image=final_image, tv_info=tv_info,
                                        already_written=already_written)

    if wagon_idx is not None:
        tv_txt = ""
        if tv_info:
            parts = []
            if tv_info.get("t"):
                parts.append(f"TONNA {tv_info['t']}")
            if tv_info.get("v"):
                parts.append(f"HAJM {tv_info['v']}")
            tv_txt = (" | " + "  ".join(parts)) if parts else ""
        print(f"\n[EVENT] 🚆 Wagon ID:{track_id} | Number: {winner} | ✅ VALID{source_tag}{tv_txt}")
        stats['read_success'] += 1
        stats['read_valid'] += 1
        print("-" * 50)
    # takror trek bo'lsa ham, keyin kelgan qiymat o'sha yozuvga borsin
    return wagon_idx if wagon_idx is not None else getattr(train_session, "last_merge_index", None)


def setup_device():
    """Qurilmani tanlaydi va unga moslashadi. Qaytaradi: "cuda" yoki "cpu"."""
    global DEVICE, TV_DET_OPENVINO_DEVICE
    want = str(DEVICE).lower()
    if want == "auto":
        want = "cuda" if torch.cuda.is_available() else "cpu"
    if want.startswith("cuda") and not torch.cuda.is_available():
        print("⚠️  GPU so'ralgan, lekin CUDA mavjud emas -- CPU ishlatiladi")
        want = "cpu"
    DEVICE = "cuda" if want.startswith("cuda") else "cpu"
    if DEVICE == "cuda":
        try:
            # GPU haqiqatan ishlayaptimi (drayver xatosi, xotira yetmasligi) -- aks holda CPU ga o'tiladi
            _x = torch.randn(256, 256, device="cuda")
            assert torch.isfinite(_x @ _x).all()
            del _x
        except Exception as e:
            print(f"⚠️  GPU ishga tushmadi ({e}) -- CPU ga o'tildi")
            DEVICE = "cpu"
    if DEVICE == "cuda":
        name = torch.cuda.get_device_name(0)
        mem = torch.cuda.get_device_properties(0).total_memory / 2 ** 30
        print(f"⚙️  Qurilma: GPU -- {name} ({mem:.0f} GB)")
    if DEVICE == "cpu":
        n = os.cpu_count() or 4
        torch.set_num_threads(n)          # ba'zi tizimlarda standart 1 ta ip bo'ladi
        cv2.setNumThreads(n)
        print(f"⚙️  Qurilma: CPU ({n} yadro, {platform.machine()}) -- GPU topilmadi. "
              f"Video fayl har bir kadri bilan tahlil qilinadi (aniqlik saqlanadi), lekin sekinroq.")
        if (TV_DET_OPENVINO_DEVICE is None and platform.machine().lower() in ("x86_64", "amd64")
                and importlib.util.find_spec("openvino") is not None):
            # Intel/AMD protsessorda eng og'ir model (t/v detektori) OpenVINO bilan 2-3 barobar tez.
            TV_DET_OPENVINO_DEVICE = "intel:cpu"
    return DEVICE


def dev():
    """predict(device=...) uchun: tanlangan qurilma (ultralytics o'zi tanlasa, CPU so'ralganda ham GPU oladi)."""
    return "cpu" if DEVICE == "cpu" else 0


def is_live_source(src):
    """Kamera indeksi, /dev/video*, RTSP/HTTP oqimi -- jonli; qolgani -- video fayl."""
    if isinstance(src, int) or FORCE_LIVE:
        return True
    s = str(src).strip().lower()
    return s.isdigit() or s.startswith(("rtsp://", "rtsps://", "rtmp://", "http://", "https://",
                                        "udp://", "tcp://", "/dev/video"))


def mask_source(src):
    """Jurnalga parol chiqmasin: rtsp://admin:parol@ip -> rtsp://admin:***@ip"""
    s = str(src)
    if "://" in s and "@" in s:
        head, rest = s.split("://", 1)
        cred, host = rest.rsplit("@", 1)
        if ":" in cred:
            return f"{head}://{cred.split(':', 1)[0]}:***@{host}"
    return s


_ACTIVE_CAPTURES = []
# Ochiq VideoWriter'lar. mp4 ning indeksi (moov atom) fayl YOPILGANDA
# yoziladi — release() qilinmasa video umuman ochilmaydi. CTRL+C bilan
# to'xtatilganda ham yopilishi uchun shu ro'yxat orqali kuzatiladi.
_ACTIVE_WRITERS = []


def _close_writers():
    for _w in list(_ACTIVE_WRITERS):
        try:
            _w.release()
        except Exception:
            pass
        _ACTIVE_WRITERS.remove(_w)


class LiveCapture:
    """
    Jonli manba (IP-kamera, RTSP, USB-kamera) uchun ishonchli o'quvchi.

    * Kadrlar alohida oqimda uzluksiz o'qiladi, read() har doim ENG YANGI kadrni beradi:
      ishlov bir lahza sekinlashsa ham kechikish to'planmaydi (eski kadrlar tashlanadi).
    * Oqim uzilsa yoki qotsa -- o'zi qayta ulanadi; read() hech qachon "tugadi" demaydi.
    * Sinov uchun video faylni ham kamera kabi o'qiy oladi (--jonli): o'z tezligida,
      oxiriga yetganda "uzilish" deb qayta ochadi.
    """

    def __init__(self, source):
        self.source = int(source) if str(source).strip().isdigit() else source
        self.is_file = isinstance(self.source, str) and os.path.isfile(self.source)
        self.lock = threading.Condition()
        self.frame, self.seq, self.read_seq = None, 0, 0
        self.last_frame_time = time.time()
        self.reconnects = 0
        self.running = True
        self.cap = None
        self.width = self.height = 0
        self.fps = 25.0
        self.generation = 0
        self.conn_id = 0                    # ulanish urinishlari zanjiri raqami -- faqat eng yangisi ishlaydi
        self.connecting = False             # hozir _connect() urinishlari ketyaptimi
        self.conn_beat = time.time()        # oxirgi urinish vaqti (qotgan urinishni aniqlash uchun)
        _ACTIVE_CAPTURES.append(self)
        self._connect(first=True)
        self._start_thread()

    def _open(self):
        if isinstance(self.source, int):
            backend = cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_V4L2
            cap = cv2.VideoCapture(self.source, backend)
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            return cap
        if not self.is_file:
            # RTSP TCP orqali -- UDP da paketlar yo'qolib, kadrlar buziladi.
            os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
        params = []
        for name, val in (("CAP_PROP_OPEN_TIMEOUT_MSEC", LIVE_OPEN_TIMEOUT_MS),
                          ("CAP_PROP_READ_TIMEOUT_MSEC", LIVE_READ_TIMEOUT_MS)):
            if hasattr(cv2, name):
                params += [getattr(cv2, name), val]
        try:
            return cv2.VideoCapture(self.source, cv2.CAP_FFMPEG, params)
        except Exception:
            return cv2.VideoCapture(self.source, cv2.CAP_FFMPEG)

    def _connect(self, first=False):
        """Ulanguncha urinadi (kutish 1 s dan LIVE_RECONNECT_MAX_WAIT gacha oshib boradi).
        Bir vaqtda faqat BITTA urinishlar zanjiri ishlaydi: yangisi boshlansa (conn_id o'zgarsa),
        eskisi keyingi qadamida o'zi to'xtaydi va False qaytaradi."""
        with self.lock:
            self.conn_id += 1
            my = self.conn_id
            self.connecting = True
        wait = 1
        try:
            while self.running and my == self.conn_id:
                self.conn_beat = time.time()
                cap = None
                try:
                    cap = self._open()
                    ok, f = cap.read() if cap is not None and cap.isOpened() else (False, None)
                    if ok and f is not None:
                        with self.lock:
                            if not self.running or my != self.conn_id:
                                break               # shu orada o'rnimizga yangi urinish boshlangan
                            self.cap, cap = cap, None
                            self.height, self.width = f.shape[:2]
                            self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 25.0
                            if not (1 <= self.fps <= 240):
                                self.fps = 25.0
                            self.frame = f
                            self.seq += 1
                            self.last_frame_time = time.time()
                            self.connecting = False
                            self.lock.notify_all()
                        if not first:
                            print(f"✅ Manbaga qayta ulandi ({self.reconnects}-marta): {mask_source(self.source)}")
                        return True
                except Exception as e:
                    print(f"⚠️  Manbani ochishda xato: {e}")
                finally:
                    if cap is not None:
                        try:
                            cap.release()
                        except Exception:
                            pass
                if not self.running or my != self.conn_id:
                    break
                print(f"⚠️  Manbaga ulanib bo'lmadi ({mask_source(self.source)}) -- {wait} s dan keyin qayta urinish")
                self.conn_beat = time.time()
                time.sleep(wait)
                wait = min(wait * 2, LIVE_RECONNECT_MAX_WAIT)
            return False
        finally:
            with self.lock:
                if my == self.conn_id:
                    self.connecting = False

    def _start_thread(self):
        self.generation += 1
        th = threading.Thread(target=self._loop, args=(self.generation,), daemon=True)
        th.start()

    def _loop(self, gen):
        period = 1.0 / self.fps if self.is_file else 0.0
        next_t = time.perf_counter()
        while self.running and gen == self.generation:
            try:
                ok, f = self.cap.read()
            except Exception:
                ok, f = False, None
            if gen != self.generation:
                return                      # qotgan eski oqim -- o'rniga yangisi ishlayapti
            if ok and f is not None:
                with self.lock:
                    self.frame = f
                    self.seq += 1
                    self.last_frame_time = time.time()
                    self.lock.notify_all()
                if period:
                    next_t += period
                    time.sleep(max(0.0, next_t - time.perf_counter()))
                continue
            if not self.running:
                return
            print("⚠️  Oqim uzildi -- qayta ulanmoqda...")
            try:
                self.cap.release()
            except Exception:
                pass
            self.reconnects += 1
            self._connect()
            next_t = time.perf_counter()

    def read(self):
        """Yangi kadr kelguncha kutadi va uni qaytaradi. Oqim qotib qolsa -- qayta ulaydi."""
        with self.lock:
            while self.running and self.seq == self.read_seq:
                self.lock.wait(timeout=1.0)
                now = time.time()
                if self.running and now - self.last_frame_time > LIVE_STALL_SECONDS:
                    # Uzilishdan keyin qayta ulanish allaqachon ketayotgan bo'lsa, ustiga yangisini
                    # boshlamaymiz: aks holda uzilish davomida har 20 s da yana bitta urinishlar zanjiri
                    # qo'shilib, kamera qaytganda hammasi ketma-ket ulanardi (oqim qayta-qayta uzilardi).
                    # Faqat o'sha urinishning o'zi qotib qolgan bo'lsa (uzoq vaqt belgi bermasa) aralashamiz.
                    if self.connecting and now - self.conn_beat < LIVE_CONNECT_HANG_SECONDS:
                        continue
                    print(f"⚠️  {LIVE_STALL_SECONDS} s dan beri yangi kadr yo'q -- oqim qotgan, qayta ulanmoqda")
                    self.last_frame_time = now
                    self.reconnects += 1
                    threading.Thread(target=self._restart_stalled, daemon=True).start()
            if not self.running:
                return False, None
            self.read_seq = self.seq
            return True, self.frame

    def _restart_stalled(self):
        old = self.cap
        self.generation += 1                # eski (qotgan) oqim natijasi e'tiborsiz qoladi
        if self._connect():
            self._start_thread()
        try:
            old.release()
        except Exception:
            pass

    def grab(self):
        return False

    def isOpened(self):
        return self.cap is not None

    def get(self, prop):
        if prop == cv2.CAP_PROP_FRAME_WIDTH:
            return self.width
        if prop == cv2.CAP_PROP_FRAME_HEIGHT:
            return self.height
        if prop == cv2.CAP_PROP_FPS:
            return self.fps
        return 0

    def set(self, *a):
        return False

    def release(self):
        self.running = False
        with self.lock:
            self.lock.notify_all()
        try:
            if self.cap is not None:
                self.cap.release()
        except Exception:
            pass
        if self in _ACTIVE_CAPTURES:
            _ACTIVE_CAPTURES.remove(self)


class PacedFileReader:
    """
    Video faylni jonli kamera kabi o'z tezligida beradi (5 daqiqalik video -- 5 daqiqa).

    Dekodlash alohida oqimda: har bir kadr o'z vaqtida tayyor bo'ladi, read() esa
    ENG YANGI kadrni va uning videodagi tartib raqamini qaytaradi. Ishlov orqada
    qolsa, oraliq kadrlar shunchaki o'tkazib yuboriladi -- asosiy oqim ularni
    dekodlashga vaqt sarflamaydi (ilgari grab() bilan tashlanardi, HEVC da har
    biri ~7 ms edi va orqada qolish o'z-o'zidan kuchayardi).
    """

    def __init__(self, path):
        self.cap = cv2.VideoCapture(path, cv2.CAP_FFMPEG)
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 25.0
        if not (1 <= self.fps <= 240):
            self.fps = 25.0
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.lock = threading.Condition()
        self.frame, self.index, self.read_index = None, 0, 0
        self.done = False
        self.running = True
        self.start_time = None
        self.thread = None

    def isOpened(self):
        return self.cap.isOpened()

    def get(self, prop):
        if prop == cv2.CAP_PROP_FRAME_WIDTH:
            return self.width
        if prop == cv2.CAP_PROP_FRAME_HEIGHT:
            return self.height
        if prop == cv2.CAP_PROP_FPS:
            return self.fps
        return self.cap.get(prop)

    def _loop(self):
        i = 0
        while self.running:
            ok, f = self.cap.read()
            if not ok or f is None:
                break
            i += 1
            wait = self.start_time + (i - 1) / self.fps - time.perf_counter()
            if wait > 0:
                time.sleep(wait)
            with self.lock:
                self.frame, self.index = f, i
                self.lock.notify_all()
        with self.lock:
            self.done = True
            self.lock.notify_all()

    def read(self):
        """(ok, kadr, kadr_raqami). Jadval birinchi chaqiruvda boshlanadi (modellar tayyor bo'lgach)."""
        if self.thread is None:
            self.start_time = time.perf_counter()
            self.thread = threading.Thread(target=self._loop, daemon=True)
            self.thread.start()
        with self.lock:
            while self.index == self.read_index and not self.done:
                self.lock.wait(timeout=1.0)
            if self.index == self.read_index:
                return False, None, self.index
            self.read_index = self.index
            return True, self.frame, self.index

    def release(self):
        self.running = False
        if self.thread is not None:
            self.thread.join(timeout=2.0)
        self.cap.release()


FORCE_LIVE = False
_RUN_STATE = {"quit": False}


def cleanup_old_results():
    """KEEP_DAYS dan eski natijalarni (rasm papkalari, hisobot fayllari) o'chiradi."""
    if not KEEP_DAYS or KEEP_DAYS <= 0 or not os.path.isdir(TRAINS_OUTPUT_DIR):
        return
    edge = datetime.datetime.now() - datetime.timedelta(days=KEEP_DAYS)
    for name in os.listdir(TRAINS_OUTPUT_DIR):
        try:
            day = datetime.datetime.strptime(name, "%Y.%m.%d")   # faqat kun papkalari
        except ValueError:
            continue
        if day < edge:
            shutil.rmtree(os.path.join(TRAINS_OUTPUT_DIR, name), ignore_errors=True)


def run_realtime():
    setup_device()
    print("📡 Loading detector model (YOLOv8)...")
    try:
        detector = load_model(VAGON_NUMBER_DETECTION, NUMBER_IMGSZ)
    except Exception as e:
        print(f"Error loading detector: {e}")
        return

    print("⏳ Loading digit detector (YOLOv8)...")
    try:
        classifier = load_model(VAGON_NUMBER_CLASSIFICATION, NUMBER_IMGSZ)
    except Exception as e:
        print(f"Error loading classifier: {e}")
        return

    tv_detector = tv_classifier = tv_det_device = None
    tv_active = False
    if TV_ENABLED:
        try:
            print("🔤 Loading t/v plate detector...")
            tv_detector, tv_det_device = load_tv_detector()
            print("🔤 Loading t/v character reader...")
            tv_classifier = load_model(TV_CLASSIFICATION, TV_CLS_IMGSZ)
            tv_active = True
            print(f"   t/v detektor klasslari : {tv_detector.names}")
            print(f"   t/v belgi klasslari    : {tv_classifier.names}")
        except Exception as e:
            print(f"⚠️  t/v modellari yuklanmadi ({e}) -- t/v o'qish O'CHIRILDI, "
                  f"raqam aniqlash odatdagidek davom etadi.")
            tv_active = False

    gui_available = check_gui_support()

    _live_source = is_live_source(VIDEO_SOURCE)
    if _live_source:
        print(f"📷 Jonli manbaga ulanmoqda: {mask_source(VIDEO_SOURCE)}")
        cap = LiveCapture(VIDEO_SOURCE)
    else:
        pace = REALTIME_PLAYBACK and not (DEVICE == "cpu" and CPU_PROCESS_EVERY_FRAME)
        if pace:
            cap = PacedFileReader(VIDEO_SOURCE)
        else:
            cap = cv2.VideoCapture(VIDEO_SOURCE, cv2.CAP_FFMPEG)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
    if not cap.isOpened():
        print("❌ Failed to open video source!")
        return

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    print(f"✅ Camera started: {width}x{height} @ {fps} FPS")

    # Jonli manba (kamera, RTSP/HTTP oqimi) -- real soat; fayl -- video vaqti.
    clock.configure(_live_source, fps)

    ui_scale = ui_scale_of(width)
    list_font_scale = RECOGNIZED_LIST_FONT_SCALE * ui_scale
    list_line_height = max(11, int(RECOGNIZED_LIST_LINE_HEIGHT * ui_scale))
    list_margin_left = max(4, int(RECOGNIZED_LIST_MARGIN_LEFT * ui_scale))
    list_margin_top = max(8, int(RECOGNIZED_LIST_MARGIN_TOP * ui_scale))
    list_margin_bottom = max(4, int(RECOGNIZED_LIST_MARGIN_BOTTOM * ui_scale))
    list_margin_right = max(6, int(RECOGNIZED_LIST_MARGIN_RIGHT * ui_scale))
    list_thickness = max(1, round(1.3 * ui_scale))
    list_shadow_thickness = list_thickness + 1
    line_thickness = max(1, round(1.4 * ui_scale))      # ramkalar va zona chiziqlari

    if SAVE_RESIZE_WIDTH and SAVE_RESIZE_WIDTH < width:
        save_width = SAVE_RESIZE_WIDTH
        save_height = int(height * (SAVE_RESIZE_WIDTH / width))
    else:
        save_width, save_height = width, height

    out = None
    if SAVE_RESULT:
        os.makedirs(TRAINS_OUTPUT_DIR, exist_ok=True)
        base_name, ext = os.path.splitext(OUTPUT_FILENAME)
        timestamp_str = datetime.datetime.now().strftime('%Y.%m.%d_%H.%M.%S')
        # Manba fayl nomi ham qo'shiladi: bir necha video ketma-ket
        # ishlanganda qaysi natija qaysi videodan ekani ko'rinib tursin.
        manba = ""
        if isinstance(VIDEO_SOURCE, str):
            manba = os.path.splitext(os.path.basename(VIDEO_SOURCE))[0]
            manba = f"_{manba}" if manba else ""
        FINAL_OUTPUT_PATH = os.path.join(
            TRAINS_OUTPUT_DIR, f"{timestamp_str}_{base_name}{manba}{ext}")
        fourcc_h264 = cv2.VideoWriter_fourcc(*'avc1')
        out = cv2.VideoWriter(FINAL_OUTPUT_PATH, fourcc_h264, fps, (save_width, save_height))
        if not out.isOpened():
            print("⚠️  H.264 (avc1) kodek topilmadi, mp4v kodekka qaytilmoqda")
            out = cv2.VideoWriter(FINAL_OUTPUT_PATH, cv2.VideoWriter_fourcc(*'mp4v'), fps, (save_width, save_height))
        else:
            print("✅ H.264 (avc1) kodek bilan saqlanmoqda")
        _ACTIVE_WRITERS.append(out)
        print(f"🎥 Video shu manzilga saqlanadi: {FINAL_OUTPUT_PATH}")

    frame_center_x = width / 2
    zone_pixel_width = width * ZONE_TOLERANCE
    zone_left = int(frame_center_x - zone_pixel_width)
    zone_right = int(frame_center_x + zone_pixel_width)
    track_scores = defaultdict(lambda: defaultdict(float))
    track_candidate_frames = defaultdict(lambda: defaultdict(int))
    track_position_votes = defaultdict(make_position_votes)
    track_position_vote_frames = defaultdict(int)
    track_lifespan = defaultdict(int)
    track_any_digit_seen = defaultdict(bool)
    track_middle_reads = defaultdict(lambda: defaultdict(int))   # o'rtaga qo'yilgan o'qishlar
    track_read_frames = defaultdict(int)
    track_rel_positions = defaultdict(list)
    track_session_ordinal = {}
    last_seen_frame = {}
    frame_count = 0

    track_best_conf = defaultdict(float)
    track_best_image = {}
    track_best_raw_crop = {}

    # {track_id: {"t": <ovoz idishi>, "v": <ovoz idishi>}}
    track_tv_votes = defaultdict(lambda: {"t": make_tv_slot(), "v": make_tv_slot()})
    # jonli ekranda ko'rsatish uchun
    track_tv_live = defaultdict(dict)
    track_last_box = {}          # {track_id: ([x1,y1,x2,y2], kadr raqami)}
    track_vx = {}                # {track_id: gorizontal tezlik, px/kadr}

    session_track_counter = [0]

    height_history = deque(maxlen=HEIGHT_HISTORY_MAXLEN)

    seen_stable_ids = set()
    finalized_wagon = {}         # {track_id: hisobotdagi vagon indeksi} -- kech kelgan qiymat uchun
    early_commit = {}            # {track_id: sessiya boshlanishi} -- trek yopilmasdan yozilgan vagonlar
    early_tried = set()          # erta yozishga bir marta urinib ko'rilgan treklar
    stats = {'read_success': 0, 'read_valid': 0}

    pace = isinstance(cap, PacedFileReader)
    play_start = None
    dropped_frames = 0
    proc_frames = 0

    hb_time, hb_frames = time.time(), 0

    track_first_frame = {}       # {track_id: trek birinchi ko'ringan kadr}
    ref_box_w = deque(maxlen=200)  # kadr chetiga tegmagan raqam qutilarining eni
    tv_pending = deque()         # [(kadr, plastinka, kesim)] -- egasi hali ko'rinmagan plastinkalar

    def full_box(b):
        """Kadr chetida kesilgan raqam qutisining to'liq o'lchamini tiklaydi (t/v biriktirish uchun):
        kesilgan qutining markazi va eni plastinkagacha bo'lgan masofani buzadi."""
        if not ref_box_w:
            return b
        rw = sorted(ref_box_w)[len(ref_box_w) // 2]
        if b[2] - b[0] >= rw:
            return b
        if b[0] <= 3:
            return [b[2] - rw, b[1], b[2], b[3]]
        if b[2] >= width - 3:
            return [b[0], b[1], b[0] + rw, b[3]]
        return b

    def tv_settle(tid):
        # trekning t/v o'qishi tugadi -- yozuvdagi qiymatlar yakuniy ovozga keltiriladi
        idx, votes = finalized_wagon.get(tid), track_tv_votes.get(tid)
        if idx is None or not votes:
            return
        number = train_session.wagons[idx][0] if 0 <= idx < len(train_session.wagons) else None
        for kind in ("t", "v"):
            val, support, crop = tv_slot_value(votes.get(kind), kind, number)
            _sl = votes.get(kind)
            if TV_SUMMARY and _sl and (_sl["raw"] or _sl["strn"]) and 0 <= idx < len(train_session.wagons):
                print(f"       [TV-YAKUN] {train_session.wagons[idx][0]} {kind}: tanlandi={val} | "
                      f"tiniq={dict(_sl['strn'])} | barcha={dict(_sl['raw'])} | "
                      f"eng_tiniq={dict(tv_top_counts(_sl))} | qoshimcha={_sl['extra']} | "
                      f"eski={tv_slot_value(_sl, kind, number, sharpest=False)[0]}")
            train_session.settle_wagon_value(idx, kind, val, support, crop, src=tid)

    def tv_read_plate(tid, p, tv_crop, draw):
        h = p["y2"] - p["y1"]
        if h < TV_READ_MIN_H or tv_crop.size == 0:
            return
        det_slot = track_tv_votes[tid][p["kind"]]
        if tv_slot_full(det_slot, h):
            return
        sharpness = tv_sharpness(tv_crop)
        sharp = sharpness >= TV_MIN_SHARPNESS
        # xira kadr ham o'qiladi, lekin faqat zaxira hisobi uchun va TV_MAX_READS tagacha --
        # GPU yuki cheklangan bo'lib qoladi
        need_raw = det_slot["rawn"] < TV_MAX_READS
        # undan keyin mayda plastinkaning xira kadri faqat tiniqroq yarmiga kira olsagina o'qiladi (TV_SHARPEST_FALLBACK)
        need_top = (TV_SHARPEST_FALLBACK and not sharp and not need_raw and h < TV_BIG_PLATE_H
                    and det_slot["extra"] < TV_SHARPEST_EXTRA_READS and tv_top_small(det_slot)
                    and sharpness > sorted(r[0] for r in det_slot["top"])[len(det_slot["top"]) // 2])
        if not sharp and not need_raw and not need_top:
            return
        chars, unit, cf, dot_pos = tv_read_chars(tv_classifier, tv_crop, prefer=p["kind"])
        if TV_DEBUG and chars:
            print(f"[TV] ID:{tid} {p['kind']} -> '{''.join(chars)}' birlik={unit} "
                  f"cls_conf={cf:.2f} det_conf={p['conf']:.2f} "
                  f"crop={tv_crop.shape[1]}x{tv_crop.shape[0]}")
        # Plastinka turi BELGI O'QISHIDAN olinadi: belgilar modeli birlikni
        # 419 ta haqiqiy kesimda 99% to'g'ri aniqladi, t/v detektori esa xira
        # kadrda adashadi -- bitta plastinka ikkala slotga tushib, vagonda
        # "68 t / 68 m3" kabi qiymat chiqardi.
        kind = ("t" if unit == "t" else "v") if unit else p["kind"]
        if need_raw:
            det_slot["rawn"] += 1
            tv_note_raw(track_tv_votes[tid][kind], chars, unit, dot_pos, kind, tv_crop)
        if need_top:
            det_slot["extra"] += 1
        if TV_SHARPEST_FALLBACK:
            tv_note_top(track_tv_votes[tid][kind], sharpness, chars, unit, dot_pos, kind, tv_crop)
        if sharp:
            tv_note_read(track_tv_votes[tid][kind], h)
        # Haqiqiy vagonnikiga o'xshamaydigan o'qish (bir xonali "7" -- kesilgan
        # plastinka yoki logotip, "881120" -- ikki plastinka qo'shilib ketgan)
        # ovozga kirmaydi: aks holda u to'g'ri qiymatning ovozini bosib ketadi.
        if (sharp and chars and not (TV_REQUIRE_UNIT and not unit)
                and tv_plausible(tv_apply_decimal("".join(chars), kind, dot_pos), kind)):
            tv_add_vote(track_tv_votes[tid][kind], chars, cf * p["conf"], tv_crop, dot_pos)
        _idx = finalized_wagon.get(tid)
        _num = train_session.wagons[_idx][0] if _idx is not None and 0 <= _idx < len(train_session.wagons) else None
        live_val, support, live_crop = tv_slot_value(track_tv_votes[tid][kind], kind, _num)
        if live_val:
            track_tv_live[tid][kind] = live_val
            if tid in finalized_wagon:      # vagon allaqachon yozilgan bo'lsa
                train_session.update_wagon_value(
                    finalized_wagon[tid], kind, live_val, support, live_crop, src=tid)
            if draw:
                draw_plate_label(frame, f"{live_val}{'t' if kind == 't' else 'm3'}",
                                 p["x1"], p["y1"],
                                 (255, 200, 0) if kind == "t" else (0, 200, 255),
                                 ui=ui_scale)

    print("🚀 Started. Press 'q' to exit.")
    while True:
        if _live_source and time.time() - hb_time >= HEARTBEAT_SECONDS:
            el = time.time() - hb_time
            print(f"💓 {datetime.datetime.now():%Y-%m-%d %H:%M:%S} ishlayapti: "
                  f"{(frame_count - hb_frames) / el:.1f} kadr/s ishlandi, "
                  f"qayta ulanishlar {getattr(cap, 'reconnects', 0)}, "
                  f"joriy poyezdda {len(train_session.wagons)} vagon", flush=True)
            hb_time, hb_frames = time.time(), frame_count
        if pace:
            success, frame, idx = cap.read()
            if success:
                if play_start is None:
                    play_start = time.perf_counter()
                dropped_frames += idx - frame_count - 1
                frame_count = idx
        else:
            success, frame = cap.read()
            frame_count += 1
        if not success:
            print("⚠️ Stream interrupted or camera disconnected.")
            break
        proc_frames += 1
        clock.tick(frame_count)
        # Kroplar SHU nusxadan olinadi: `frame` ga zona chiziqlari, ramkalar va yozuvlar
        # chiziladi, ular plastinka yoki raqam ustidan o'tib o'qishni buzishi mumkin.
        clean_frame = frame.copy()
        results = detector.track(frame, persist=True, verbose=False, tracker="bytetrack.yaml",
                                 conf=WAGON_DETECTOR_CONF, agnostic_nms=WAGON_DETECTOR_AGNOSTIC_NMS,
                                 device=dev())
        result = results[0]
        cv2.line(frame, (zone_left, 0), (zone_left, height), (200, 200, 200), line_thickness)
        cv2.line(frame, (zone_right, 0), (zone_right, height), (200, 200, 200), line_thickness)

        track_ids, boxes, assoc_boxes = [], [], []
        if result.boxes is not None and result.boxes.id is not None:
            track_ids = result.boxes.id.int().cpu().tolist()
            boxes = result.boxes.xyxy.cpu().tolist()
            for b in boxes:
                if b[0] > 3 and b[2] < width - 3:
                    ref_box_w.append(b[2] - b[0])
            assoc_boxes = [full_box(b) for b in boxes] if TV_FULL_BOX else list(boxes)
            for tid, b in zip(track_ids, assoc_boxes):
                track_first_frame.setdefault(tid, frame_count)
                prev = track_last_box.get(tid)
                if prev:
                    df = frame_count - prev[1]
                    if 0 < df <= 5:
                        v = ((b[0] + b[2]) - (prev[0][0] + prev[0][2])) / 2.0 / df
                        track_vx[tid] = v if tid not in track_vx else 0.6 * track_vx[tid] + 0.4 * v
                track_last_box[tid] = (list(b), frame_count)

        # ---------- t/v plastinkalari: HAR KADRDA ----------
        # Ilgari bu blok "raqam qutisi topilgan bo'lsa" ichida edi. Plastinka eng katta va
        # aniq ko'ringan paytda vagon raqami ko'pincha kadrdan chiqib ketgan bo'ladi --
        # aynan eng yaxshi kadrlar umuman qidirilmay qolardi.
        tv_assigned = {}
        if tv_active and frame_count % TV_FRAME_STRIDE == 0:
            tv_plates = tv_detect_plates(tv_detector, clean_frame, tv_det_device)
            # Chegara zonasi PLASTINKAGA qo'yiladi, raqamga emas: chekkadagi
            # plastinka kesilgan va xira bo'ladi, bundan tashqari uzoqdagi
            # plastinka qo'shni vagonning trekiga yopishib, qiymatlarni
            # aralashtirib yuboradi.
            centered = [p for p in tv_plates if zone_left < p["cx"] < zone_right]
            # Avval KADRDA KO'RINIB turgan vagonlarga biriktiriladi.
            tv_assigned = tv_assign_to_tracks(centered, assoc_boxes, track_ids)
            # Egasi topilmagan plastinkalar uchun zaxira: raqami kadrdan chiqib ketgan
            # treklarning oxirgi qutisi tezlik bo'yicha oldinga siljitiladi (poyezd bir
            # tekis harakatlanadi). Bashorat faqat ZAXIRA -- aks holda eski trekning
            # taxminiy qutisi plastinkani ko'rinib turgan vagondan tortib oladi.
            taken = {id(p) for ps in tv_assigned.values() for p in ps}
            rest = [p for p in centered if id(p) not in taken]
            if rest:
                pred_boxes, pred_ids = [], []
                for tid, (lb, lf) in track_last_box.items():
                    gap = frame_count - lf
                    if tid in track_ids or not (0 < gap <= TV_PREDICT_MAX_FRAMES) or tid not in track_vx:
                        continue
                    shift = track_vx[tid] * gap
                    pred_boxes.append([lb[0] + shift, lb[1], lb[2] + shift, lb[3]])
                    pred_ids.append(tid)
                if pred_boxes:
                    for tid, ps in tv_assign_to_tracks(rest, pred_boxes, pred_ids).items():
                        tv_assigned.setdefault(tid, []).extend(ps)
                taken = {id(p) for ps in tv_assigned.values() for p in ps}
                # Hali egasi yo'q plastinka -- bufer (raqami keyin keladigan vagonniki bo'lishi mumkin).
                for p in rest:
                    if id(p) not in taken and p["y2"] - p["y1"] >= TV_READ_MIN_H:
                        tv_pending.append((frame_count, p, clean_frame[p["y1"]:p["y2"], p["x1"]:p["x2"]].copy()))
            for p in tv_plates:
                col = (255, 200, 0) if p["kind"] == "t" else (0, 200, 255)
                if p not in centered:
                    col = (110, 110, 110)
                cv2.rectangle(frame, (p["x1"], p["y1"]), (p["x2"], p["y2"]), col, line_thickness)

            for tid, plates in tv_assigned.items():
                for p in plates:
                    tv_read_plate(tid, p, clean_frame[p["y1"]:p["y2"], p["x1"]:p["x2"]], draw=True)

        # Buferdagi plastinkalar: kadrda ko'rinib turgan, plastinka paytida hali YO'Q bo'lgan
        # trekning qutisi tezlik bo'yicha o'sha kadrga orqaga siljitiladi.
        while tv_pending and frame_count - tv_pending[0][0] > TV_PENDING_MAX_FRAMES:
            tv_pending.popleft()
        if tv_pending and track_ids:
            cand = [(tid, b) for tid, b in zip(track_ids, assoc_boxes) if tid in track_vx]
            done, keep = 0, deque()
            for pf, p, crop in tv_pending:
                if done >= TV_PENDING_READS_PER_FRAME:
                    keep.append((pf, p, crop))
                    continue
                back_boxes, back_ids = [], []
                for tid, b in cand:
                    if track_first_frame.get(tid, 0) <= pf:
                        continue                # plastinka paytida bu trek bor edi -- o'shanda hal bo'lgan
                    shift = track_vx[tid] * (frame_count - pf)
                    back_boxes.append([b[0] - shift, b[1], b[2] - shift, b[3]])
                    back_ids.append(tid)
                owner = tv_assign_to_tracks([p], back_boxes, back_ids) if back_boxes else {}
                if owner:
                    tv_read_plate(next(iter(owner)), p, crop, draw=False)
                    done += 1
                else:
                    keep.append((pf, p, crop))
            tv_pending = keep

        if track_ids:
            for box, track_id in zip(boxes, track_ids):
                track_lifespan[track_id] += 1
                last_seen_frame[track_id] = frame_count
                x1_orig, y1_orig, x2_orig, y2_orig = map(int, box)
                box_center_x = (x1_orig + x2_orig) / 2
                box_h = y2_orig - y1_orig
                is_stable = track_lifespan[track_id] > 2

                if is_stable and track_id not in seen_stable_ids:
                    seen_stable_ids.add(track_id)
                    if track_id not in track_session_ordinal:
                        track_session_ordinal[track_id] = session_track_counter[0]
                        session_track_counter[0] += 1

                is_in_x_zone = zone_left < box_center_x < zone_right

                is_main_track = True
                median_h_debug = None
                if is_in_x_zone:
                    height_history.append(box_h)
                    if len(height_history) >= MIN_SAMPLES_FOR_ADAPTIVE:
                        sorted_heights = sorted(height_history)
                        n = len(sorted_heights)
                        median_h_debug = sorted_heights[n // 2] if n % 2 == 1 else \
                            (sorted_heights[n // 2 - 1] + sorted_heights[n // 2]) / 2
                        is_main_track = box_h >= (median_h_debug * ADAPTIVE_HEIGHT_RATIO)

                is_in_zone = is_in_x_zone and is_main_track
                color = (0, 0, 255)

                if is_in_zone:
                    color = (0, 255, 0)

                    pad_v = int(box_h * CROP_PADDING_RATIO_V)
                    pad_v = max(CROP_PADDING_MIN, min(CROP_PADDING_MAX, pad_v))
                    pad_h = int(box_h * CROP_PADDING_RATIO_H)
                    pad_h = max(4, min(CROP_PADDING_MAX, pad_h))

                    x1_pad = max(0, x1_orig - pad_h)
                    y1_pad = max(0, y1_orig - pad_v)
                    x2_pad = min(width, x2_orig + pad_h)
                    y2_pad = min(height, y2_orig + pad_v)
                    crop = clean_frame[y1_pad:y2_pad, x1_pad:x2_pad]

                    box_aspect_ratio = (x2_orig - x1_orig) / max(1, box_h)
                    is_plausible_plate_shape = box_aspect_ratio >= MIN_PLATE_ASPECT_RATIO

                    # Raqam allaqachon ko'p marta bir xil o'qilgan bo'lsa (masalan to'xtab turgan
                    # vagon) har kadrda qayta o'qilmaydi -- faqat har DIGIT_SETTLED_EVERY kadrda
                    # tekshirib turiladi. Bo'shagan vaqt yangi kelayotgan vagonlarga qoladi.
                    settled = None
                    if (track_position_vote_frames[track_id] >= DIGIT_ENOUGH_READS
                            and track_lifespan[track_id] % DIGIT_SETTLED_EVERY != 0):
                        lead, agr = build_voted_number(track_position_votes[track_id])
                        if lead and agr >= DIGIT_SETTLED_AGREEMENT and validate_wagon_number(lead):
                            settled = lead
                    if settled:
                        _now = clock.now()
                        train_session.activity(_now)
                        _seen = train_session.last_number_time.get(settled)
                        if (_seen is not None and
                                (_now - _seen).total_seconds() < DUPLICATE_NUMBER_COOLDOWN_SECONDS):
                            # yozilgan vagon UZLUKSIZ ko'rinib turibdi: takror to'sig'i oxirgi marta
                            # KO'RINGAN vaqtdan sanaladi (soatlab turgan vagon sessiya yopilgach yangi
                            # poyezd bo'lib qolmasin). Ancha oldin ketib, qaytib kelgan vagonga tegmaydi.
                            train_session.last_number_time[settled] = _now
                        if (track_id not in early_tried
                                and track_lifespan[track_id] >= EARLY_COMMIT_SECONDS * fps):
                            early_tried.add(track_id)
                            _idx = process_finished_track(
                                track_id, track_scores.get(track_id),
                                track_candidate_frames.get(track_id, {}),
                                track_position_votes.get(track_id),
                                track_position_vote_frames.get(track_id, 0),
                                track_lifespan.get(track_id), stats,
                                track_any_digit_seen.get(track_id, False),
                                track_rel_positions.get(track_id), track_session_ordinal.get(track_id),
                                best_image=track_best_image.get(track_id),
                                raw_number_crop=track_best_raw_crop.get(track_id),
                                tv_votes=track_tv_votes.get(track_id),
                                middle_reads=track_middle_reads.get(track_id))
                            if _idx is not None:
                                finalized_wagon[track_id] = _idx
                                early_commit[track_id] = train_session.session_start
                        if SHOW_LIVE_LABEL:
                            draw_number_label(frame, settled, x1_orig, y1_orig, (0, 255, 0), ui_scale)

                    if crop.size > 0 and is_plausible_plate_shape and not settled:
                        crop_upscaled, applied_scale = maybe_upscale_crop(crop)
                        crop_sharp = sharpen_crop(crop_upscaled)

                        detected_digits, any_digit, avg_y_center = detect_digits_in_crop(
                            classifier, crop_sharp, x1_pad, y1_pad, box_center_x, track_id,
                            scale_factor=applied_scale)

                        if any_digit:
                            track_any_digit_seen[track_id] = True

                        if SPLIT_NUMBER_GROUPS and 3 <= len(detected_digits) <= 5:
                            # Raqam ikki guruhda yozilgan va detektor har yarmini alohida
                            # quti qilib topgan ("2434" | "4863"): yonidagi, bir xil
                            # balandlikdagi qutini qo'shib, birgalikda o'qiladi.
                            for ob in boxes:
                                ox1, oy1, ox2, oy2 = map(int, ob)
                                oh = oy2 - oy1
                                if (ox1, oy1, ox2, oy2) == (x1_orig, y1_orig, x2_orig, y2_orig) or oh <= 0:
                                    continue
                                if not (0.75 <= oh / max(1, box_h) <= 1.33):
                                    continue
                                if min(y2_orig, oy2) - max(y1_orig, oy1) < 0.6 * min(box_h, oh):
                                    continue
                                gap = max(ox1 - x2_orig, x1_orig - ox2)
                                if not (-0.3 * box_h <= gap <= 1.5 * box_h):
                                    continue
                                ux1, uy1 = min(x1_orig, ox1), min(y1_orig, oy1)
                                ux2, uy2 = max(x2_orig, ox2), max(y2_orig, oy2)
                                ux1p, uy1p = max(0, ux1 - pad_h), max(0, uy1 - pad_v)
                                ux2p, uy2p = min(width, ux2 + pad_h), min(height, uy2 + pad_v)
                                crop_u = clean_frame[uy1p:uy2p, ux1p:ux2p]
                                if crop_u.size == 0:
                                    continue
                                up_u, sc_u = maybe_upscale_crop(crop_u)
                                dd_u, _any_u, ay_u = detect_digits_in_crop(
                                    classifier, sharpen_crop(up_u), ux1p, uy1p, (ux1 + ux2) / 2,
                                    track_id, scale_factor=sc_u)
                                if len(dd_u) == 8:
                                    detected_digits, avg_y_center, crop = dd_u, ay_u, crop_u
                                    x1_pad, x2_pad = ux1p, ux2p
                                    break

                        if DIGIT_TRY_INVERTED and len(detected_digits) not in (8, 9):
                            dd_i, _any_i, ay_i = detect_digits_in_crop(
                                classifier, 255 - crop_sharp, x1_pad, y1_pad, box_center_x, track_id,
                                scale_factor=applied_scale)
                            if len(dd_i) in (8, 9):
                                detected_digits, avg_y_center = dd_i, ay_i

                        if len(detected_digits) >= 6:
                            train_session.activity(clock.now())   # vagon raqami ko'rinib turibdi

                        if len(detected_digits) == 9:
                            # Ortiqcha belgini geometriya hal qila olmadi -- nomzodlardan biri
                            # shu trekning boshqa kadrlarda to'plagan yetakchi raqami bo'lsa, o'sha.
                            leader, _agr = build_voted_number(track_position_votes[track_id])
                            if leader and validate_wagon_number(leader):
                                srt = sorted(detected_digits, key=lambda d: d[0])
                                for i in range(9):
                                    rest = srt[:i] + srt[i + 1:]
                                    if "".join(d[1] for d in rest) == leader:
                                        detected_digits = rest
                                        break

                        middle_fixed = False
                        if len(detected_digits) == 7:
                            ins = insert_missing_middle(detected_digits)
                            if ins:
                                detected_digits, middle_fixed = ins, True
                                track_middle_reads[track_id]["".join(d[1] for d in ins)] += 1

                        added_to_votes = add_position_votes(track_position_votes[track_id], detected_digits)
                        if added_to_votes:
                            track_position_vote_frames[track_id] += 1

                        final_number_str = None
                        is_repaired = False
                        avg_conf = 0.0

                        if detected_digits:
                            final_number_str, is_repaired, log = repair_number(
                                detected_digits, box_x1=x1_pad, box_x2=x2_pad)
                            is_repaired = is_repaired or middle_fixed
                            avg_conf = sum([d[2] for d in detected_digits]) / len(detected_digits)

                            if len(final_number_str) == 8 and avg_conf > 0.5:
                                is_valid = validate_wagon_number(final_number_str)

                                if is_valid:
                                    track_read_frames[track_id] += 1
                                    # O'rtaga qo'yilgan raqamli o'qish faqat pozitsion ovozga kiradi: bo'yalgan,
                                    # tartibsiz o'qilgan raqamda 3 ta shunday o'qish "repair-fallback" ni o'tib,
                                    # yolg'on raqam (52398054) yozardi.
                                    if not middle_fixed:
                                        track_candidate_frames[track_id][final_number_str] += 1
                                    score_boost = 3.0 * REPAIRED_SCORE_MULTIPLIER if is_repaired else 3.0
                                    text_color = (0, 255, 0)
                                    if not middle_fixed:
                                        track_scores[track_id][final_number_str] += (avg_conf * score_boost)

                                    wagon_box_h = max(1, y2_orig - y1_orig)
                                    if avg_y_center is not None:
                                        rel_y = (avg_y_center - y1_orig) / wagon_box_h
                                        track_rel_positions[track_id].append(rel_y)

                                    if (SAVE_WAGON_IMAGES and avg_conf > track_best_conf[track_id]
                                            and final_number_str.isdigit() and len(final_number_str) == 8):
                                        raw_view_img = crop
                                        if raw_view_img.size > 0:
                                            track_best_conf[track_id] = avg_conf
                                            display_number = final_number_str + ("*" if is_repaired else "")
                                            track_best_image[track_id] = combine_wagon_image(
                                                display_number, raw_view_img)
                                            track_best_raw_crop[track_id] = raw_view_img.copy()

                                    if SHOW_LIVE_LABEL:
                                        # t/v qiymatlari bu yerda emas -- ular
                                        # o'z plastinkasining ustiga yoziladi.
                                        draw_number_label(frame, final_number_str + ("*" if is_repaired else ""),
                                                          x1_orig, y1_orig, text_color, ui_scale)

                if is_stable:
                    cv2.rectangle(frame, (x1_orig, y1_orig), (x2_orig, y2_orig), color, line_thickness)
                    # ID raqam yorlig'idan TEPADA turadi: ilgari ular ustma-ust tushib,
                    # o'qilmay qolardi.
                    id_txt = f"ID:{track_id}"
                    id_scale = 0.38 * ui_scale
                    id_thick = max(1, round(ui_scale))
                    (iw, ih), ib = cv2.getTextSize(id_txt, cv2.FONT_HERSHEY_SIMPLEX, id_scale, id_thick)
                    iy = max(ih + 4, y1_orig - int(37 * ui_scale))
                    cv2.rectangle(frame, (x1_orig - 4, iy - ih - 4), (x1_orig + iw + 4, iy + ib + 2),
                                  (0, 0, 0), -1)
                    cv2.putText(frame, id_txt, (x1_orig, iy),
                                cv2.FONT_HERSHEY_SIMPLEX, id_scale, color, id_thick, cv2.LINE_AA)

        dead_tracks = []
        for tid, last_frame in last_seen_frame.items():
            if frame_count - last_frame > FRAMES_TO_FORGET:
                if tid in early_commit and early_commit[tid] != train_session.session_start:
                    # vagon oldingi sessiyada yozilgan (uzoq turib qolgan) -- yangi poyezdga qo'shilmaydi
                    dead_tracks.append(tid)
                    continue
                _idx = process_finished_track(tid, track_scores.get(tid), track_candidate_frames.get(tid, {}),
                                        track_position_votes.get(tid),
                                        track_position_vote_frames.get(tid, 0),
                                        track_lifespan.get(tid), stats,
                                        track_any_digit_seen.get(tid, False),
                                        track_rel_positions.get(tid), track_session_ordinal.get(tid),
                                        best_image=track_best_image.get(tid),
                                        raw_number_crop=track_best_raw_crop.get(tid),
                                        tv_votes=track_tv_votes.get(tid),
                                        middle_reads=track_middle_reads.get(tid),
                                        already_written=tid in early_commit)
                if _idx is not None:
                    finalized_wagon[tid] = _idx
                dead_tracks.append(tid)

        for tid in dead_tracks:
            seen_stable_ids.discard(tid)
            early_commit.pop(tid, None)
            early_tried.discard(tid)
            for d in (last_seen_frame, track_scores, track_candidate_frames, track_rel_positions,
                      track_position_votes, track_position_vote_frames, track_lifespan,
                      track_any_digit_seen, track_read_frames, track_session_ordinal, track_middle_reads,
                      track_best_conf, track_best_image, track_best_raw_crop):
                if tid in d:
                    del d[tid]
        # track_last_box / track_vx / track_tv_votes saqlanadi: plastinka vagon raqami
        # kadrdan chiqqandan keyin o'qilishi mumkin. Eskirganlari tozalanadi.
        for tid in [t for t, (_b, f0) in track_last_box.items()
                    if frame_count - f0 > TV_LATE_VALUE_FRAMES]:
            tv_settle(tid)
            for d in (track_last_box, track_vx, track_tv_votes, track_tv_live, finalized_wagon,
                      track_first_frame):
                if tid in d:
                    del d[tid]

        if train_session.should_close():
            for tid in list(finalized_wagon):
                tv_settle(tid)
            finalized_wagon.clear()          # indekslar shu sessiyaga tegishli edi
            train_session.close()
            height_history.clear()
            session_track_counter[0] = 0

        if SHOW_RECOGNIZED_LIST and train_session.wagons:
            available_height = height - list_margin_top - list_margin_bottom
            max_rows_that_fit = max(1, available_height // list_line_height)
            visible_wagons = train_session.wagons[-max_rows_that_fit:]
            # Ustunlar tekis tursin: kengliklar eng uzun bo'lishi mumkin qiymatlardan
            # olinadi (raqam 8 xona, tonna "125.5t", hajm "138.5m3").
            font = cv2.FONT_HERSHEY_SIMPLEX
            w_num = cv2.getTextSize("00000000", font, list_font_scale, list_thickness)[0][0]
            w_t = cv2.getTextSize("125.5t", font, list_font_scale, list_thickness)[0][0]
            w_v = cv2.getTextSize("138.5m3", font, list_font_scale, list_thickness)[0][0]
            col_gap = max(10, int(12 * ui_scale))
            block_w = w_num + col_gap + w_t + col_gap + w_v
            block_x = (width - block_w - list_margin_right
                       if RECOGNIZED_LIST_ON_RIGHT else list_margin_left)
            (_, th), tb = cv2.getTextSize("0", font, list_font_scale, list_thickness)
            if visible_wagons:                  # butun ro'yxat ortiga bitta fon
                y0 = list_margin_top - th - 6
                y1 = list_margin_top + (len(visible_wagons) - 1) * list_line_height + tb + 6
                bg = frame[max(0, y0):min(height, y1), max(0, block_x - 10):min(width, block_x + block_w + 10)]
                if bg.size:
                    bg[:] = (bg * RECOGNIZED_LIST_DIM).astype(bg.dtype)
            for idx, wagon_rec in enumerate(visible_wagons):
                number = wagon_rec[0]
                tv_info = wagon_rec[4] if len(wagon_rec) > 4 else {}
                t_txt = f"{tv_info['t']}t" if tv_info.get("t") else ""
                v_txt = f"{tv_info['v']}m3" if tv_info.get("v") else ""
                list_y = list_margin_top + idx * list_line_height
                for text, x, w_col in ((number, block_x, w_num),
                                       (t_txt, block_x + w_num + col_gap, w_t),
                                       (v_txt, block_x + w_num + col_gap + w_t + col_gap, w_v)):
                    if not text:
                        continue
                    tw = cv2.getTextSize(text, font, list_font_scale, list_thickness)[0][0]
                    tx = x + w_col - tw          # ustun ichida o'ngga tekislanadi
                    cv2.putText(frame, text, (tx + 1, list_y + 1), font, list_font_scale,
                                (0, 0, 0), list_shadow_thickness, cv2.LINE_AA)
                    cv2.putText(frame, text, (tx, list_y), font, list_font_scale,
                                (0, 255, 0), list_thickness, cv2.LINE_AA)

        if SHOW_CLOCK:
            clock_txt = clock.now().strftime(TIME_FMT)
            cfont = cv2.FONT_HERSHEY_SIMPLEX
            cy = height - list_margin_bottom
            cv2.putText(frame, clock_txt, (list_margin_left + 1, cy + 1), cfont, list_font_scale,
                        (0, 0, 0), list_shadow_thickness, cv2.LINE_AA)
            cv2.putText(frame, clock_txt, (list_margin_left, cy), cfont, list_font_scale,
                        (255, 255, 255), list_thickness, cv2.LINE_AA)

        if gui_available:
            try:
                display_frame = frame
                if width > 1920:
                    display_frame = cv2.resize(frame, (1280, 720))
                elif width < DISPLAY_MIN_WIDTH:
                    scale_up = DISPLAY_MIN_WIDTH / width
                    display_frame = cv2.resize(
                        frame, (int(width * scale_up), int(height * scale_up)),
                        interpolation=cv2.INTER_CUBIC)
                cv2.imshow("Wagon Number + TONNA/HAJM RealTime", display_frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    _RUN_STATE["quit"] = True
                    break
            except cv2.error as e:
                print(f"ℹ️  GUI/resize xatosi ({e}) -- oyna o'chirildi, ishlov berish davom etmoqda.")
                gui_available = False

        if out:
            if SAVE_RESIZE_WIDTH and SAVE_RESIZE_WIDTH < width:
                out.write(cv2.resize(frame, (save_width, save_height)))
            else:
                out.write(frame)

    for tid in list(last_seen_frame.keys()):
        if tid in early_commit and early_commit[tid] != train_session.session_start:
            continue
        _idx = process_finished_track(tid, track_scores.get(tid), track_candidate_frames.get(tid, {}),
                                track_position_votes.get(tid),
                                track_position_vote_frames.get(tid, 0),
                                track_lifespan.get(tid), stats,
                                track_any_digit_seen.get(tid, False),
                                track_rel_positions.get(tid), track_session_ordinal.get(tid),
                                best_image=track_best_image.get(tid),
                                raw_number_crop=track_best_raw_crop.get(tid),
                                tv_votes=track_tv_votes.get(tid),
                                middle_reads=track_middle_reads.get(tid),
                                already_written=tid in early_commit)
        if _idx is not None:
            finalized_wagon[tid] = _idx
    for tid in list(finalized_wagon):
        tv_settle(tid)

    train_session.close()

    if out:
        out.release()
        if out in _ACTIVE_WRITERS:
            _ACTIVE_WRITERS.remove(out)
    cap.release()
    if gui_available:
        cv2.destroyAllWindows()
        for _ in range(3):
            cv2.waitKey(1)

    print("\n" + "=" * 50)
    print("📊 YAKUNIY HISOBOT")
    print(f"✅ Checksum bo'yicha to'g'ri (VALID) chiqqan vagonlar: {stats['read_valid']}")
    if TV_ENABLED:
        print(f"🔤 TONNA/HAJM o'qilgan vagonlar: {train_session.total_tv_found}")
    if pace and play_start is not None:
        played = time.perf_counter() - play_start
        print(f"⏱️  Real vaqt: video {frame_count / fps:.1f} s -- ko'rsatildi {played:.1f} s, "
              f"ishlangan kadrlar {proc_frames}/{frame_count} ({proc_frames / max(played, 1e-6):.1f} kadr/s), "
              f"tashlangan {dropped_frames} ({100 * dropped_frames / max(frame_count, 1):.1f}%)")
    print(f"📁 Natijalar (har kun -- alohida papka): {TRAINS_OUTPUT_DIR}")
    print("=" * 50)
    print("🛑 Work completed.")


if __name__ == "__main__":
    # python logic3.py                      -- yuqoridagi VIDEO_SOURCE
    # python logic3.py video.mp4            -- boshqa video
    # python logic3.py video.mp4 --oynasiz  -- oynasiz (ketma-ket sinov uchun)
    # python logic3.py video.mp4 --natijalar <papka>  -- hisobotni boshqa papkaga
    # python logic3.py video.mp4 --tez      -- real vaqtni kutmasdan, imkon qadar tez
    # python logic3.py video.mp4 --cpu      -- GPU bo'lsa ham CPU da (sinov uchun)
    # python logic3.py video.mp4 --video    -- ramkali videoni ham saqlash
    # python logic3.py video.mp4 --vaqt "2025-12-10 16:05:00"  -- video yozilgan real vaqt
    _args = sys.argv[1:]
    if "--oynasiz" in _args or "--no-window" in _args:
        SHOW_WINDOW = False
        _args = [a for a in _args if a not in ("--oynasiz", "--no-window")]
    if "--oynali" in _args:
        SHOW_WINDOW = True                  # standart holat; birinchi argument bo'lib kelsa manba deb olinmasin
        _args = [a for a in _args if a != "--oynali"]
    if "--tez" in _args:
        REALTIME_PLAYBACK = False
        _args = [a for a in _args if a != "--tez"]
    if "--natijalar" in _args:
        _i = _args.index("--natijalar")
        TRAINS_OUTPUT_DIR = _args[_i + 1]
        _args = _args[:_i] + _args[_i + 2:]
    if "--vaqt" in _args:
        _i = _args.index("--vaqt")
        VIDEO_START_TIME = _args[_i + 1]
        datetime.datetime.strptime(VIDEO_START_TIME, "%Y-%m-%d %H:%M:%S")   # format tekshiruvi
        _args = _args[:_i] + _args[_i + 2:]
    if "--cpu" in _args:
        DEVICE = "cpu"
        _args = [a for a in _args if a != "--cpu"]
    if "--video" in _args:
        SAVE_RESULT = True
        _args = [a for a in _args if a != "--video"]
    if "--jonli" in _args:
        # sinov: video faylni jonli kamera kabi (o'z tezligida, oxirida qayta ulanib) o'qish
        FORCE_LIVE = True
        _args = [a for a in _args if a != "--jonli"]
    if _args:
        VIDEO_SOURCE = int(_args[0]) if _args[0].isdigit() else _args[0]

    def _on_term(signum, frame):
        raise KeyboardInterrupt
    try:
        signal.signal(signal.SIGTERM, _on_term)   # servis to'xtatilganda ham hisobot saqlanadi
    except (ValueError, AttributeError):
        pass

    if is_live_source(VIDEO_SOURCE):
        # 24/7: kutilmagan xato bo'lsa ham to'xtamaydi -- RESTART_DELAY_SECONDS dan keyin davom etadi.
        # Poyezd sessiyasi (train_session) saqlanib qoladi, yozilgan vagonlar yo'qolmaydi.
        while True:
            try:
                run_realtime()
                if _RUN_STATE["quit"]:
                    break
                print(f"↻ Ishlov to'xtadi -- {RESTART_DELAY_SECONDS} s dan keyin qayta ishga tushadi", flush=True)
            except KeyboardInterrupt:
                break
            except Exception:
                traceback.print_exc()
                print(f"↻ Kutilmagan xato -- {RESTART_DELAY_SECONDS} s dan keyin qayta ishga tushadi", flush=True)
            finally:
                for _c in list(_ACTIVE_CAPTURES):
                    _c.release()
                _close_writers()
            try:
                time.sleep(RESTART_DELAY_SECONDS)
            except KeyboardInterrupt:
                break
        print("\n🛑 To'xtatildi -- joriy poyezd hisoboti saqlanmoqda...", flush=True)
        train_session.close()
    else:
        try:
            run_realtime()
        except KeyboardInterrupt:
            print("\n🛑 To'xtatildi -- joriy poyezd hisoboti saqlanmoqda...", flush=True)
            train_session.close()
        finally:
            _close_writers()   # video yarim qolsa ham ochiladigan bo'lsin
    sys.stdout.flush()
    sys.stderr.flush()
    # Qt/CUDA yopilish tartibidagi segfault oldini olish: barcha fayllar allaqachon yozilgan.
    os._exit(0)