@echo off
REM copy_to_edge.bat - Copy cấu trúc Edge-optimized sang thư mục mới
REM Chạy trên máy Hub để chuẩn bị bản Edge

set DEST=%1
if "%DEST%"=="" set DEST=edge_build

echo === Copying Edge-optimized structure to %DEST% ===

REM Create folders
mkdir %DEST% 2>nul
mkdir %DEST%\edge_client 2>nul
mkdir %DEST%\shared\services 2>nul
mkdir %DEST%\shared\db 2>nul
mkdir %DEST%\shared\events 2>nul
mkdir %DEST%\shared\tools 2>nul
mkdir %DEST%\projects\sop_monitoring\core\engines 2>nul
mkdir %DEST%\projects\sop_monitoring\config 2>nul
mkdir %DEST%\config 2>nul
mkdir %DEST%\data 2>nul

REM Copy edge_client
echo Copying edge_client...
copy edge_client\*.py %DEST%\edge_client\
copy edge_client\*.yaml %DEST%\edge_client\ 2>nul
copy edge_client\*.txt %DEST%\edge_client\ 2>nul
copy edge_client\requirements.txt %DEST%\edge_client\

REM Copy shared (chỉ những file cần thiết)
echo Copying shared...
copy shared\rtsp_manager.py %DEST%\shared\
copy shared\inference_engine.py %DEST%\shared\
copy shared\services\config_loader.py %DEST%\shared\services\
copy shared\services\annotator.py %DEST%\shared\services\
copy shared\events\*.py %DEST%\shared\events\
copy shared\db\*.py %DEST%\shared\db\
copy shared\shared\__init__.py %DEST%\shared\ 2>nul

REM Copy projects/sop_monitoring
echo Copying projects/sop_monitoring...
copy projects\sop_monitoring\processor.py %DEST%\projects\sop_monitoring\ 2>nul
copy projects\sop_monitoring\hand_detector.py %DEST%\projects\sop_monitoring\
copy projects\sop_monitoring\buffer.py %DEST%\projects\sop_monitoring\
copy projects\sop_monitoring\core\violation_detector.py %DEST%\projects\sop_monitoring\core\
copy projects\sop_monitoring\core\engines\*.py %DEST%\projects\sop_monitoring\core\engines\
copy projects\sop_monitoring\config\*.yaml %DEST%\projects\sop_monitoring\config\

REM Copy root config and requirements
echo Copying config...
copy config\config.yaml %DEST%\config\edge_config.yaml.example
copy requirements.txt %DEST%\

REM Copy models (thư mục rỗng, user tự copy model vào)
echo Copying models folder...
mkdir %DEST%\shared\models\yolo 2>nul

echo.
echo === Done ===
echo Next steps:
echo 1. Copy ONNX models to: %DEST%\shared\models\yolo\
echo 2. Edit %DEST%\edge_client\config.yaml
echo 3. Copy to Edge server and run: python edge_client\main.py
pause
