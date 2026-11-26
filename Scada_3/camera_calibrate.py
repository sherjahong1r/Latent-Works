"""
camera_calibrate.py — kamera kadrida dashboard ekranining 4 burchagini
belgilash. Kamera joyi o'zgarganda BIR MARTA ishga tushiriladi.

    py camera_calibrate.py              # .env dagi CAMERA_INDEX kamerasi
    py camera_calibrate.py --image x.jpg   # kamerasiz, tayyor rasm ustida

Oynada:
  - sichqoncha bilan ekranning 4 burchagini bosing (istalgan tartibda);
    ekran kadrdan chiqib ketgan bo'lsa, kadr chetini bosing
  - ENTER  — natijani ko'rish va saqlash
  - R      — qaytadan belgilash
  - Q/Esc  — saqlamasdan chiqish

Natija camera_calibration.json ga yoziladi; capture_source.py uni har
kadrda ishlatib, ekranni to'g'ri to'rtburchak qilib kesadi.
"""

import argparse
import ctypes
import json
import sys

import cv2
import numpy as np

from capture_source import open_camera, order_corners, warp_to_screen, frame_problem
from config import CAMERA_INDEX, CAMERA_WIDTH, CAMERA_HEIGHT, CAMERA_CALIBRATION_FILE

WIN = "Kalibrlash: ekranning 4 burchagini bosing (ENTER saqlash, R qayta, Q chiqish)"


def _screen_size():
    try:
        u = ctypes.windll.user32
        u.SetProcessDPIAware()
        return u.GetSystemMetrics(0), u.GetSystemMetrics(1)
    except Exception:
        return 1600, 900


def _grab_frame(index: int):
    cap, size = open_camera(index, CAMERA_WIDTH, CAMERA_HEIGHT)
    frame = None
    for _ in range(15):
        ok, f = cap.read()
        if ok and frame_problem(f) is None:
            frame = f
    cap.release()
    if frame is None:
        sys.exit("Kameradan yaroqli kadr olinmadi.")
    return frame


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", help="kamera o'rniga shu rasmdan foydalanish")
    ap.add_argument("--camera", type=int, default=CAMERA_INDEX)
    args = ap.parse_args()

    frame = cv2.imread(args.image) if args.image else _grab_frame(args.camera)
    if frame is None:
        sys.exit("Rasm o'qilmadi.")
    fh, fw = frame.shape[:2]

    sw, sh = _screen_size()
    scale = min((sw * 0.9) / fw, (sh * 0.85) / fh, 1.0)
    points: list[tuple[float, float]] = []

    def on_mouse(event, x, y, _flags, _param):
        if event == cv2.EVENT_LBUTTONDOWN and len(points) < 4:
            points.append((x / scale, y / scale))

    cv2.namedWindow(WIN, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(WIN, on_mouse)

    while True:
        view = cv2.resize(frame, (int(fw * scale), int(fh * scale)))
        pts = [(int(x * scale), int(y * scale)) for x, y in points]
        for p in pts:
            cv2.circle(view, p, 8, (0, 0, 255), -1)
        if len(pts) == 4:
            poly = order_corners(np.array(pts)).astype(int)
            cv2.polylines(view, [poly], True, (0, 255, 0), 3)
            msg = "ENTER - saqlash, R - qaytadan"
        else:
            msg = f"Ekran burchagini bosing: {len(pts)}/4"
        cv2.putText(view, msg, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 255, 255), 3)
        cv2.imshow(WIN, view)

        key = cv2.waitKey(30) & 0xFF
        if key in (ord("q"), 27) or cv2.getWindowProperty(WIN, cv2.WND_PROP_VISIBLE) < 1:
            print("Saqlanmadi.")
            break
        if key == ord("r"):
            points.clear()
        if key in (13, 10) and len(points) == 4:
            corners = order_corners(points)
            warped = warp_to_screen(frame, corners)
            data = {
                "corners": [[round(float(x), 1), round(float(y), 1)] for x, y in corners],
                "frame_size": [fw, fh],
                "screen_size": [int(warped.shape[1]), int(warped.shape[0])],
            }
            with open(CAMERA_CALIBRATION_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=1)
            cv2.imwrite("camera_calibration_preview.png", warped)
            print(f"Saqlandi: {CAMERA_CALIBRATION_FILE}  (ekran {data['screen_size'][0]}x"
                  f"{data['screen_size'][1]} px). Natija: camera_calibration_preview.png")
            cv2.destroyWindow(WIN)
            pv = "Natija (istalgan tugma - yopish)"
            k = min((sw * 0.9) / warped.shape[1], (sh * 0.85) / warped.shape[0], 1.0)
            cv2.imshow(pv, cv2.resize(warped, (int(warped.shape[1] * k), int(warped.shape[0] * k))))
            cv2.waitKey(0)
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
