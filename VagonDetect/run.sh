#!/usr/bin/env bash
# VagonDetect -- ishga tushirish (birinchi marta bo'lsa, avval o'zi o'rnatadi).
#   ./run.sh video.mp4                -- video faylni real vaqtda tahlil qilish
#   ./run.sh "rtsp://admin:parol@192.168.1.64:554/Streaming/Channels/101"   -- IP-kamera, 24/7
#   ./run.sh 0                        -- USB kamera
# Qo'shimcha: --oynasiz (oynasiz)   --natijalar <papka>   --tez (faylni kutmasdan, tez)
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
cd "$DIR"
if [ $# -eq 0 ]; then
  cat <<'USAGE'
VagonDetect -- manbani ko'rsating:
  ./run.sh video.mp4      video bilan sinov: video tugaganda dastur o'zi to'xtaydi
  ./run.sh 0              USB kamera: o'zingiz to'xtatmaguningizcha uzluksiz ishlaydi
  ./run.sh "rtsp://admin:parol@192.168.1.64:554/Streaming/Channels/101"
                          IP-kamera: o'zingiz to'xtatmaguningizcha uzluksiz ishlaydi
To'xtatish: oynada q yoki terminalda Ctrl+C (joriy poyezd hisoboti saqlanadi).
Qo'shimcha: --oynasiz   --natijalar <papka>   --tez   --vaqt "2026-10-06 12:00:00"
USAGE
  exit 1
fi
if [ ! -x .venv/bin/python ] || ! .venv/bin/python -c 'import torch, cv2, ultralytics' 2>/dev/null; then
  ./install.sh || exit 1
fi
exec .venv/bin/python -u logic_N_T_V.py "$@"
