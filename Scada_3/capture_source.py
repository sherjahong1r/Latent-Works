"""
capture_source.py — SCADA ekranidan kadr olish manbalari.

capture_pipeline.py faqat shu yerdagi `open_source()` ni chaqiradi va
qaytgan obyektning `grab(path)` usulini har siklda ishlatadi. Manba
qanday ishlashini (brauzer, kamera, oyna) quvurning qolgan qismi bilmaydi.

CAPTURE_MODE (.env):
  url    — SCADA veb-sahifasi Playwright brauzerida doimiy ochiq turadi.
  camera — boshqa monitordagi dashboard kamera orqali suratga olinadi.
  window — SCADA Windows dasturining oynasi (PrintWindow).
  screen — shu kompyuterning butun ekrani.

KAMERA REJIMI HAQIDA:
  Kamera kadrida ekrandan tashqari stol, devor, monitor tagligi ham
  bo'ladi va ekran qiya ko'rinadi. AI'ga faqat ekranning o'zi, to'g'ri
  to'rtburchak qilib yuborilishi kerak — aks holda piksellar bekorga
  ketadi va qiyshiq yozuvlar xato o'qiladi. Buning uchun ekranning 4
  burchagi BIR MARTA belgilanadi (`py camera_calibrate.py`) va
  camera_calibration.json ga yoziladi. Kamera joyi o'zgarmasa, qayta
  kalibrlash kerak emas. Kalibrlash bo'lmasa, butun kadr ishlatiladi.
"""

import json
import os
import time
from pathlib import Path

from PIL import Image

from config import (
    CAPTURE_MODE,
    SCADA_URL,
    SCADA_WINDOW_TITLE,
    CAMERA_INDEX,
    CAMERA_WIDTH,
    CAMERA_HEIGHT,
    CAMERA_CALIBRATION_FILE,
    CAMERA_WARMUP_FRAMES,
)


class CaptureError(RuntimeError):
    """Kadr olinmadi (manba ishlamayapti yoki kadr yaroqsiz)."""


# ───────────────────────────── URL (brauzer) ─────────────────────────────
class UrlSource:
    def __init__(self):
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch()
        self._page = self._browser.new_page(viewport={"width": 1920, "height": 1080})
        self._page.goto(SCADA_URL, timeout=45000, wait_until="domcontentloaded")
        try:
            self._page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        print(f"[CAPTURE] Brauzer sahifasi ochildi: {SCADA_URL}")

    def grab(self, path: str) -> str:
        self._page.screenshot(path=path)
        return path

    def close(self):
        try:
            self._browser.close()
        finally:
            self._pw.stop()


# ───────────────────────────── KAMERA ────────────────────────────────────
def load_calibration(path: str = CAMERA_CALIBRATION_FILE) -> dict | None:
    """{"corners": [[x,y] x4], "frame_size": [w,h]} yoki None."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if len(data.get("corners", [])) == 4:
            return data
    except (OSError, ValueError):
        pass
    print(f"[CAPTURE][OGOHLANTIRISH] {path} buzilgan, butun kadr ishlatiladi.")
    return None


def order_corners(pts):
    """4 nuqtani chap-yuqori, o'ng-yuqori, o'ng-past, chap-past tartibiga
    keltiradi — foydalanuvchi qaysi tartibda bosganidan qat'i nazar."""
    import numpy as np

    pts = np.asarray(pts, dtype="float32")
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    return np.array([pts[np.argmin(s)], pts[np.argmin(d)],
                     pts[np.argmax(s)], pts[np.argmax(d)]], dtype="float32")


def warp_to_screen(frame, corners):
    """Kadrdagi qiya ekranni to'g'ri to'rtburchakka aylantiradi.
    Chiqish o'lchami ekranning kadrdagi eng uzun tomonlariga teng —
    piksellar kichraytirilmaydi, aniqlik saqlanadi."""
    import cv2
    import numpy as np

    tl, tr, br, bl = order_corners(corners)
    w = int(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl)))
    h = int(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr)))
    dst = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], dtype="float32")
    m = cv2.getPerspectiveTransform(np.array([tl, tr, br, bl]), dst)
    return cv2.warpPerspective(frame, m, (w, h), flags=cv2.INTER_CUBIC)


def frame_problem(frame) -> str | None:
    """Kadr yaroqsiz bo'lsa sababini qaytaradi, yaroqli bo'lsa None.

    Bular kamera qaysi dashboardga qaratilganiga bog'liq emas:
      - USB orqali kadr oxirigacha kelmasa, pastki qismi bir tekis
        kulrang bo'ladi (sinovda kuzatilgan);
      - monitor o'chgan yoki kamera yopilgan bo'lsa, kadr deyarli qora;
      - kadrda hech qanday tafsilot yo'q (kamera fokusni yo'qotgan)."""
    import numpy as np

    gray = frame.mean(axis=2) if frame.ndim == 3 else frame
    if gray.mean() < 12:
        return "kadr juda qorong'i (monitor o'chgan yoki kamera yopilgan)"
    tail = gray[int(gray.shape[0] * 0.75):]
    if (np.ptp(tail, axis=1) <= 6).mean() > 0.5:
        return "kadrning pastki qismi kelmagan (USB uzatish xatosi)"
    # Dashboard — matn va ramkalarga to'la, keskin qirralar ko'p. O'lchangan:
    # yaxshi kadrlarda qirralar ulushi 0.11-0.14; monitor o'chib, kamerada
    # faqat xira aks qolganda — 0.0007. Bunday kadrni AI'ga yuborish
    # bo'sh natija beradi va bazaga "hamma qiymat yo'qoldi" bo'lib tushadi.
    import cv2
    g = gray.astype("uint8")
    small = cv2.resize(g, (960, max(1, int(960 * g.shape[0] / g.shape[1]))))
    if (cv2.Canny(small, 60, 150) > 0).mean() < 0.01:
        return "kadrda ekran ko'rinmayapti (monitor o'chgan, kamera surilgan yoki fokus yo'q)"
    return None


def open_camera(index: int, width: int = 0, height: int = 0):
    """Kamerani ochadi. width/height 0 bo'lsa, kamera qo'llaydigan ENG
    KATTA o'lcham tanlanadi — matn uchun har bir piksel muhim."""
    import cv2

    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        raise CaptureError(
            f"Kamera {index} ochilmadi. Kamera ulanganini va boshqa dastur "
            f"(masalan kamera ko'rinish oynasi) uni band qilmaganini tekshiring.")
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    if width and height:
        sizes = [(width, height)]
    else:
        sizes = [(3840, 2160), (2560, 1440), (2304, 1536), (1920, 1080), (1280, 720)]
    best = (0, 0)
    for w, h in sizes:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        got = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        if got[0] * got[1] > best[0] * best[1]:
            best = got
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, best[0])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, best[1])
    return cap, best


class CameraSource:
    def __init__(self):
        self._cap, size = open_camera(CAMERA_INDEX, CAMERA_WIDTH, CAMERA_HEIGHT)
        self._calib = load_calibration()
        if self._calib and list(self._calib.get("frame_size", [])) != list(size):
            print(f"[CAPTURE][OGOHLANTIRISH] Kalibrlash {self._calib.get('frame_size')} o'lchamda "
                  f"qilingan, kamera hozir {size}. Burchaklar moslashtiriladi, lekin "
                  f"`py camera_calibrate.py` ni qayta ishga tushirish tavsiya etiladi.")
        note = "ekran 4 burchak bo'yicha kesiladi" if self._calib else \
            "KALIBRLASH YO'Q — butun kadr ishlatiladi (`py camera_calibrate.py`)"
        print(f"[CAPTURE] Kamera {CAMERA_INDEX} ochildi: {size[0]}x{size[1]}, {note}.")
        self._size = size

    def _read_fresh(self):
        # Kamera ichki buferida eski kadrlar turadi — oxirgisini olish
        # uchun bir nechtasini tashlab yuboramiz.
        for _ in range(max(0, CAMERA_WARMUP_FRAMES)):
            self._cap.grab()
        ok, frame = self._cap.read()
        if not ok or frame is None:
            raise CaptureError("Kameradan kadr kelmadi (kabel uzilgan bo'lishi mumkin).")
        return frame

    def grab(self, path: str) -> str:
        import cv2
        import numpy as np

        problem = None
        for _ in range(3):
            frame = self._read_fresh()
            problem = frame_problem(frame)
            if problem is None:
                break
            print(f"[CAPTURE] Yaroqsiz kadr tashlandi: {problem}")
            time.sleep(0.5)
        else:
            raise CaptureError(f"3 marta ketma-ket yaroqsiz kadr: {problem}")

        if self._calib:
            corners = np.asarray(self._calib["corners"], dtype="float32")
            fw, fh = self._calib.get("frame_size", self._size)
            if (fw, fh) != (frame.shape[1], frame.shape[0]):
                corners *= [frame.shape[1] / fw, frame.shape[0] / fh]
            frame = warp_to_screen(frame, corners)

        # PNG — siqish artefakti qo'shilmaydi; bo'laklarga kesilgach
        # vision_toolkit o'zi JPEG qiladi.
        cv2.imwrite(path, frame)
        return path

    def close(self):
        self._cap.release()


# ───────────────────────── OYNA va EKRAN ─────────────────────────────────
class WindowSource:
    def grab(self, path: str) -> str:
        from vision_toolkit import take_screenshot_from_window
        return take_screenshot_from_window(path)

    def close(self):
        pass


class ScreenSource:
    def grab(self, path: str) -> str:
        import mss
        with mss.mss() as sct:
            sct.shot(mon=1, output=path)
        return path

    def close(self):
        pass


def open_source():
    mode = CAPTURE_MODE
    if mode == "url":
        return UrlSource()
    if mode == "camera":
        return CameraSource()
    if mode == "window":
        return WindowSource()
    if mode == "screen":
        return ScreenSource()
    raise ValueError(f"Noma'lum CAPTURE_MODE: {mode!r} (url/camera/window/screen)")
