# =====================================================================
#  Kamera qidiruvchi: USB va tarmoqdagi IP-kameralarni topib, ishlaydigan
#  manzilni (RTSP) aniqlaydi va har biridan bitta surat saqlaydi.
#
#   .venv/bin/python kamera_qidir.py                         -- faqat qidirish
#   .venv/bin/python kamera_qidir.py --login admin --parol 12345   -- RTSP manzilni ham sinash
#   .venv/bin/python kamera_qidir.py --ip 192.168.1.64 --login admin --parol 12345
#
#  Parollar tanlab ko'rilmaydi: faqat siz bergan login/parol ishlatiladi.
# =====================================================================
import os, sys, glob, socket, subprocess, ipaddress, argparse, concurrent.futures as cf
import cv2

RTSP_PATHS = [
    "/Streaming/Channels/101",                    # Hikvision (asosiy oqim)
    "/cam/realmonitor?channel=1&subtype=0",       # Dahua / Imou
    "/h264/ch1/main/av_stream",                   # Hikvision (eski)
    "/live/main", "/stream1", "/11", "/live", "/av0_0", "/onvif1", "/ch01.264", "/",
]
PORTS = (554, 8554)


def usb_cameras():
    found = []
    if os.name == "nt":
        idx = range(4)
        backend = cv2.CAP_DSHOW
    else:
        idx = sorted(int(p.replace("/dev/video", "")) for p in glob.glob("/dev/video*")
                     if p.replace("/dev/video", "").isdigit())
        backend = cv2.CAP_V4L2
    for i in idx:
        cap = cv2.VideoCapture(i, backend)
        ok, f = cap.read() if cap.isOpened() else (False, None)
        cap.release()
        if ok and f is not None:
            cv2.imwrite(f"kamera_usb{i}.jpg", f)
            found.append((i, f.shape[1], f.shape[0]))
    return found


def local_subnets():
    nets = []
    try:
        out = subprocess.run(["ip", "-4", "-o", "addr"], capture_output=True, text=True).stdout
        for line in out.splitlines():
            parts = line.split()
            dev, cidr = parts[1], parts[3]
            if dev == "lo" or dev.startswith(("docker", "br-", "veth", "virbr")):
                continue
            net = ipaddress.ip_interface(cidr).network
            if net.prefixlen < 24:          # katta tarmoqni butunlay skanerlamaymiz
                net = ipaddress.ip_interface(cidr.split("/")[0] + "/24").network
            nets.append((dev, cidr.split("/")[0], net))
    except FileNotFoundError:
        ip = socket.gethostbyname(socket.gethostname())
        nets.append(("?", ip, ipaddress.ip_interface(ip + "/24").network))
    return nets


def port_open(host, port, timeout=0.4):
    try:
        with socket.create_connection((str(host), port), timeout=timeout):
            return True
    except OSError:
        return False


def try_rtsp(host, port, login, parol):
    os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
    cred = f"{login}:{parol}@" if login else ""
    params = []
    for name, val in (("CAP_PROP_OPEN_TIMEOUT_MSEC", 5000), ("CAP_PROP_READ_TIMEOUT_MSEC", 5000)):
        if hasattr(cv2, name):
            params += [getattr(cv2, name), val]
    for path in RTSP_PATHS:
        url = f"rtsp://{cred}{host}:{port}{path}"
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG, params)
        ok, f = cap.read() if cap.isOpened() else (False, None)
        fps = cap.get(cv2.CAP_PROP_FPS)
        cap.release()
        if ok and f is not None:
            cv2.imwrite(f"kamera_{host}.jpg", f)
            return url, f.shape[1], f.shape[0], fps
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--login", default="")
    ap.add_argument("--parol", default="")
    ap.add_argument("--ip", default="", help="aniq kamera IP si (butun tarmoqni skanerlamasdan)")
    a = ap.parse_args()

    print("== USB kameralar ==")
    usb = usb_cameras()
    for i, w, h in usb:
        print(f"  ✅ USB kamera {i}: {w}x{h}  -> ishga tushirish:  ./run.sh {i}   (surat: kamera_usb{i}.jpg)")
    if not usb:
        print("  topilmadi")

    print("\n== Tarmoq kameralari (RTSP) ==")
    if a.ip:
        hosts = [ipaddress.ip_address(a.ip)]
    else:
        nets = local_subnets()
        for dev, ip, net in nets:
            print(f"  interfeys {dev}: {ip}  -> {net} skanerlanmoqda")
        if not nets:
            print("  IP manzilli tarmoq interfeysi yo'q. Kamera to'g'ridan-to'g'ri serverga kabel bilan ulangan bo'lsa,\n"
                  "  serverning shu portiga kamera tarmog'idan statik IP bering, masalan:\n"
                  "    sudo nmcli con add type ethernet ifname <port> con-name kamera ipv4.method manual ipv4.addresses 192.168.1.100/24")
        hosts = [h for _d, _ip, n in nets for h in n.hosts()]
    with cf.ThreadPoolExecutor(128) as ex:
        opened = [(h, p) for (h, p), ok in zip([(h, p) for h in hosts for p in PORTS],
                  ex.map(lambda hp: port_open(*hp), [(h, p) for h in hosts for p in PORTS])) if ok]
    if not opened:
        print("  RTSP porti ochiq qurilma topilmadi.")
        print("  Tekshiring: kamera yoqilganmi (PoE kamera uchun PoE switch/injektor kerak), kabel ulanganmi,\n"
              "  kamera va server bir tarmoqdami (kamera odatda 192.168.1.64 / .108 / .10 da bo'ladi).")
        return
    for h, p in opened:
        print(f"  • {h}:{p} -- RTSP porti ochiq")
        if not (a.login or a.parol):
            print("      manzilni aniqlash uchun login/parol bering:  --login admin --parol <parol>")
            continue
        r = try_rtsp(h, p, a.login, a.parol)
        if r:
            url, w, hh, fps = r
            shown = url.replace(f":{a.parol}@", ":***@") if a.parol else url
            print(f"      ✅ ISHLAYDI: {shown}  ({w}x{hh}, {fps:.0f} fps)  surat: kamera_{h}.jpg")
            print(f"      ishga tushirish:  ./run.sh \"{url}\"")
        else:
            print("      ❌ login/parol yoki manzil mos kelmadi (kamera veb-sahifasidan RTSP manzilini tekshiring)")


if __name__ == "__main__":
    main()
