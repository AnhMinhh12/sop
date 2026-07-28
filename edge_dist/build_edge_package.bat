@echo off
REM build_edge_package.bat - Build gói Edge sạch
REM Chạy trên máy Hub

set DEST=edge_package

echo === Building Edge Package ===

REM 1. Create folders
echo Creating folder structure...
mkdir %DEST% 2>nul
mkdir %DEST%\edge_client 2>nul
mkdir %DEST%\shared\services 2>nul
mkdir %DEST%\shared\db 2>nul
mkdir %DEST%\shared\events 2>nul
mkdir %DEST%\shared\models\yolo 2>nul
mkdir %DEST%\projects\sop_monitoring\core\engines 2>nul
mkdir %DEST%\projects\sop_monitoring\config 2>nul
mkdir %DEST%\config 2>nul
mkdir %DEST%\__pycache__ 2>nul

REM 2. Copy edge_client
echo Copying edge_client...
copy edge_client\*.py %DEST%\edge_client\
copy edge_client\requirements.txt %DEST%\edge_client\

REM 3. Copy shared (chỉ file cần thiết)
echo Copying shared...
copy shared\rtsp_manager.py %DEST%\shared\
copy shared\inference_engine.py %DEST%\shared\
copy shared\services\config_loader.py %DEST%\shared\services\
copy shared\services\annotator.py %DEST%\shared\services\
copy shared\services\__init__.py %DEST%\shared\services\ 2>nul
copy shared\events\*.py %DEST%\shared\events\
copy shared\db\*.py %DEST%\shared\db\
copy shared\__init__.py %DEST%\shared\

REM 4. Copy projects/sop_monitoring
echo Copying projects...
copy projects\sop_monitoring\processor.py %DEST%\projects\sop_monitoring\
copy projects\sop_monitoring\hand_detector.py %DEST%\projects\sop_monitoring\
copy projects\sop_monitoring\buffer.py %DEST%\projects\sop_monitoring\
copy projects\sop_monitoring\core\violation_detector.py %DEST%\projects\sop_monitoring\core\
copy projects\sop_monitoring\core\engines\*.py %DEST%\projects\sop_monitoring\core\engines\
copy projects\sop_monitoring\core\engines\base_engine.py %DEST%\projects\sop_monitoring\core\engines\
copy projects\sop_monitoring\config\*.yaml %DEST%\projects\sop_monitoring\config\
copy projects\__init__.py %DEST%\projects\ 2>nul
copy projects\sop_monitoring\__init__.py %DEST%\projects\sop_monitoring\ 2>nul
copy projects\sop_monitoring\core\__init__.py %DEDT%\projects\sop_monitoring\core\ 2>nul

REM 5. Copy config template
copy config\config.yaml %DEST%\config\edge_config.yaml.example

REM 6. Create requirements.txt
(
echo opencv-python^>=4.8.0
echo numpy^>=1.24.0
echo requests^>=2.31.0
echo pyyaml^>=6.0
) > %DEST%\requirements.txt

REM 7. Create README
(
echo AI Monitoring Hub - Edge Package
echo =================================
echo.
echo CAI DAT:
echo 1. Copy ONNX model vao: shared\models\yolo\
echo    VD: TFF4040.onnx, laprap.onnx
echo.
echo 2. Tao config.yaml:
echo    copy config\edge_config.yaml.example config.yaml
echo    Edit config.yaml - thay URL, API key, RTSP
echo.
echo 3. Cai dependencies:
echo    pip install -r requirements.txt
echo    pip install -r edge_client\requirements.txt
echo.
echo 4. Chay Edge:
echo    python edge_client\main.py --config config.yaml
echo.
echo HOAC voi env vars:
echo    set HUB_URL=http://10.0.10.100:5001
echo    set HUB_API_KEY=your-key
echo    set CAMERA_ID=machine_06
echo    set RTSP_URL=rtsp://...
echo    python edge_client\main.py
) > %DEST%\README_EDGE.txt

echo.
echo === Done: %DEST% ===
echo.
echo Kich thuoc (chua co model):
dir %DEST% /s /-c 2>nul | findstr "File(s)"
echo.
pause
