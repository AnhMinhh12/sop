@echo off
REM prepare_edge.bat - Chuẩn bị Edge server (Windows)
REM Usage: prepare_edge.bat <hub_url> <api_key> [camera_id]
REM Ví dụ: prepare_edge.bat http://10.0.10.100:5001 my-secret-key machine_06

set HUB_URL=%1
set API_KEY=%2
set CAMERA_ID=%3

if "%HUB_URL%"=="" set HUB_URL=http://localhost:5001
if "%API_KEY%"=="" set API_KEY=change-me-in-production
if "%CAMERA_ID%"=="" set CAMERA_ID=edge_camera

echo === Edge Setup ===
echo Hub URL: %HUB_URL%
echo Camera ID: %CAMERA_ID%
echo.

REM Create folder structure
mkdir edge_log 2>nul
mkdir shared\models\yolo 2>nul
mkdir projects\sop_monitoring\config 2>nul
mkdir projects\sop_monitoring\core\engines 2>nul

REM Create config.yaml
(
echo camera:
echo   id: "%CAMERA_ID%"
echo   name: "Edge Camera"
echo   rtsp_url: "rtsp://admin:password@192.168.1.100:554/Streaming/Channels/101"
echo   resolution: [640, 480]
echo.
echo hub:
echo   url: "%HUB_URL%"
echo   api_key: "%API_KEY%"
echo.
echo ai:
echo   model_path: "shared\models\yolo\laprap.onnx"
echo   input_size: 416
echo.
echo sop:
echo   file: "projects\sop_monitoring\config\laprap.yaml"
echo.
echo push:
echo   interval_sec: 1.0
echo   quality: 60
) > edge_config.yaml

echo Created: edge_config.yaml
echo.
echo === Setup Complete ===
echo 1. Copy ONNX model vao: shared\models\yolo\
echo 2. Copy SOP config vao: projects\sop_monitoring\config\
echo 3. Chay: python edge_client\main.py --config edge_config.yaml
echo.
pause
