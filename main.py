import os
import logging
import signal
import sys
import cv2

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        # Fallback for Python versions < 3.7
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# --- TỐI ƯU HÓA TÀI NGUYÊN ---
# Giới hạn OpenCV threads để không chiếm hết CPU cores
cv2.setNumThreads(0)
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OMP_WAIT_POLICY"] = "PASSIVE"

from services.config_loader import ConfigLoader
from services.disk_monitor import DiskMonitor
from pipelines.inference_engine import InferenceEngine
from pipelines.frame_processor import FrameProcessor
from core.spatial_engine import SpatialEngine
from core.violation_detector import ViolationDetector
from events.audio_alert import AudioAlert
from events.clip_saver import ClipSaver
from db.db import db
from db.cleanup import StorageCleanup
from app import app as flask_app, socketio, processors

# Đảm bảo các thư mục dữ liệu tồn tại
os.makedirs("data/logs", exist_ok=True)
os.makedirs("data/violations", exist_ok=True)

# Cấu hình log chuyên nghiệp
# Đảm bảo StreamHandler sử dụng sys.stdout đã được reconfigure
console_handler = logging.StreamHandler(sys.stdout)
file_handler = logging.FileHandler("data/logs/system.log", encoding='utf-8')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[file_handler, console_handler]
)
logger = logging.getLogger("Main")


def shutdown_handler(signum, frame):
    """Xử lý tắt hệ thống an toàn."""
    logger.info("Shutdown signal received. Stopping all processors...")
    for cam_id, processor in processors.items():
        processor.stop()
    sys.exit(0)


signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)


def start_sop_monitoring():
    """Hàm khởi động chính."""
    logger.info("=== HTMP SOP MONITORING SYSTEM STARTING ===")

    # 1. Load config
    config = ConfigLoader.load_config()
    if not config:
        logger.error("Failed to load config.yaml. Exiting.")
        return

    # 2. Khởi tạo Database (Đã tự động khởi tạo khi import db)

    # 3. Khởi tạo AI Engine (Singleton)
    yolo_cfg = config["models"]["yolo"]
    inference_cfg = config.get("inference", {})
    InferenceEngine(
        model_path=yolo_cfg["weights"],
        num_threads=inference_cfg.get("num_threads", 4),
        input_size=yolo_cfg["input_size"]
    )

    # 4. Khởi tạo các dịch vụ toàn hệ thống
    logger.info("Main: Initializing system services...")
    cleanup = StorageCleanup(
        violations_dir="data/violations",
        max_usage_percent=85.0
    )
    cleanup.start()

    logger.info("Main: Creating ClipSaver...")
    clip_saver = ClipSaver(output_dir="data/violations", fps=yolo_cfg.get("fps_cap", 15))

    logger.info("Main: Creating AudioAlert (Safe Mode)...")
    audio_alert = None
    try:
        audio_alert = AudioAlert(sound_file="sounds/alert.wav")
    except Exception as e:
        logger.error(f"Main: AudioAlert failed to init: {e}. System will continue without audio.")

    # 5. Khởi tạo từng trạm Camera
    logger.info(f"Main: Found {len(config['cameras'])} cameras in config.")
    for cam_cfg in config["cameras"]:
        cam_id = cam_cfg["id"]
        station_id = cam_cfg["id"]

        logger.info(f"Main: Starting station {station_id} setup...")

        # Load SOP (Phiên bản ZONES mới)
        clean_sid = station_id.replace("station_", "")
        sop_def = ConfigLoader.load_sop_definition(clean_sid)
        
        # New Reformed Engine
        spatial_engine = SpatialEngine(sop_def)
        violation_detector = ViolationDetector(cam_id)

        # Tạo Processor trung tâm
        logger.info(f"Main: Building Reformed FrameProcessor for {cam_id}...")
        processor = FrameProcessor(
            camera_config=cam_cfg,
            spatial_engine=spatial_engine,
            violation_detector=violation_detector,
            audio_alert=audio_alert,
            clip_saver=clip_saver
        )

        # Lưu vào registry và Khởi chạy
        processors[cam_id] = processor
        processor.start()
        logger.info(f"Main: Station {cam_id} is now ACTIVE (Spatial Based).")

    # 6. Chạy Web Dashboard
    logger.info("====================================================")
    logger.info("  DASHBOARD IS READY AT: http://localhost:5001")
    logger.info("====================================================")

    # Khởi chạy Web Dashboard ở chế độ đa luồng (threading)
    socketio.run(flask_app, host='0.0.0.0', port=5001,
                 debug=False, use_reloader=False,
                 log_output=True, allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    start_sop_monitoring()
