import cv2 # Video o'qish, kadrlarni ko'rsatish, rasm ustiga chizish (box, matn) uchun
import os # Fayl tizimi bilan ishlash uchun
import numpy as np
import torch # YOLOv8 modelini yuklash va ishlatish uchun
import pathlib # Fayl yo'llarini platformaga mos tarzda boshqarish uchun
import datetime
from ultralytics import YOLO
from collections import defaultdict # Lug'at (dictionary) — kalit mavjud bo'lmasa xato bermay, avtomatik boshlang'ich qiymat beradi (masalan 0
import warnings # Keraksiz ogohlantirish xabarlarini o'chirish uchun
# import time

VIDEO_SOURCE = './test_new3.mp4'

SAVE_RESULT = True
OUTPUT_FILENAME = 'realtime_result.mp4' # agar saqlash yoqilsa, natija shu nom bilan saqlanadi

# Ogohlantirishlarni o'chirish va Windows/Linux moslashtirish
warnings.filterwarnings("ignore", category=FutureWarning)
temp = pathlib.PosixPath
pathlib.WindowsPath = pathlib.PosixPath

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VAGON_NUMBER_DETECTION = 'vndetection.pt'
VAGON_NUMBER_CLASSIFICATION = 'vnclassification.pt'

FINAL_OUTPUT_PATH = os.path.join(BASE_DIR, OUTPUT_FILENAME)

# ============ SOZLAMALAR ============
DIGIT_CONF = 0.45
WAGON_DETECTOR_CONF = 0.5  # YANGI: 1-bosqich detektor uchun ishonch chegarasi.
                             # Bu belgilanmagan bo'lsa, model juda past ishonch
                             # bilan ham (masalan bo'sh devor, konteyner yon
                             # tomoni kabi raqam yo'q joylarda) "box" chizib,
                             # keraksiz kuzatuv (track) boshlab yuboradi.
ZONE_TOLERANCE = 0.12  # 0.22 -> 0.12 ga toraytirildi: faqat markazga juda yaqin
                          # kelgan vagon o'qiladi -- bu orqadagi/qo'shni yo'ldagi
                          # vagonni tasodifan "ushlab qolish" ehtimolini kamaytiradi
CROP_PADDING_RATIO_V = 0.12
CROP_PADDING_RATIO_H = 0.05
CROP_PADDING_MIN = 8
CROP_PADDING_MAX = 40
HEIGHT_OUTLIER_RATIO = 0.55
DIGIT_GAP_RATIO = 1.9
REPAIRED_SCORE_MULTIPLIER = 0.5
MIN_FRAMES_TO_SURVIVE = 8
MIN_CONF_TO_FIX = 0.60
LAST_DIGIT_TRUST_CONF = 0.75
SHOW_LIVE_LABEL = True
FRAMES_TO_FORGET = 45
SHOW_WAGON_COUNTER = True
DEBUG_RAW_DETECTIONS = False

# ============ MOSLASHUVCHAN (ADAPTIVE) MASOFA FILTRI ============
# Qattiq foiz (masalan "frame balandligining 20%i") har xil poyezd/kamera
# masofasida yaxshi ishlamaydi -- bugun yaqinroq turgan poyezd ertaga
# uzoqroq bo'lishi mumkin. Shuning uchun endi chegarani DINAMIK hisoblaymiz:
# shu sessiyada (hozirgi poyezd o'tishi davomida) markaziy zonada ko'rilgan
# barcha box'larning median balandligini kuzatib boramiz. Asosiy yo'ldagi
# vagon deyarli har doim eng ko'p uchraydigan (median) balandlikka yaqin
# bo'ladi; undan sezilarli kichikroq bo'lgan box (masalan ikki barobar
# kichik) -- orqadagi/uzoqdagi boshqa yo'l deb hisoblanadi.
ADAPTIVE_HEIGHT_RATIO = 0.55   # median balandlikning shu nisbatidan kichik box -- rad etiladi
MIN_SAMPLES_FOR_ADAPTIVE = 15  # shuncha namuna to'planguncha, barcha box'lar vaqtincha qabul qilinadi
HEIGHT_HISTORY_MAXLEN = 200    # xotirada saqlanadigan oxirgi balandliklar soni
PRINT_BOX_HEIGHT_DEBUG = False  # sozlash tugadi -- endi konsolni "spam" qilmaslik uchun o'chirilgan
# =====================================================================

# ============ BEGONA/BOSHQA QATORDAGI RAQAMLARNI CHIQARIB TASHLASH ============
# Vagon raqami har doim BITTA gorizontal chiziqda joylashadi. Ba'zan vagon
# tanasida boshqa raqamlar ham bo'ladi (yasalgan yili "1986", vagon turi kodi
# "29" va h.k.) -- bular odatda asosiy raqamdan PASTROQ yoki YUQORIROQ
# joylashgan bo'ladi. Bu filtr Y-koordinata (balandlik bo'yicha joylashuv)
# asosida faqat BITTA qatordagi raqamlarni qoldiradi, boshqa qatordagilarni
# chiqarib tashlaydi.
ROW_Y_TOLERANCE_RATIO = 0.6  # raqam balandligiga nisbatan ruxsat etilgan Y farqi
# =====================================================================

# ============ POYEZD SESSIYASI VA FAYLGA YOZISH ============
TRAINS_OUTPUT_DIR = os.path.join(BASE_DIR, "trains")  # har bir poyezd uchun fayllar shu papkaga yoziladi
TRAIN_SESSION_GAP_SECONDS = 180   # shuncha soniya hech qanday vagon o'qilmasa, poyezd "ketdi" deb hisoblanadi
DUPLICATE_NUMBER_COOLDOWN_SECONDS = 120  # shu vaqt ichida bir xil raqam qayta chiqsa -- takror deb hisoblanib yozilmaydi
# =====================================================================


def filter_height_outliers(detections): # balandligi mos kelmagan raqamlarni chiqarib tashlash
    """
    detections: (x, digit_str, conf, height, y_center) tuplalar.
    Median balandlikdan ko'p farq qiladigan box'lar (zang dog'i, nur ta'siri) chiqariladi.
    """
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
    """
    detections: (x, digit_str, conf, height, y_center) tuplalar.
    Vagon raqami bitta gorizontal chiziqda joylashadi. Boshqa qatorga
    tegishli (masalan pastda joylashgan yasalgan yili) raqamlarni
    median Y-koordinatadan farqiga qarab chiqarib tashlaydi.
    """
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

    return filtered if filtered else detections  # ehtiyot chorasi: hammasi chiqib ketmasin


def cluster_digits_by_gap(detections, target_center_x, gap_ratio=DIGIT_GAP_RATIO):
    """
    detections: (x, digit_str, conf, height, y_center) tuplalar ro'yxati.
    X-koordinata bo'yicha katta bo'shliqlarga qarab guruhlarga ajratadi,
    faqat bitta (asl box markaziga eng yaqin / 8 taga eng yaqin) guruhni tanlaydi.
    """
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

    def cluster_key(c): # eng yaxshi guruhni tanlash uchun kalit (tuple) qaytaradi
        count_penalty = abs(8 - len(c))
        cx = sum(d[0] for d in c) / len(c)
        dist_penalty = abs(cx - target_center_x)
        return (count_penalty, dist_penalty)

    best_cluster = min(clusters, key=cluster_key)

    if DEBUG_RAW_DETECTIONS and len(clusters) > 1:
        dropped = sum(len(c) for c in clusters) - len(best_cluster)
        print(f"[CLUSTER] {len(clusters)} ta guruh topildi, {dropped} ta belgi begona guruh(lar)dan chiqarib tashlandi")

    return best_cluster


def calculate_checksum(number_str_7): # 7 ta raqamli string uchun tekshirish raqamini hisoblaydi
    if len(number_str_7) != 7: return -1
    digits = [int(d) for d in number_str_7]
    weights = [2, 1, 2, 1, 2, 1, 2]
    total_sum = 0
    for d, w in zip(digits, weights):
        res = d * w
        total_sum += (res // 10) + (res % 10)
    next_ten = (total_sum + 9) // 10 * 10
    return next_ten - total_sum


def validate_wagon_number(number_str): # 8 ta raqamli stringni tekshiradi (oxirgi raqam tekshirish raqami bo'lishi kerak)
    if len(number_str) != 8 or not number_str.isdigit(): return False
    target = int(number_str[-1])
    calc = calculate_checksum(number_str[:7])
    return target == calc


def repair_number(detected_digits): # detected_digits: (x, digit_str, conf) tuplari ro'yxati
    detected_digits.sort(key=lambda x: x[0])

    if len(detected_digits) == 7:
        prefix_str = "".join([d[1] for d in detected_digits])
        guessed_last = calculate_checksum(prefix_str)
        if guessed_last != -1:
            candidate = prefix_str + str(guessed_last)
            return candidate, True, f"Completed missing last digit (guessed): {guessed_last}"

    original_str = "".join([d[1] for d in detected_digits])
    if len(original_str) != 8: return original_str, False, "Len!=8"
    if validate_wagon_number(original_str): return original_str, False, "Valid"
    prefix = original_str[:7]
    last_digit_conf = detected_digits[7][2]

    if last_digit_conf < LAST_DIGIT_TRUST_CONF:
        correct_last = calculate_checksum(prefix)
        candidate = prefix + str(correct_last)
        return candidate, True, f"Fixed Last: {original_str[-1]}->{correct_last}"

    min_conf_val = 1.0
    min_conf_idx = -1
    for i in range(7):
        if detected_digits[i][2] < min_conf_val:
            min_conf_val = detected_digits[i][2]
            min_conf_idx = i

    if min_conf_val < MIN_CONF_TO_FIX and min_conf_idx != -1:
        current_tail = int(original_str[-1])
        for d in range(10):
            temp_prefix = list(prefix)
            temp_prefix[min_conf_idx] = str(d)
            temp_str = "".join(temp_prefix)
            if calculate_checksum(temp_str) == current_tail:
                new_full = temp_str + str(current_tail)
                return new_full, True, f"Brute pos {min_conf_idx}: {original_str[min_conf_idx]}->{d}"

    return original_str, False, "No Fix"


# ============ POYEZD SESSIYASINI BOSHQARISH ============
class TrainSessionManager:
    """
    Har bir "poyezd o'tishi" (session) ni boshqaradi:
      - session boshlanish vaqti (birinchi vagon o'qilganda)
      - session davomida o'qilgan barcha vagon raqamlari + har birining REAL vaqti
      - bir xil raqam qisqa vaqt ichida qayta kelsa -- takror deb hisoblab yozmaydi
      - agar uzoq vaqt (TRAIN_SESSION_GAP_SECONDS) hech qanday vagon o'qilmasa
        -- session yopiladi va natija faylga yoziladi
    """

    def __init__(self):
        self.session_start = None
        self.wagons = []  # list of (number_str, datetime, is_valid)
        self.last_number_time = {}  # number_str -> oxirgi marta yozilgan vaqt (dedup uchun)
        self.last_event_time = None  # oxirgi marta har qanday vagon o'qilgan vaqt

    def add_wagon(self, number_str, is_valid): #  yangi vagon qo'shish
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

        self.wagons.append((number_str, now, is_valid))
        self.last_number_time[number_str] = now
        self.last_event_time = now
        return True

    def should_close(self): # sessiyani yopish kerakmi, ya'ni oxirgi vagon o'qilganidan beri TRAIN_SESSION_GAP_SECONDS soniya o'tib ketdimi
        if self.session_start is None or self.last_event_time is None:
            return False
        elapsed = (datetime.datetime.now() - self.last_event_time).total_seconds()
        return elapsed > TRAIN_SESSION_GAP_SECONDS

    def close(self): # sessiyani yopish va natijani faylga yozish
        if self.session_start is None or not self.wagons:
            self._reset()
            return

        start_dt = self.session_start
        end_dt = self.wagons[-1][1]

        os.makedirs(TRAINS_OUTPUT_DIR, exist_ok=True)

        date_str = start_dt.strftime('%Y.%m.%d')
        start_time_str = start_dt.strftime('%H.%M')
        end_time_str = end_dt.strftime('%H.%M')
        filename = f"{date_str}_{start_time_str}-{end_time_str}.txt"
        filepath = os.path.join(TRAINS_OUTPUT_DIR, filename)

        counter = 1
        base_filepath = filepath
        while os.path.exists(filepath):
            name_no_ext = base_filepath[:-4]
            filepath = f"{name_no_ext}_{counter}.txt"
            counter += 1

        valid_count = sum(1 for _, _, v in self.wagons if v)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"Poyezd kelgan vaqt : {start_dt.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Poyezd ketgan vaqt : {end_dt.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Jami vagonlar      : {len(self.wagons)}\n")
            f.write(f"To'g'ri (VALID)     : {valid_count}\n")
            f.write("-" * 50 + "\n")
            for i, (number, ts, is_valid) in enumerate(self.wagons, 1):
                status = "VALID" if is_valid else "INVALID"
                f.write(f"{i:>3}) {number}   [{status}]   {ts.strftime('%H:%M:%S')}\n")

        print(f"\n💾 Poyezd hisoboti saqlandi: {filepath}")
        print(f"   Jami {len(self.wagons)} ta vagon, shundan {valid_count} tasi VALID\n")

        self._reset()

    def _reset(self):
        self.session_start = None
        self.wagons = []
        self.last_number_time = {}
        self.last_event_time = None


train_session = TrainSessionManager()
# =====================================================================


def process_finished_track(track_id, scores_dict, lifespan, stats, any_digit_seen): # track tugagach, uning natijasini qayta ishlash
    if lifespan < MIN_FRAMES_TO_SURVIVE:
        if DEBUG_RAW_DETECTIONS and scores_dict:
            best_guess = sorted(scores_dict.items(), key=lambda item: item[1], reverse=True)[0]
            print(f"[DROPPED] ID:{track_id} | Juda qisqa umr (lifespan={lifespan} < {MIN_FRAMES_TO_SURVIVE}) | "
                  f"Eng yaxshi taxmin edi: {best_guess[0]} (ball={best_guess[1]:.2f})")
        return

    if not scores_dict:
        if not any_digit_seen:
            # Butun umri davomida bitta ham raqam ko'rinmagan -- bu ehtimol
            # 1-bosqich detektorning soxta aniqlashi (bu yerda umuman raqam
            # paneli yo'q, masalan konteyner devori yoki bo'sh joy edi).
            # Bu holatni "xira/o'chgan" deb noto'g'ri atamaslik uchun jim
            # o'tkazib yuboramiz (yoki DEBUG yoqilgan bo'lsa, alohida belgilaymiz).
            if DEBUG_RAW_DETECTIONS:
                print(f"[SKIP-EMPTY] ID:{track_id} | Bu yerda umuman raqam topilmadi -- ehtimol soxta aniqlash")
            return
        # Raqamlar ba'zi kadrlarda ko'ringan, lekin to'liq/ishonchli yig'ilmadi --
        # bu haqiqatan ham xira/noaniq holat
        print(f"⚠️  Vagon (ID:{track_id}) raqami aniqlanmadi — rasm xira yoki raqam o'chib ketgan bo'lishi mumkin")
        return

    sorted_candidates = sorted(scores_dict.items(), key=lambda item: item[1], reverse=True)
    winner, score = sorted_candidates[0]
    is_valid = validate_wagon_number(winner)
    threshold = 5.0
    if lifespan > 40: threshold = 2.0
    if lifespan > 80: threshold = 0.5
    if score < threshold:
        # Raqam taxmin qilindi, lekin ishonch darajasi juda past -- bu ham
        # "aniqlanmadi" holatiga tenglashtiriladi
        print(f"⚠️  Vagon (ID:{track_id}) raqami aniqlanmadi — rasm xira yoki raqam o'chib ketgan bo'lishi mumkin")
        return

    status = "✅ VALID" if is_valid else "❌ INVALID"

    was_added = train_session.add_wagon(winner, is_valid)

    if was_added:
        print(f"\n[EVENT] 🚆 Wagon ID:{track_id} | Number: {winner} | {status}")
        stats['read_success'] += 1
        if is_valid:
            stats['read_valid'] += 1

        if not is_valid and len(sorted_candidates) > 1:
            runner_up, r_score = sorted_candidates[1]
            if validate_wagon_number(runner_up.replace("°", "")) and r_score > (score * 0.1):
                print(f"        ↳ Alternative: {runner_up} ({r_score:.1f}) ✅")
        print("-" * 50)


def run_realtime(): #  Modellarni yuklash
    # Ikkala modelni ham (vndetection.pt — vagon panelini topuvchi, vnclassification.pt — raqamlarni 
    # tanuvchi) navbat bilan yuklaydi. try/except — agar fayl topilmasa yoki buzilgan bo'lsa, 
    # dastur to'satdan qulab tushmasdan, tushunarli xato xabari bilan to'xtaydi (return).
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

    if isinstance(VIDEO_SOURCE, int): #  Video/kamera manbasini ochish
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

    out = None
    if SAVE_RESULT: out = cv2.VideoWriter(FINAL_OUTPUT_PATH, cv2.VideoWriter_fourcc(*'mp4v'), fps, (width, height))
    frame_center_x = width / 2
    zone_pixel_width = width * ZONE_TOLERANCE
    zone_left = int(frame_center_x - zone_pixel_width)
    zone_right = int(frame_center_x + zone_pixel_width)
    track_scores = defaultdict(lambda: defaultdict(float))
    track_lifespan = defaultdict(int)
    track_any_digit_seen = defaultdict(bool)  # YANGI: shu track umrida hech bo'lmasa bitta
                                                # raqam ko'ringan-ko'rinmaganini eslab qoladi
    last_seen_frame = {}
    frame_count = 0

    # markaziy zonada ko'rilgan box balandliklarining tarixi (adaptive filtr uchun)
    from collections import deque
    height_history = deque(maxlen=HEIGHT_HISTORY_MAXLEN)

    seen_stable_ids = set()
    stats = {'read_success': 0, 'read_valid': 0}

    print("🚀 Started. Press 'q' to exit.")
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
                is_stable = track_lifespan[track_id] > 5

                if is_stable and track_id not in seen_stable_ids:
                    seen_stable_ids.add(track_id)

                is_in_x_zone = zone_left < box_center_x < zone_right

                # moslashuvchan (adaptive) masofa filtri.
                # Avval zonadagi box balandligini tarixga qo'shamiz, keyin
                # shu tarixning medianiga nisbatan qaror qabul qilamiz.
                is_main_track = True  # yetarli namuna yig'ilmaguncha, hammasi qabul qilinadi
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

                if PRINT_BOX_HEIGHT_DEBUG and track_lifespan[track_id] % 20 == 0:
                    med_str = f"{median_h_debug:.0f}" if median_h_debug is not None else "yig'ilmoqda"
                    print(f"[DEBUG-HEIGHT] ID:{track_id} | box_h={box_h} | median={med_str} "
                          f"| is_main_track={is_main_track} | in_x_zone={is_in_x_zone}")

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

                    if crop.size > 0:
                        results_v8 = classifier.predict(crop, conf=DIGIT_CONF, iou=0.45, verbose=False)
                        predictions = results_v8[0].boxes.data.cpu().numpy()
                        raw_detections = []

                        for pred in predictions:
                            dx1, dy1, dx2, dy2, d_conf, d_cls = pred
                            class_id = int(d_cls)

                            if hasattr(classifier, 'names'):
                                names = classifier.names
                                digit_str = names[class_id] if isinstance(names, list) else names.get(class_id, str(class_id))
                            else:
                                digit_str = str(class_id)
                            digit_height = float(dy2 - dy1)
                            digit_y_center = float((dy1 + dy2) / 2)
                            raw_detections.append((int(x1_pad + dx1), digit_str, float(d_conf), digit_height, digit_y_center))

                        if raw_detections:
                            track_any_digit_seen[track_id] = True

                        height_filtered = filter_height_outliers(raw_detections)
                        row_filtered = filter_same_row(height_filtered)
                        detected_full = cluster_digits_by_gap(row_filtered, box_center_x)
                        detected_digits = [(x, s, c) for (x, s, c, h, y) in detected_full]

                        if DEBUG_RAW_DETECTIONS and len(raw_detections) != len(detected_full):
                            removed = len(raw_detections) - len(detected_full)
                            print(f"[FILTER] ID:{track_id} | {removed} ta begona/fantom box chiqarib tashlandi")

                        if detected_digits:
                            if DEBUG_RAW_DETECTIONS:
                                raw_sorted = sorted(detected_digits, key=lambda x: x[0])
                                raw_str = "".join([d[1] for d in raw_sorted])
                                raw_confs = ", ".join([f"{d[1]}:{d[2]:.2f}" for d in raw_sorted])
                                print(f"[RAW] ID:{track_id} | {len(detected_digits)} ta raqam | "
                                      f"Ketma-ket: {raw_str} | Har biri: {raw_confs}")

                            final_number_str, is_repaired, log = repair_number(detected_digits)
                            avg_conf = sum([d[2] for d in detected_digits]) / len(detected_digits)

                            if DEBUG_RAW_DETECTIONS and is_repaired:
                                print(f"       ↳ [REPAIR] {log}")

                            if len(final_number_str) == 8 and avg_conf > 0.5:
                                is_valid = validate_wagon_number(final_number_str)

                                if is_valid:
                                    score_boost = 3.0 * REPAIRED_SCORE_MULTIPLIER if is_repaired else 3.0
                                    text_color = (0, 255, 0)
                                else:
                                    score_boost = 0.5
                                    text_color = (0, 0, 255)

                                track_scores[track_id][final_number_str] += (avg_conf * score_boost)
                                if SHOW_LIVE_LABEL:
                                    label = final_number_str
                                    if is_repaired: label += "°"
                                    cv2.putText(frame, label, (x1_orig, y1_orig - 10),
                                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, text_color, 2)

                if is_stable:
                    cv2.rectangle(frame, (x1_orig, y1_orig), (x2_orig, y2_orig), color, 3)
                    cv2.putText(frame, f"ID:{track_id}",
                                (x1_orig, y1_orig - 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        dead_tracks = []
        for tid, last_frame in last_seen_frame.items():
            if frame_count - last_frame > FRAMES_TO_FORGET:
                process_finished_track(tid, track_scores.get(tid), track_lifespan.get(tid), stats,
                                        track_any_digit_seen.get(tid, False))
                dead_tracks.append(tid)

        for tid in dead_tracks:
            if tid in last_seen_frame: del last_seen_frame[tid]
            if tid in track_scores: del track_scores[tid]
            if tid in track_lifespan: del track_lifespan[tid]
            if tid in track_any_digit_seen: del track_any_digit_seen[tid]

        if train_session.should_close():
            train_session.close()
            height_history.clear()  # yangi poyezd uchun balandlik tarixi qaytadan boshlanadi

        if SHOW_WAGON_COUNTER:
            counter_text = f"Wagons counted: {len(seen_stable_ids)}"
            cv2.putText(frame, counter_text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX,
                        1.0, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(frame, counter_text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX,
                        1.0, (0, 0, 0), 1, cv2.LINE_AA)

        display_frame = frame
        if width > 1920: display_frame = cv2.resize(frame, (1280, 720))
        cv2.imshow("Wagon Number Recognition RealTime", display_frame)
        if out: out.write(frame)
        if cv2.waitKey(1) & 0xFF == ord('q'): break

    for tid in list(last_seen_frame.keys()):
        process_finished_track(tid, track_scores.get(tid), track_lifespan.get(tid), stats,
                                track_any_digit_seen.get(tid, False))

    train_session.close()

    if out: out.release()
    cap.release()
    cv2.destroyAllWindows()

    print("\n" + "=" * 50)
    print("📊 YAKUNIY HISOBOT")
    print(f"🔢 Raqami muvaffaqiyatli o'qilgan vagonlar: {stats['read_success']}")
    print(f"✅ Raqami checksum bo'yicha to'g'ri (VALID) chiqqan vagonlar: {stats['read_valid']}")
    print(f"📁 Barcha poyezd fayllari: {TRAINS_OUTPUT_DIR}")
    print("=" * 50)
    print("🛑 Work completed.")


if __name__ == "__main__":
    run_realtime()




# Yuk vagonlari (yuk poyezdlari)
# Bularning barchasi 8 xonali, va biz allaqachon bilgan tizim bo'yicha:

# 1-xona — vagon turi: 2=yopiq, 4=platforma, 6=yarim vagon, 7=sisterna, 8=izotermik, 3/9=boshqa
# 8-xona — nazorat raqami (checksum), bizning kodimizdagi formula bilan bir xil






