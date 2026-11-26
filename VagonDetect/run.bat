@echo off
REM VagonDetect -- ishga tushirish (birinchi marta bo'lsa, avval o'zi o'rnatadi).
REM   run.bat video.mp4
REM   run.bat "rtsp://admin:parol@192.168.1.64:554/Streaming/Channels/101"
REM   run.bat 0          (USB kamera)
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe call install.bat
.venv\Scripts\python.exe -u logic_N_T_V.py %*
