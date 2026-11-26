#!/usr/bin/env bash
# =====================================================================
#  VagonDetect -- bitta buyruq bilan o'rnatish (Linux: Ubuntu/Debian, x86_64 yoki ARM64)
#
#   ./install.sh                         -- barcha kerakli paketlarni o'rnatadi
#   ./install.sh --servis "<manba>"      -- + 24/7 ishlaydigan systemd servis qiladi
#        manba: "rtsp://admin:parol@192.168.1.64:554/Streaming/Channels/101" yoki 0 (USB kamera)
#
#  Nima qiladi:
#   1. Tizim paketlari yetishmasa (python3-venv, libGL) -- apt orqali o'rnatadi (sudo so'raydi)
#   2. Loyiha ichida .venv yaratadi (tizim Python'iga tegmaydi)
#   3. NVIDIA GPU va drayverning CUDA versiyasini aniqlab, mos PyTorch o'rnatadi
#      (GPU bo'lmasa -- CPU versiya; NVIDIA Jetson bo'lsa -- Jetson uchun maxsus PyTorch
#      va tizimdagi TensorRT .venv ga ulanadi)
#   4. requirements.txt dagi paketlarni o'rnatadi va hammasini tekshiradi
# =====================================================================
set -euo pipefail
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
cd "$DIR"
say() { echo -e "\n==> $*"; }

# ---------------------------------------------------------- 0. modellar
for m in detection4.pt classificationvagon.pt detect-t-v-small.pt cllas-t-vsmall.pt; do
  if [ ! -f "$m" ]; then
    echo "XATO: '$m' topilmadi. To'rtta model fayli logic_N_T_V.py bilan bir papkada bo'lishi kerak."
    exit 1
  fi
done

# ---------------------------------------------------------- 1. tizim paketlari
# Tizimda kutubxona bormi. "grep -q" ISHLATILMAYDI: u birinchi mos qatorda chiqib ketadi, ldconfig esa
# yozishda davom etib SIGPIPE oladi va "pipefail" tufayli bor kutubxona "yo'q" bo'lib chiqadi.
has_lib() { ldconfig -p 2>/dev/null | grep -F "$1" >/dev/null; }
need=()
python3 -c 'import venv, ensurepip' 2>/dev/null || need+=(python3-venv python3-pip)
has_lib 'libGL.so.1'       || need+=(libgl1)
has_lib 'libglib-2.0.so.0' || need+=(libglib2.0-0)
if ! command -v python3 >/dev/null; then need+=(python3); fi
if [ -f /etc/nv_tegra_release ]; then
  # Jetson uchun PyTorch yig'masi shu tizim kutubxonalariga bog'langan
  has_lib 'libopenblas.so.0' || need+=(libopenblas0)
  has_lib 'libnuma.so.1'     || need+=(libnuma1)
  has_lib 'libgomp.so.1'     || need+=(libgomp1)
fi
if [ ${#need[@]} -gt 0 ]; then
  say "Tizim paketlari o'rnatilmoqda: ${need[*]}"
  if command -v apt-get >/dev/null; then
    sudo apt-get update || echo "  (apt-get update xato berdi -- o'rnatishga urinib ko'ramiz)"
    sudo apt-get install -y "${need[@]}"
  else
    echo "apt-get topilmadi -- quyidagilarni qo'lda o'rnating: ${need[*]}"; exit 1
  fi
fi
python3 -c 'import sys; assert sys.version_info >= (3, 9), "Python 3.9+ kerak"'

# ---------------------------------------------------------- 2. virtual muhit
if [ ! -x .venv/bin/python ]; then
  say "Virtual muhit yaratilmoqda (.venv)"
  python3 -m venv .venv
fi
PY="$DIR/.venv/bin/python"
"$PY" -m pip install --upgrade pip wheel "setuptools<82" -q     # PyTorch setuptools<82 ni talab qiladi

# ---------------------------------------------------------- 3. PyTorch (GPU ga mos)
TORCH_INDEX=cpu
JETSON=0
if [ -f /etc/nv_tegra_release ]; then
  # NVIDIA Jetson: oddiy PyTorch yig'malari Jetson GPU sini ko'rmaydi -- Jetson uchun maxsus indeks kerak.
  # JetPack 6 (L4T R36) + CUDA 12.6 da sinalgan: torch 2.11.0, torchvision 0.26.0.
  JETSON=1
  L4T=$(sed -n 's/^# R\([0-9]*\) .*/\1/p' /etc/nv_tegra_release | head -1)
  CUDA=$(ls -d /usr/local/cuda-[0-9]*.[0-9]* 2>/dev/null | sed -n 's/.*cuda-\([0-9]*\)\.\([0-9]*\)$/\1\2/p' | sort -n | tail -1)
  if [ "${L4T:-0}" -lt 36 ] || [ -z "$CUDA" ] || ! has_lib 'libcudnn.so'; then
    echo "XATO: bu Jetsonda (L4T R${L4T:-?}, CUDA ${CUDA:-topilmadi}) JetPack 6 to'liq o'rnatilmagan (CUDA / cuDNN yo'q)."
    echo "      Avval:  sudo apt update && sudo apt install nvidia-jetpack   -- keyin ./install.sh ni qayta ishga tushiring."
    exit 1
  fi
  TORCH_INDEX="https://pypi.jetson-ai-lab.io/jp$((L4T - 30))/cu$CUDA"
  say "NVIDIA Jetson: L4T R$L4T, CUDA ${CUDA:0:${#CUDA}-1}.${CUDA: -1} -> PyTorch '$TORCH_INDEX'"
elif command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
  CUDA=$(nvidia-smi | sed -n 's/.*CUDA Version: *\([0-9]*\)\.\([0-9]*\).*/\1\2/p' | head -1)
  CUDA=${CUDA:-0}
  if   [ "$CUDA" -ge 130 ]; then TORCH_INDEX=cu130
  elif [ "$CUDA" -ge 128 ]; then TORCH_INDEX=cu128
  elif [ "$CUDA" -ge 126 ]; then TORCH_INDEX=cu126
  elif [ "$CUDA" -ge 124 ]; then TORCH_INDEX=cu124
  elif [ "$CUDA" -ge 121 ]; then TORCH_INDEX=cu121
  elif [ "$CUDA" -ge 118 ]; then TORCH_INDEX=cu118
  fi
  say "NVIDIA GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader | head -1), drayver CUDA ${CUDA:0:${#CUDA}-1}.${CUDA: -1} -> PyTorch '$TORCH_INDEX'"
else
  say "NVIDIA GPU topilmadi -> PyTorch CPU versiyasi (real vaqt uchun NVIDIA GPU tavsiya etiladi)"
fi
if [ $JETSON -eq 1 ]; then
  SITE=$("$PY" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
  if [ ! -d "$SITE/torch" ]; then
    "$PY" -m pip install --index-url "$TORCH_INDEX" torch==2.11.0 torchvision==0.26.0 \
      || "$PY" -m pip install --index-url "$TORCH_INDEX" torch torchvision
  fi
  if [ ! -e "$SITE/torch/lib/libcudss.so.0" ]; then
    # Jetson PyTorch libcudss.so.0 ni talab qiladi, u esa JetPack tarkibida yo'q. Faqat o'zini olamiz
    # (--no-deps): uning bog'liqliklari (CUDA 12.9 cuBLAS, ~600 MB) Jetsonning CUDA 12.6 si bilan
    # to'qnashib, "CUBLAS_STATUS_ALLOC_FAILED" xatosini beradi. Kutubxona PyTorch topadigan joyga ulanadi.
    "$PY" -m pip install --no-deps nvidia-cudss-cu12==0.7.1.6
    ln -sfn ../../nvidia/cu12/lib/libcudss.so.0 "$SITE/torch/lib/libcudss.so.0"
  fi
fi
if ! "$PY" -c 'import torch' 2>/dev/null; then
  if [ $JETSON -eq 1 ]; then
    echo "XATO: PyTorch o'rnatildi, lekin yuklanmayapti:"; "$PY" -c 'import torch' || true; exit 1
  fi
  "$PY" -m pip install --index-url "https://download.pytorch.org/whl/$TORCH_INDEX" torch torchvision
else
  say "PyTorch allaqachon o'rnatilgan: $("$PY" -c 'import torch; print(torch.__version__)')"
fi

# ---------------------------------------------------------- 4. qolgan paketlar
say "Paketlar o'rnatilmoqda (requirements.txt)"
"$PY" -m pip install -r requirements.txt
if [ "$TORCH_INDEX" = "cpu" ] && [ "$(uname -m)" = "x86_64" ]; then
  # GPU yo'q Intel/AMD kompyuter: t/v detektori OpenVINO bilan 2-3 barobar tez ishlaydi (ixtiyoriy)
  say "GPU yo'q -- CPU tezlatkichi (OpenVINO) o'rnatilmoqda"
  "$PY" -m pip install openvino || echo "  OpenVINO o'rnatilmadi -- oddiy CPU rejimida ishlaydi"
fi
if [ $JETSON -eq 1 ]; then
  # TensorRT Jetsonda JetPack bilan birga tizimga o'rnatilgan (pip'da yo'q) -- uni .venv ga ulaymiz.
  # TensorRT'siz dastur PyTorch'da ~5 kadr/s beradi, TensorRT bilan ~20 kadr/s.
  if ! "$PY" -c 'import tensorrt' 2>/dev/null; then
    SYS_TRT=$(cd / && python3 -c 'import tensorrt, os; print(os.path.dirname(os.path.dirname(tensorrt.__file__)))' 2>/dev/null || true)
    if [ -z "$SYS_TRT" ] && command -v apt-get >/dev/null; then
      sudo apt-get install -y python3-libnvinfer || true
      SYS_TRT=$(cd / && python3 -c 'import tensorrt, os; print(os.path.dirname(os.path.dirname(tensorrt.__file__)))' 2>/dev/null || true)
    fi
    if [ -n "$SYS_TRT" ]; then
      SITE=$("$PY" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
      for p in "$SYS_TRT"/tensorrt*; do ln -sfn "$p" "$SITE/$(basename "$p")"; done
      say "TensorRT .venv ga ulandi ($SYS_TRT)"
    else
      echo "  OGOHLANTIRISH: tizimda TensorRT topilmadi -- dastur sekin (PyTorch) rejimda ishlaydi."
      echo "  Tuzatish: sudo apt install nvidia-jetpack, keyin ./install.sh ni qayta ishga tushiring."
    fi
  fi
  # Modellarni TensorRT ga o'tkazish uchun kerak (aks holda birinchi ishga tushishda internetdan yuklanadi)
  "$PY" -m pip install "onnx>=1.12.0,<2.0.0" "onnxslim>=0.1.82" onnxruntime
fi

# Qt oynasi shrift ogohlantirishlari chiqmasin (tizim shriftlari ulanadi)
QTDIR=$("$PY" -c 'import cv2, os; print(os.path.join(os.path.dirname(cv2.__file__), "qt"))')
for fd in /usr/share/fonts/truetype/dejavu /usr/share/fonts/dejavu /usr/share/fonts/TTF; do
  if [ -d "$fd" ] && [ -d "$QTDIR" ] && [ ! -e "$QTDIR/fonts" ]; then ln -s "$fd" "$QTDIR/fonts"; break; fi
done

# ---------------------------------------------------------- 5. tekshiruv
say "Tekshiruv"
"$PY" - <<'EOF'
import torch, cv2, ultralytics, lap, numpy
gpu = torch.cuda.is_available()
print(f"  torch {torch.__version__} | GPU: {torch.cuda.get_device_name(0) if gpu else 'YOQ (CPU)'}")
print(f"  opencv {cv2.__version__} | ultralytics {ultralytics.__version__} | numpy {numpy.__version__}")
if gpu:
    x = torch.randn(512, 512, device="cuda"); assert torch.isfinite(x @ x).all()
    print("  GPU hisoblash testi: OK")
    import importlib.util
    if importlib.util.find_spec("tensorrt"):
        import tensorrt
        print(f"  TensorRT {tensorrt.__version__}: modellar birinchi ishga tushishda tezlashtiriladi (engines/)")
    else:
        print("  TensorRT yo'q: modellar oddiy PyTorch GPU rejimida ishlaydi")
EOF

# ---------------------------------------------------------- 6. 24/7 servis (ixtiyoriy)
if [ "${1:-}" = "--servis" ]; then
  SRC="${2:-}"
  if [ -z "$SRC" ]; then echo "Manba ko'rsatilmadi: ./install.sh --servis \"rtsp://...\""; exit 1; fi
  UNIT=/etc/systemd/system/vagon-detect.service
  say "systemd servis yaratilmoqda: $UNIT"
  sudo tee "$UNIT" >/dev/null <<EOF
[Unit]
Description=VagonDetect - vagon raqami, tonna va hajmni aniqlash (24/7)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$(id -un)
WorkingDirectory=$DIR
ExecStart=$PY -u $DIR/logic_N_T_V.py "$SRC" --oynasiz
Restart=always
RestartSec=5
KillSignal=SIGTERM
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF
  sudo systemctl daemon-reload
  sudo systemctl enable --now vagon-detect.service
  say "Servis ishga tushdi. Holat:   systemctl status vagon-detect"
  echo "    Jurnal (jonli): journalctl -u vagon-detect -f"
  echo "    To'xtatish:     sudo systemctl stop vagon-detect"
fi

say "Tayyor. Ishga tushirish:  ./run.sh <video yoki kamera manzili>"
