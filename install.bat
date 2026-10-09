@echo off
REM ==================================================================
REM  VagonDetect -- bitta buyruq bilan o'rnatish (Windows 10/11, x64)
REM  Talab: Python 3.9+ (https://www.python.org/downloads/, "Add to PATH" belgilansin)
REM ==================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"
for %%m in (detection4.pt classificationvagon.pt detect-t-v-small.pt cllas-t-vsmall.pt) do (
  if not exist "%%m" ( echo XATO: %%m topilmadi & pause & exit /b 1 )
)
where python >nul 2>nul || ( echo Python topilmadi. https://www.python.org/downloads/ dan o'rnating. & pause & exit /b 1 )
if not exist .venv\Scripts\python.exe ( echo Virtual muhit yaratilmoqda... & python -m venv .venv )
set PY=.venv\Scripts\python.exe
%PY% -m pip install --upgrade pip wheel setuptools -q

set IDX=cpu
where nvidia-smi >nul 2>nul
if !errorlevel! == 0 (
  for /f "usebackq delims=" %%v in (`powershell -NoProfile -Command "$m=(nvidia-smi ^| Select-String 'CUDA Version:\s*(\d+)\.(\d+)').Matches; if($m){[int]$m[0].Groups[1].Value*10+[int]$m[0].Groups[2].Value}else{0}"`) do set CUDAV=%%v
  if !CUDAV! GEQ 130 ( set IDX=cu130 ) else if !CUDAV! GEQ 128 ( set IDX=cu128 ) else if !CUDAV! GEQ 126 ( set IDX=cu126 ) else if !CUDAV! GEQ 124 ( set IDX=cu124 ) else if !CUDAV! GEQ 121 ( set IDX=cu121 ) else if !CUDAV! GEQ 118 ( set IDX=cu118 )
  echo NVIDIA GPU topildi, drayver CUDA !CUDAV! -^> PyTorch !IDX!
) else (
  echo NVIDIA GPU topilmadi -^> PyTorch CPU versiyasi
)
%PY% -c "import torch" 2>nul || %PY% -m pip install --index-url https://download.pytorch.org/whl/!IDX! torch torchvision
%PY% -m pip install -r requirements.txt
if "!IDX!" == "cpu" ( echo GPU yo'q -- CPU tezlatkichi OpenVINO o'rnatilmoqda & %PY% -m pip install openvino )
%PY% -c "import torch,cv2,ultralytics;print('torch',torch.__version__,'| GPU:',torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'YOQ (CPU)');print('opencv',cv2.__version__,'| ultralytics',ultralytics.__version__)"
echo.
echo Tayyor. Ishga tushirish:  run.bat ^<video yoki kamera manzili^>
endlocal
