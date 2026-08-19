import cv2
import os
import numpy as np
import torch
import pathlib
import datetime
from ultralytics import YOLO
from collections import defaultdict, deque
import warnings
import time

VIDEO_SOURCE = './gruzovoy_poezd_6.mp4'

# ============ VIDEO O'RNIGA -- HAR BIR VAGON UCHUN RASM SAQLASH ============
# Foydalanuvchi so'rovi bo'yicha: endi butun videoni saqlash SHART EMAS.
# Uning o'rniga HAR BIR vagon uchun ENG YAXSHI (eng yuqori ishonch bilan
# o'qilgan) freymdan BITTA birlashtirilgan rasm saqlanadi:
#   - YUQORIDA : model TAHLIL QILGAN/o'qigan RAQAM hududi (label bilan)
#   - PASTIDA  : xuddi shu RAQAM hududining hech qanday ishlov berilmagan
#                ASL (xom) ko'rinishi -- solishtirish/tekshirish uchun
# Bitta poyezdning barcha vagon-rasmlari BITTA papkaga ("N-poyezd") tushadi;
# keyingi poyezd uchun alohida (sana+vaqt / tartib raqami bilan
# nomlangan) papka ochiladi -- xuddi hozirgi matnli hisobot fayllari kabi.
SAVE_RESULT = False           # eski video-yozish -- ENDI O'CHIRILGAN (kerak bo'lsa True qiling)
OUTPUT_FILENAME = 'realtime_result.mp4'
SAVE_RESIZE_WIDTH = None
SHOW_WINDOW = True  # GUI/display yo'q muhitda avtomatik o'chib qoladi

SAVE_WAGON_IMAGES = True       # YANGI: har bir vagon uchun rasm saqlansinmi
WAGON_IMAGES_SUBDIR = "images"  # trains/images/<sana>_<N>-poyezd/...
COMBINED_IMAGE_MAX_WIDTH = 700  # birlashtirilgan rasmning maksimal kengligi (piksel)
# =====================================================================

warnings.filterwarnings("ignore", category=FutureWarning)
temp = pathlib.PosixPath
pathlib.WindowsPath = pathlib.PosixPath

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VAGON_NUMBER_DETECTION = os.path.join(BASE_DIR, 'detection4.pt')
VAGON_NUMBER_CLASSIFICATION = os.path.join(BASE_DIR, 'classificationvagon.pt')

# ============ SOZLAMALAR ============s
DIGIT_CONF = 0.38
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
SHOW_WAGON_COUNTER = False  # "Wagons counted: N" yozuvi -- endi ekranga chiqarilmaydi
SHOW_RECOGNIZED_LIST = True
RECOGNIZED_LIST_FONT_SCALE = 0.42
RECOGNIZED_LIST_LINE_HEIGHT = 17
RECOGNIZED_LIST_MARGIN_RIGHT = 12
RECOGNIZED_LIST_MARGIN_TOP = 25
RECOGNIZED_LIST_MARGIN_BOTTOM = 20
MIN_LIST_FONT_SCALE = 0.45
MIN_LIST_LINE_HEIGHT = 16
DISPLAY_MIN_WIDTH = 1280
DEBUG_RAW_DETECTIONS = False

ADAPTIVE_HEIGHT_RATIO = 0.55
MIN_SAMPLES_FOR_ADAPTIVE = 15
HEIGHT_HISTORY_MAXLEN = 200
PRINT_BOX_HEIGHT_DEBUG = False

ROW_Y_TOLERANCE_RATIO = 0.6

DIGIT_CHARS = set("0123456789")
NON_DIGIT_DISCARD_THRESHOLD = 1  # hatto 1 ta begona belgi ham butun o'qishni bekor qiladi

MISSING_SIDE_GAP_RATIO = 0.55

# ============ YANGI: "OXIRGI RAQAMNI TAXMIN QILISH"NI O'CHIRISH ============
# MUAMMO: agar 7 ta raqam ko'rinib, 8-chisi (OXIRIDA/o'ngda) yetishmasa,
# eski kod uni checksum formulasi orqali "hisoblab" to'ldirar edi. LEKIN
# bu hisoblash HECH QANDAY haqiqiy tekshiruv bermaydi -- checksum
# raqami aynan shu 7 ta raqamning FUNKSIYASI, shuning uchun bu "taxmin"
# har doim -- hatto ko'rinib turgan 7 ta raqamning ICHIDA bittasi xato
# o'qilgan bo'lsa ham -- "muvaffaqiyatli" (checksumga mos) chiqaveradi.
# Bu xato TASODIFIY emas -- agar kamera bir xil tarzda kesib qo'ysa,
# xato HAR SAFAR bir xil holda takrorlanadi, shuning uchun "bir necha
# marta bir xil chiqsin" degan tekshiruv ham buni tuta olmaydi.
#
# Solishtirish uchun: "BIRINCHI raqam yetishmasa" holati BOSHQACHA --
# u yerda 0-9 orasidan checksumga mos keladigan YAGONA variant
# qidiriladi, bu haqiqiy (kamida 1/10) tekshiruv beradi, shuning uchun
# o'sha yo'l saqlab qolinadi.
ENABLE_MISSING_LAST_DIGIT_GUESS = False
# =====================================================================

# ============ YANGI: NOTO'G'RI HUDUD (RAQAM EMAS) FILTRI ============
# MUAMMO: ba'zan raqam-detektor (detection4.pt) vagon raqami o'rniga
# BOSHQA yozuv/logotip/belgi hududini "raqam" deb noto'g'ri aniqlab
# qo'yadi. Agar klassifikator o'sha harflarni DOIMIY ravishda (har
# freymda bir xil, tasodifiy emas) raqamlarga o'xshatib xato o'qisa --
# "3 marta bir xil chiqsin" talabi buni USHLAY OLMAYDI, chunki xato
# tizimli, tasodifiy emas.
#
# YECHIM: haqiqiy 8 xonali UIC vagon raqami HAR DOIM ancha CHO'ZIQ
# (keng, past) shaklda bo'ladi -- 8 ta raqam bir qatorda joylashgani
# uchun. Boshqa yozuv/logotip/belgi hududlari odatda bunday shaklda
# BO'LMAYDI (kvadratroq yoki torroq). Shuning uchun raqam-detektor
# bergan hududning KENGLIK/BALANDLIK nisbatini tekshiramiz -- agar bu
# nisbat haqiqiy raqam plastinkasiga o'xshamasa, o'sha freymda
# klassifikatorga umuman yubormaymiz (bu hudud e'tiborga olinmaydi).
MIN_PLATE_ASPECT_RATIO = 2.2  # kenglik/balandlik shundan kam bo'lsa -- raqam plastinkasi emas deb hisoblanadi
# =====================================================================

FAST_INSTANT_ACCEPT_CONF = 0.62
# ============ YANGI: XATO-QABUL QILISHNI KAMAYTIRISH ============
# MUAMMO: checksum FAQAT 1 ta xato raqamni ~90% ishonch bilan ushlaydi.
# Agar bir vaqtning o'zida 2+ raqam xato o'qilib, ular tasodifan
# checksumni "muvozanatlab" to'g'ri chiqarib qo'ysa -- dastur buni
# noto'g'ri ravishda VALID deb qabul qilardi (masalan 20 tadan 5 tasi
# shu sababli xato chiqqan edi).
#
# YECHIM: checksumga yolg'iz ishonish o'rniga, AYNAN BIR XIL natija
# bir nechta MUSTAQIL freymda qayta-qayta chiqishini talab qilamiz --
# tasodifiy (2+ raqamli) xato bir xil holda 3 marta qayta chiqishi
# statistik jihatdan deyarli mumkin emas. Shuning uchun talab qilinadigan
# freymlar sonini 2 dan 3 ga oshiramiz (ham repair-fallback, ham
# position-vote uchun).
FAST_MIN_READ_FRAMES = 3

POSITION_VOTE_MIN_FRAMES_STRONG = 3
# =====================================================================

SPACING_UNIFORMITY_MAX_RATIO = 2.2

DIAGNOSTIC_LOG_ENABLED = False

# =====================================================================
# ==========  LOKOMOTIV / BEGONA-YOZUV FILTRLARI (rangga bog'liq emas)  =
# =====================================================================
IGNORE_FIRST_N_TRACKS_PER_SESSION = 1

KNOWN_FALSE_POSITIVE_NUMBERS = {
    # bu yerga ma'lum lokomotiv/begona-yozuv raqamlarini qo'shib boring
    # "XXXXXXXX",
}

# ============ YANGI: POZITSIYA (BALANDLIK) ASOSLANGAN FILTR ============
# G'OYA: UIC standarti bo'yicha haqiqiy vagon raqami HAR DOIM vagon
# balandligining BIR XIL NISBIY qismida (odatda tom chizig'iga yaqin,
# yuqori qismda) joylashadi. Bu -- rangdan farqli o'laroq -- FIZIK/QOIDAGA
# ASOSLANGAN cheklov, shuning uchun turli poyezd/yorug'likda ham barqaror
# bo'lishi kerak. Kompaniya logotiplari, texnik yozuvlar va h.k. odatda
# vagonning BOSHQA (pastroq yoki tasodifiy) qismida joylashadi.
#
# ISHLASH TARZI: har bir SESSIYA (bitta poyezd o'tishi) davomida, barcha
# checksum-VALID o'qishlarning vagon balandligiga nisbatan qayerda
# joylashganini (0=vagon tepasi, 1=vagon tagi) yozib boramiz. Sessiya
# yakunlanganda MEDIANni hisoblab, mediandan SEZILARLI chetga chiquvchi
# o'qishlarni (masalan pastroqdagi logotip) hisobotdan chiqarib tashlaymiz.
# Bu -- rang-filtridagi bilan BIR XIL statistik g'oya, lekin RANG o'rniga
# POZITSIYAdan foydalanadi, shuning uchun turli xil rangdagi poyezdlarda
# ham universal ishlashi kutiladi.
ENABLE_POSITION_OUTLIER_FILTER = True
POSITION_OUTLIER_THRESHOLD = 0.18   # mediandan shuncha (vagon balandligining ulushi) farq -- begona deb hisoblanadi
MIN_WAGONS_FOR_POSITION_MEDIAN = 3  # shuncha yoki undan ko'p vagon bo'lsagina median hisoblab, filtrlaymiz
# =====================================================================

# ============ YANGI: TREK BO'LINIB KETISHI (FRAGMENTATSIYA) FILTRI ============
# MUAMMO: real natijalarni tahlil qilganda, ba'zan ikkita "vagon" orasida
# ATIGI 1 SONIYA farq borligi aniqlandi. Bu FIZIK JIHATDAN mumkin emas --
# haqiqiy vagon (hatto eng qisqasi ham) kamera zonasidan kamida bir necha
# soniyada o'tadi. Bunday "juda tez" holat odatda ByteTrack trekni
# vaqtincha yo'qotib (ustun/qo'shni vagon to'sib qo'yganda), keyin uni
# YANGI ID sifatida qayta boshlashi natijasida yuzaga keladi -- ya'ni
# BITTA jismoniy vagon IKKI marta hisoblanadi.
#
# YECHIM: agar yangi vagon oldingi qabul qilingan vagondan
# MIN_INTER_WAGON_SECONDS dan kamroq vaqt ichida kelsa -- bu "shubhali tez"
# deb hisoblanadi va FAQAT eng ishonchli yo'l (pozitsiya-ovoz, kamida
# FRAGMENTATION_STRONG_VOTE_MIN marta mustaqil tasdiqlangan) orqali qabul
# qilinadi; zaifroq repair-fallback yo'li bunday holatda BUTUNLAY rad etiladi.
MIN_INTER_WAGON_SECONDS = 2.0
FRAGMENTATION_STRONG_VOTE_MIN = 3
# =====================================================================

TRAINS_OUTPUT_DIR = os.path.join(BASE_DIR, "trains")
TRAIN_SESSION_GAP_SECONDS = 300
DUPLICATE_NUMBER_COOLDOWN_SECONDS = 120


def sharpen_crop(image):
    blurred = cv2.GaussianBlur(image, (0, 0), sigmaX=3)
    sharpened = cv2.addWeighted(image, 1.8, blurred, -0.8, 0)
    return sharpened


# ============ YANGI: UZOQDAGI (KICHIK) VAGONLAR UCHUN UPSCALE ============
# G'OYA: poyezdning kamera zonasiga uzoqroq tushgan qismida (masalan
# oxirgi vagonlar) raqam kropi juda kichik (past piksel zichligi) bo'lib
# qoladi -- bu klassifikator uchun aynan RAQAM SHAKLINI (dumaloq/tekis
# vagon farqi emas) tanib olishni qiyinlashtiradi. Bu -- HAR QANDAY
# videoda, HAR QANDAY vagon turida takrorlanadigan UNIVERSAL muammo.
#
# YECHIM: agar crop balandligi biror chegaradan past bo'lsa, klassifikatorga
# yuborishdan OLDIN uni kattalashtiramiz (bicubic interpolyatsiya bilan) --
# bu kichik matnni aniqlashda YOLO kabi modellar uchun keng tarqalgan va
# samarali usul.
CROP_MIN_HEIGHT_FOR_UPSCALE = 70   # shundan past balandlikdagi crop kattalashtiriladi
CROP_UPSCALE_FACTOR = 2.2          # necha barobar kattalashtirish
# =====================================================================


def maybe_upscale_crop(crop):
    """Kichik (uzoqdagi vagon) croplarni klassifikatordan oldin kattalashtiradi.
    Qaytaradi: (yangi_crop, qo'llanilgan_koeffitsient)."""
    h = crop.shape[0]
    if h > 0 and h < CROP_MIN_HEIGHT_FOR_UPSCALE:
        new_crop = cv2.resize(crop, None, fx=CROP_UPSCALE_FACTOR, fy=CROP_UPSCALE_FACTOR,
                               interpolation=cv2.INTER_CUBIC)
        return new_crop, CROP_UPSCALE_FACTOR
    return crop, 1.0


# ============ YANGI: HAR BIR VAGON UCHUN BIRLASHTIRILGAN RASM ============
# ODDIY 2 QATOR, IKKALASI HAM BIR XIL KENGLIK/BALANDLIKDA:
#
#   ┌──────────────────────┐
#   │      50889386        │   <- 1-QATOR: MODEL ANIQLAGAN raqam --
#   │   (model natijasi)    │      aniq, katta matn sifatida chiziladi
#   └──────────────────────┘       (checksum bilan tasdiqlangan, TO'LIQ
#                                   oxirgi natija -- FOTO EMAS, balki
#                                   model qaror qilgan raqamning o'zi,
#                                   shuning uchun pastdagi xira fotoga
#                                   o'xshab qolib "bir xil" ko'rinmaydi)
#   ┌──────────────────────┐
#   │      50889385        │   <- 2-QATOR: vagondagi ASL raqam --
#   │      (kamera surati)  │      kamera kropi, TO'LIQ, o'zgarishsiz
#   └──────────────────────┘
#
# Video saqlashning o'rniga -- har bir vagondan BITTA eng yaxshi (eng
# yuqori ishonchli) freymning shu ikki qator birlashgan rasmi saqlanadi.
def combine_wagon_image(number_text, raw_view_crop,
                         max_width=COMBINED_IMAGE_MAX_WIDTH, min_width=400):
    """
    number_text    -- model TO'LIQ OXIRGI natija sifatida aniqlagan raqam
                       (checksum bilan tasdiqlangan matn, masalan "50889386")
                       -- 1-QATORGA aniq, katta harflar bilan chiziladi
    raw_view_crop  -- freymdan olingan, vagondagi ASL (xom) raqam hududi
                       kropi -- TO'LIQ, o'zgarishsiz -- 2-QATORGA joylanadi

    Ikkalasi BIR XIL kenglik/balandlikda, ustma-ust (1-qator: model,
    2-qator: asl) joylashtiriladi.
    """
    def resize_to_width(img, target_w):
        h, w = img.shape[:2]
        if w <= 0 or h <= 0:
            return img
        scale = target_w / w
        new_h = max(1, int(round(h * scale)))
        interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
        return cv2.resize(img, (target_w, new_h), interpolation=interp)

    raw_view_crop = raw_view_crop.copy()

    target_w = min(max_width, max(raw_view_crop.shape[1], min_width))
    bottom = resize_to_width(raw_view_crop, target_w)
    top_h = max(60, bottom.shape[0])

    # 1-QATOR -- model aniqlagan raqam, oq fonda qora matn sifatida chiziladi
    top = np.full((top_h, target_w, 3), 255, dtype=np.uint8)
    if number_text:
        base_scale = 1.0
        base_thickness = 2
        (bw, bh), _ = cv2.getTextSize(number_text, cv2.FONT_HERSHEY_DUPLEX, base_scale, base_thickness)
        scale_w = (target_w * 0.90) / bw if bw > 0 else 1.0
        scale_h = (top_h * 0.65) / bh if bh > 0 else 1.0
        font_scale = max(0.4, min(scale_w, scale_h))
        thickness = max(2, int(round(font_scale * 1.8)))
        (tw, th), baseline = cv2.getTextSize(number_text, cv2.FONT_HERSHEY_DUPLEX, font_scale, thickness)
        tx = max(0, (target_w - tw) // 2)
        ty = (top_h + th) // 2
        cv2.putText(top, number_text, (tx, ty), cv2.FONT_HERSHEY_DUPLEX,
                    font_scale, (0, 0, 0), thickness, cv2.LINE_AA)

    divider = np.full((4, target_w, 3), 255, dtype=np.uint8)
    combined = np.vstack([top, divider, bottom])

    border = 2
    combined = cv2.copyMakeBorder(combined, border, border, border, border,
                                   cv2.BORDER_CONSTANT, value=(120, 120, 120))
    return combined
# =====================================================================


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


def repair_number(detected_digits, box_x1=None, box_x2=None):
    detected_digits.sort(key=lambda x: x[0])

    if len(detected_digits) == 7:
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


def detect_digits_in_crop(classifier, crop_img, x_offset, y_offset, box_center_x, track_id=None, scale_factor=1.0):
    """
    y_offset -- crop qaysi GLOBAL (freym) Y koordinatasidan boshlanishi (y1_pad).
    digit_y_center GLOBAL koordinatada qaytariladi.

    scale_factor -- YANGI: agar crop klassifikatorga yuborishdan oldin
    kattalashtirilgan (upscale qilingan) bo'lsa, bu shu koeffitsient
    (masalan 2.0). Klassifikator natijalari KATTALASHTIRILGAN fazoda
    qaytadi, shuning uchun ularni asl (frame) koordinatasiga qaytarish
    uchun shu songa bo'lamiz.
    """
    results_v8 = classifier.predict(crop_img, conf=DIGIT_CONF, iou=0.45, verbose=False)
    predictions = results_v8[0].boxes.data.cpu().numpy()
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


class TrainSessionManager:
    def __init__(self):
        self.session_start = None
        self.wagons = []
        self.last_number_time = {}
        self.last_event_time = None
        self.last_accept_time = None  # YANGI: faqat MUVAFFAQIYATLI qo'shilgan oxirgi vaqt

    def add_wagon(self, number_str, rel_y=None, image=None):
        if number_str in KNOWN_FALSE_POSITIVE_NUMBERS:
            print(f"       ↳ [BLOCKLIST-SKIP] {number_str} -- ma'lum lokomotiv/begona yozuv, hisoblanmadi")
            self.last_event_time = datetime.datetime.now()
            return False

        now = datetime.datetime.now()
        last_time = self.last_number_time.get(number_str)
        if last_time is not None:
            elapsed = (now - last_time).total_seconds()
            if elapsed < DUPLICATE_NUMBER_COOLDOWN_SECONDS:
                print(f"       ↳ [SKIP] {number_str} -- {elapsed:.0f}s oldin allaqachon yozilgan, takror hisoblanmadi")
                self.last_event_time = now
                return False
        if self.session_start is None:
            self.session_start = now
            print(f"\n🚂 YANGI POYEZD SESSIYASI BOSHLANDI: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        # YANGI: har bir vagon endi (raqam, vaqt, pozitsiya, RASM) sifatida saqlanadi
        self.wagons.append((number_str, now, rel_y, image))
        self.last_number_time[number_str] = now
        self.last_event_time = now
        self.last_accept_time = now
        return True

    def should_close(self):
        if self.session_start is None or self.last_event_time is None:
            return False
        elapsed = (datetime.datetime.now() - self.last_event_time).total_seconds()
        return elapsed > TRAIN_SESSION_GAP_SECONDS

    def close(self):
        if self.session_start is None or not self.wagons:
            self._reset()
            return
        start_dt = self.session_start
        end_dt = self.wagons[-1][1]

        final_wagons = list(self.wagons)
        removed_as_outlier = []

        # ============ YANGI: POZITSIYA-OUTLIER FILTRI (rangga bog'liq emas) ============
        if ENABLE_POSITION_OUTLIER_FILTER:
            wagons_with_pos = [w for w in self.wagons if w[2] is not None]
            if len(wagons_with_pos) >= MIN_WAGONS_FOR_POSITION_MEDIAN:
                rel_ys = sorted(w[2] for w in wagons_with_pos)
                n = len(rel_ys)
                median_rel_y = rel_ys[n // 2] if n % 2 == 1 else (rel_ys[n // 2 - 1] + rel_ys[n // 2]) / 2
                kept = []
                for w in self.wagons:
                    number_str, ts, rel_y, image = w
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
        # =====================================================================

        os.makedirs(TRAINS_OUTPUT_DIR, exist_ok=True)
        date_str = start_dt.strftime('%Y.%m.%d')
        filename = f"{date_str}_barcha_natijalar.txt"
        filepath = os.path.join(TRAINS_OUTPUT_DIR, filename)
        start_time_str = start_dt.strftime('%H.%M.%S')
        end_time_str = end_dt.strftime('%H.%M.%S')
        train_number = 1
        if os.path.exists(filepath):
            existing_content = open(filepath, encoding='utf-8').read()
            train_number = existing_content.count("-POYEZD") + 1
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write("\n" + "=" * 60 + "\n")
            f.write(f"{train_number}-POYEZD\n")
            f.write(f"Video manba          : {VIDEO_SOURCE}\n")
            f.write(f"Poyezd kelgan vaqt    : {start_dt.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Poyezd ketgan vaqt    : {end_dt.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Oraliq                : {start_time_str} - {end_time_str}\n")
            f.write(f"Jami vagonlar (barchasi VALID) : {len(final_wagons)}\n")
            if removed_as_outlier:
                f.write(f"Pozitsiya-outlier (chetga chiqarilgan): {len(removed_as_outlier)}\n")
            f.write("-" * 60 + "\n")
            for i, (number, ts, rel_y, image) in enumerate(final_wagons, 1):
                f.write(f"{i:>3}) {number}   [VALID]   {ts.strftime('%H:%M:%S')}\n")
            if removed_as_outlier:
                f.write("-" * 60 + "\n")
                f.write("Chetga chiqarilgan (ehtimol begona yozuv, pozitsiya mos kelmadi):\n")
                for number, ts, rel_y, med in removed_as_outlier:
                    f.write(f"     {number}   pozitsiya={rel_y:.2f} (median={med:.2f})   {ts.strftime('%H:%M:%S')}\n")
        print(f"\n💾 Poyezd hisoboti qo'shildi (append): {filepath}")
        print(f"   Jami {len(final_wagons)} ta vagon (barchasi VALID)\n")

        # ============ YANGI: HAR BIR VAGON UCHUN RASMLARNI SAQLASH ============
        # Poyezd uchun ALOHIDA papka ("<sana>_<N>-poyezd") ochiladi va ichiga
        # HAR BIR vagonning birlashtirilgan (raqam+vagon) rasmi alohida
        # fayl sifatida yoziladi -- masalan 50 vagon bo'lsa, shu papkada 50 ta rasm.
        if SAVE_WAGON_IMAGES and final_wagons:
            images_root = os.path.join(TRAINS_OUTPUT_DIR, WAGON_IMAGES_SUBDIR)
            train_folder_name = f"{date_str}_{train_number}-poyezd"
            train_folder = os.path.join(images_root, train_folder_name)
            os.makedirs(train_folder, exist_ok=True)
            saved_count = 0
            for i, (number, ts, rel_y, image) in enumerate(final_wagons, 1):
                if image is None or image.size == 0:
                    continue
                img_filename = f"{i:03d}_{number}_{ts.strftime('%H.%M.%S')}.jpg"
                cv2.imwrite(os.path.join(train_folder, img_filename), image)
                saved_count += 1
            print(f"🖼️  Vagon rasmlari saqlandi: {train_folder} ({saved_count}/{len(final_wagons)} ta)\n")
        # =====================================================================

        self._reset()

    def _reset(self):
        self.session_start = None
        self.wagons = []
        self.last_number_time = {}
        self.last_event_time = None
        self.last_accept_time = None


train_session = TrainSessionManager()


def process_finished_track(track_id, scores_dict, candidate_frames, position_votes, position_vote_frames,
                            lifespan, stats, any_digit_seen, rel_positions, session_ordinal, best_image=None):
    if lifespan < MIN_FRAMES_TO_SURVIVE:
        return

    if session_ordinal is not None and session_ordinal < IGNORE_FIRST_N_TRACKS_PER_SESSION:
        # [LOCOMOTIVE-SKIP] konsolga chiqarilmaydi (foydalanuvchi so'rovi bo'yicha) -- lekin
        # filtrlash mantig'i (lokomotivni hisoblamaslik) o'zgarishsiz ishlayveradi
        return

    winner = None
    source_tag = ""

    # ============ YANGI (BU SESSIYADA TUZATILDI): BITTA FREYMGA ISHONISH
    # ENDI BUTUNLAY OLIB TASHLANDI ============
    # SABAB: sistern (tank) vagonlarda (yaltiroq/egri sirt) klassifikator
    # kamdan-kam holda bitta freymda barcha 8 ta raqamni "toza" ko'radi --
    # shuning uchun pozitsiya-ovoz ishga tushmay, zaifroq zaxira yo'lga
    # ("repair-fallback") tushib qolardi, u esa bitta yuqori-ishonchli
    # freymni ham darhol qabul qilardi. Aynan shu yerda 1-2 ta raqam xato
    # o'qilgan-lekin-checksum-mos natijalar kirib qolgan edi.
    #
    # YANGI QOIDA: ENDI IKKALA yo'l (pozitsiya-ovoz HAM, repair-fallback HAM)
    # bir xil qattiqlikda -- albatta kamida 2 marta (turli, mustaqil
    # freymlarda) AYNAN BIR XIL natija chiqishi shart. Bitta freym, qanchalik
    # yuqori ishonchli bo'lmasin, ENDI YETARLI EMAS.
    if position_vote_frames >= POSITION_VOTE_MIN_FRAMES_STRONG:
        voted_number, avg_agreement = build_voted_number(position_votes)
        if voted_number and validate_wagon_number(voted_number):
            winner = voted_number
            source_tag = f" [POSITION-VOTE x{position_vote_frames}, kelishuv={avg_agreement:.0%}]"

    if winner is None:
        if not scores_dict:
            # "raqami aniqlanmadi" ogohlantirishi konsolga chiqarilmaydi
            # (foydalanuvchi so'rovi bo'yicha) -- shunchaki bu vagon o'tkazib yuboriladi
            return

        # FAQAT checksum bo'yicha VALID nomzodlar orasidan, VA faqat kamida
        # 2 marta AYNAN BIR XIL chiqqanlaridan tanlanadi.
        valid_repeated_candidates = {
            num: sc for num, sc in scores_dict.items()
            if validate_wagon_number(num) and candidate_frames.get(num, 0) >= FAST_MIN_READ_FRAMES
        }
        if not valid_repeated_candidates:
            # "raqami aniqlanmadi" ogohlantirishi konsolga chiqarilmaydi
            return
            return

        sorted_candidates = sorted(valid_repeated_candidates.items(), key=lambda item: item[1], reverse=True)
        winner, _ = sorted_candidates[0]
        source_tag = f" [repair-fallback x{candidate_frames[winner]}]"

    if winner is None:
        return

    # ============ YANGI: FRAGMENTATSIYA (JUDA TEZ KETMA-KET) TEKSHIRUVI ============
    # Agar bu vagon oldingi qabul qilingan vagondan JUDA TEZ (real vaqtda
    # MIN_INTER_WAGON_SECONDS dan kamroq) kelayotgan bo'lsa -- bu fizik
    # jihatdan shubhali (haqiqiy vagon shuncha tez o'tolmaydi). Bunday holda
    # faqat ENG ISHONCHLI daraja (pozitsiya-ovoz, kamida
    # FRAGMENTATION_STRONG_VOTE_MIN marta) qabul qilinadi -- aks holda
    # butunlay rad etiladi (bu ehtimol bitta jismoniy vagonning davomi).
    if train_session.last_accept_time is not None:
        elapsed_since_last = (datetime.datetime.now() - train_session.last_accept_time).total_seconds()
        if elapsed_since_last < MIN_INTER_WAGON_SECONDS:
            is_strong_position_vote = position_vote_frames >= FRAGMENTATION_STRONG_VOTE_MIN
            if not is_strong_position_vote:
                print(f"       ↳ [FRAGMENTATION-REJECT] ID:{track_id} | {winner} -- oldingi vagondan "
                      f"{elapsed_since_last:.1f}s dan keyin keldi (juda tez, ehtimol trek bo'linib ketgan "
                      f"bitta vagon) -- yetarli kuchli tasdiq yo'q, rad etildi")
                return
    # =====================================================================

    median_rel_y = None
    if rel_positions:
        median_rel_y = sorted(rel_positions)[len(rel_positions) // 2]

    was_added = train_session.add_wagon(winner, rel_y=median_rel_y, image=best_image)

    if was_added:
        print(f"\n[EVENT] 🚆 Wagon ID:{track_id} | Number: {winner} | ✅ VALID{source_tag}")
        stats['read_success'] += 1
        stats['read_valid'] += 1
        print("-" * 50)


def run_realtime():
    print("📡 Loading detector model (YOLOv8)...")
    try:
        detector = YOLO(VAGON_NUMBER_DETECTION)
    except Exception as e:
        print(f"Error loading detector: {e}")
        return

    print("⏳ Loading digit detector (YOLOv8)...")
    try:
        classifier = YOLO(VAGON_NUMBER_CLASSIFICATION)
    except Exception as e:
        print(f"Error loading classifier: {e}")
        return

    if isinstance(VIDEO_SOURCE, int):
        print(f"📷 Attempting to open camera...")
        cap = cv2.VideoCapture(VIDEO_SOURCE, cv2.CAP_V4L2)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cap.set(cv2.CAP_PROP_FPS, 10.0)
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

    UI_SCALE_REFERENCE_HEIGHT = 720
    ui_scale = height / UI_SCALE_REFERENCE_HEIGHT
    list_font_scale = max(RECOGNIZED_LIST_FONT_SCALE * ui_scale, MIN_LIST_FONT_SCALE)
    list_line_height = max(MIN_LIST_LINE_HEIGHT, int(RECOGNIZED_LIST_LINE_HEIGHT * ui_scale))
    list_margin_right = max(5, int(RECOGNIZED_LIST_MARGIN_RIGHT * ui_scale))
    list_margin_top = max(10, int(RECOGNIZED_LIST_MARGIN_TOP * ui_scale))
    list_margin_bottom = max(5, int(RECOGNIZED_LIST_MARGIN_BOTTOM * ui_scale))
    list_thickness = max(1, round(ui_scale))
    list_shadow_thickness = list_thickness + 1

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
        FINAL_OUTPUT_PATH = os.path.join(TRAINS_OUTPUT_DIR, f"{timestamp_str}_{base_name}{ext}")
        fourcc_h264 = cv2.VideoWriter_fourcc(*'avc1')
        out = cv2.VideoWriter(FINAL_OUTPUT_PATH, fourcc_h264, fps, (save_width, save_height))
        if not out.isOpened():
            print("⚠️  H.264 (avc1) kodek topilmadi, mp4v kodekka qaytilmoqda")
            out = cv2.VideoWriter(FINAL_OUTPUT_PATH, cv2.VideoWriter_fourcc(*'mp4v'), fps, (save_width, save_height))
        else:
            print("✅ H.264 (avc1) kodek bilan saqlanmoqda")
        print(f"🎥 Video shu manzilga saqlanadi: {FINAL_OUTPUT_PATH}")

    frame_center_x = width / 2
    zone_pixel_width = width * ZONE_TOLERANCE
    zone_left = int(frame_center_x - zone_pixel_width)
    zone_right = int(frame_center_x + zone_pixel_width)
    track_scores = defaultdict(lambda: defaultdict(float))
    track_candidate_frames = defaultdict(lambda: defaultdict(int))  # YANGI: {track_id: {number_str: nechta freymda AYNAN shu son chiqdi}}
    track_position_votes = defaultdict(make_position_votes)
    track_position_vote_frames = defaultdict(int)
    track_lifespan = defaultdict(int)
    track_any_digit_seen = defaultdict(bool)
    track_read_frames = defaultdict(int)
    track_rel_positions = defaultdict(list)
    track_session_ordinal = {}
    last_seen_frame = {}
    frame_count = 0

    # YANGI: har bir trek uchun HOZIRGACHA topilgan ENG YAXSHI (eng yuqori
    # ishonchli) freymning birlashtirilgan (raqam+vagon) rasmi
    track_best_conf = defaultdict(float)
    track_best_image = {}

    session_track_counter = [0]

    height_history = deque(maxlen=HEIGHT_HISTORY_MAXLEN)

    seen_stable_ids = set()
    stats = {'read_success': 0, 'read_valid': 0}

    print("🚀 Started. Press 'q' to exit.")
    gui_available = SHOW_WINDOW
    while True:
        success, frame = cap.read()
        if not success:
            print("⚠️ Stream interrupted or camera disconnected.")
            break
        frame_count += 1
        results = detector.track(frame, persist=True, verbose=False, tracker="bytetrack.yaml", conf=WAGON_DETECTOR_CONF)
        result = results[0]
        cv2.line(frame, (zone_left, 0), (zone_left, height), (200, 200, 200), 2)
        cv2.line(frame, (zone_right, 0), (zone_right, height), (200, 200, 200), 2)

        if result.boxes and result.boxes.id is not None:
            track_ids = result.boxes.id.int().cpu().tolist()
            boxes = result.boxes.xyxy.cpu().tolist()

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
                    crop = frame[y1_pad:y2_pad, x1_pad:x2_pad]

                    # ============ YANGI: NOTO'G'RI HUDUD (RAQAM EMAS) FILTRI ============
                    # Detektor bergan HUDUDNING (raqam plastinkasi bo'lishi kerak bo'lgan
                    # joyning) shakli tekshiriladi -- agar bu juda "kvadrat/tor" bo'lsa
                    # (haqiqiy 8 xonali raqamga o'xshamasa), bu freym butunlay
                    # e'tiborga OLINMAYDI -- klassifikatorga yuborilmaydi.
                    box_aspect_ratio = (x2_orig - x1_orig) / max(1, box_h)
                    is_plausible_plate_shape = box_aspect_ratio >= MIN_PLATE_ASPECT_RATIO

                    if crop.size > 0 and is_plausible_plate_shape:
                        crop_upscaled, applied_scale = maybe_upscale_crop(crop)
                        crop_sharp = sharpen_crop(crop_upscaled)

                        detected_digits, any_digit, avg_y_center = detect_digits_in_crop(
                            classifier, crop_sharp, x1_pad, y1_pad, box_center_x, track_id,
                            scale_factor=applied_scale)

                        if any_digit:
                            track_any_digit_seen[track_id] = True

                        added_to_votes = add_position_votes(track_position_votes[track_id], detected_digits)
                        if added_to_votes:
                            track_position_vote_frames[track_id] += 1

                        final_number_str = None
                        is_repaired = False
                        avg_conf = 0.0

                        if detected_digits:
                            final_number_str, is_repaired, log = repair_number(
                                detected_digits, box_x1=x1_pad, box_x2=x2_pad)
                            avg_conf = sum([d[2] for d in detected_digits]) / len(detected_digits)

                            if len(final_number_str) == 8 and avg_conf > 0.5:
                                is_valid = validate_wagon_number(final_number_str)

                                if is_valid:
                                    track_read_frames[track_id] += 1
                                    track_candidate_frames[track_id][final_number_str] += 1
                                    score_boost = 3.0 * REPAIRED_SCORE_MULTIPLIER if is_repaired else 3.0
                                    text_color = (0, 255, 0)
                                    track_scores[track_id][final_number_str] += (avg_conf * score_boost)

                                    # YANGI: vagon balandligiga nisbatan pozitsiyani yozib qo'yamiz
                                    wagon_box_h = max(1, y2_orig - y1_orig)
                                    if avg_y_center is not None:
                                        rel_y = (avg_y_center - y1_orig) / wagon_box_h
                                        track_rel_positions[track_id].append(rel_y)

                                    # ============ YANGI: BU VAGON UCHUN ENG YAXSHI RASMNI SAQLASH ============
                                    # Video o'rniga -- shu treknnig HOZIRGACHA ko'rgan eng yuqori
                                    # ishonchli freymidan, ikki qatorli rasm saqlanadi:
                                    # 1-QATOR: model ANIQLAGAN raqamning o'zi (matn sifatida --
                                    #          checksum bilan tasdiqlangan, TO'LIQ oxirgi natija)
                                    # 2-QATOR: vagondagi ASL raqam hududining xom kamera kropi
                                    #
                                    # QO'SHIMCHA HIMOYA: agar final_number_str ichida "?" yoki
                                    # boshqa raqam bo'lmagan belgi bo'lsa (masalan klassifikator
                                    # noaniq/shubhali belgi chiqarsa) -- BU O'QISH RASM SIFATIDA
                                    # SAQLANMAYDI, chunki u to'liq ishonchli raqam emas.
                                    if (SAVE_WAGON_IMAGES and avg_conf > track_best_conf[track_id]
                                            and final_number_str.isdigit() and len(final_number_str) == 8):
                                        raw_view_img = crop  # xom, ishlov berilmagan asl hudud
                                        if raw_view_img.size > 0:
                                            track_best_conf[track_id] = avg_conf
                                            # MUHIM: "°" belgisi OpenCV'ning putText funksiyasida
                                            # "??" bo'lib buzilib chiqadi (faqat ASCII qo'llab-
                                            # quvvatlanadi) -- shuning uchun ASCII "*" ishlatiladi
                                            display_number = final_number_str + ("*" if is_repaired else "")
                                            track_best_image[track_id] = combine_wagon_image(
                                                display_number, raw_view_img)
                                    # =====================================================================

                                    if SHOW_LIVE_LABEL:
                                        label = final_number_str
                                        if is_repaired: label += "*"  # "°" emas -- OpenCV buni "??" qilib buzadi
                                        font_scale = 1.3
                                        thickness = 3
                                        padding = 12
                                        border_thickness = 2
                                        (text_w, text_h), baseline = cv2.getTextSize(
                                            label, cv2.FONT_HERSHEY_DUPLEX, font_scale, thickness)
                                        text_x = x1_orig
                                        text_y = max(text_h + padding, y1_orig - 20)
                                        box_x1 = text_x - padding
                                        box_y1 = text_y - text_h - padding
                                        box_x2 = text_x + text_w + padding
                                        box_y2 = text_y + baseline + padding // 2
                                        cv2.rectangle(frame, (box_x1, box_y1), (box_x2, box_y2), (0, 0, 0), -1)
                                        cv2.rectangle(frame, (box_x1, box_y1), (box_x2, box_y2), text_color, border_thickness)
                                        cv2.putText(frame, label, (text_x, text_y),
                                                    cv2.FONT_HERSHEY_DUPLEX, font_scale, text_color, thickness, cv2.LINE_AA)
                                # is_valid=False bo'lsa -- HECH NARSA qilinmaydi (eslab qolinmaydi)

                if is_stable:
                    cv2.rectangle(frame, (x1_orig, y1_orig), (x2_orig, y2_orig), color, 3)
                    cv2.putText(frame, f"ID:{track_id}",
                                (x1_orig, y1_orig - 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        dead_tracks = []
        for tid, last_frame in last_seen_frame.items():
            if frame_count - last_frame > FRAMES_TO_FORGET:
                process_finished_track(tid, track_scores.get(tid), track_candidate_frames.get(tid, {}),
                                        track_position_votes.get(tid),
                                        track_position_vote_frames.get(tid, 0),
                                        track_lifespan.get(tid), stats,
                                        track_any_digit_seen.get(tid, False),
                                        track_rel_positions.get(tid), track_session_ordinal.get(tid),
                                        best_image=track_best_image.get(tid))
                dead_tracks.append(tid)

        for tid in dead_tracks:
            if tid in last_seen_frame: del last_seen_frame[tid]
            if tid in track_scores: del track_scores[tid]
            if tid in track_candidate_frames: del track_candidate_frames[tid]
            if tid in track_rel_positions: del track_rel_positions[tid]
            if tid in track_position_votes: del track_position_votes[tid]
            if tid in track_position_vote_frames: del track_position_vote_frames[tid]
            if tid in track_lifespan: del track_lifespan[tid]
            if tid in track_any_digit_seen: del track_any_digit_seen[tid]
            if tid in track_read_frames: del track_read_frames[tid]
            if tid in track_session_ordinal: del track_session_ordinal[tid]
            if tid in track_best_conf: del track_best_conf[tid]
            if tid in track_best_image: del track_best_image[tid]

        if train_session.should_close():
            train_session.close()
            height_history.clear()
            session_track_counter[0] = 0

        if SHOW_RECOGNIZED_LIST and train_session.wagons:
            available_height = height - list_margin_top - list_margin_bottom
            max_rows_that_fit = max(1, available_height // list_line_height)
            visible_wagons = train_session.wagons[-max_rows_that_fit:]
            for idx, (number, ts, rel_y, image) in enumerate(visible_wagons):
                list_color = (0, 255, 0)
                (tw, th), _ = cv2.getTextSize(
                    number, cv2.FONT_HERSHEY_SIMPLEX, list_font_scale, list_thickness)
                list_x = width - tw - list_margin_right
                list_y = list_margin_top + idx * list_line_height
                cv2.putText(frame, number, (list_x + 1, list_y + 1),
                            cv2.FONT_HERSHEY_SIMPLEX, list_font_scale, (0, 0, 0), list_shadow_thickness, cv2.LINE_AA)
                cv2.putText(frame, number, (list_x, list_y),
                            cv2.FONT_HERSHEY_SIMPLEX, list_font_scale, list_color, list_thickness, cv2.LINE_AA)

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
                cv2.imshow("Wagon Number Recognition RealTime", display_frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
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
        process_finished_track(tid, track_scores.get(tid), track_candidate_frames.get(tid, {}),
                                track_position_votes.get(tid),
                                track_position_vote_frames.get(tid, 0),
                                track_lifespan.get(tid), stats,
                                track_any_digit_seen.get(tid, False),
                                track_rel_positions.get(tid), track_session_ordinal.get(tid),
                                best_image=track_best_image.get(tid))

    train_session.close()

    if out: out.release()
    cap.release()
    if gui_available:
        cv2.destroyAllWindows()

    print("\n" + "=" * 50)
    print("📊 YAKUNIY HISOBOT")
    print(f"✅ Checksum bo'yicha to'g'ri (VALID) chiqqan vagonlar: {stats['read_valid']}")
    print(f"📁 Barcha poyezd fayllari: {TRAINS_OUTPUT_DIR}")
    if SAVE_WAGON_IMAGES:
        print(f"🖼️  Vagon rasmlari: {os.path.join(TRAINS_OUTPUT_DIR, WAGON_IMAGES_SUBDIR)}")
    print("=" * 50)
    print("🛑 Work completed.")


if __name__ == "__main__":
    run_realtime()












