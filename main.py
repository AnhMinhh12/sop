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
os.environ["OMP_NUM_THREADS"] = os.getenv("OMP_NUM_THREADS", "1")
os.environ["MKL_NUM_THREADS"] = os.getenv("MKL_NUM_THREADS", "1")
os.environ["OMP_WAIT_POLICY"] = "PASSIVE"

from shared.services.config_loader import ConfigLoader
from shared.services.disk_monitor import DiskMonitor
from shared.inference_engine import InferenceEngine
from projects.sop_monitoring.processor import FrameProcessor
from projects.sop_monitoring.core.engines.loader import EngineLoader
from projects.sop_monitoring.core.violation_detector import ViolationDetector
from shared.events.audio_alert import AudioAlert
from shared.events.clip_saver import ClipSaver
from shared.db.db import db
from shared.db.cleanup import StorageCleanup
from app import app as flask_app, socketio, processors

# Đảm bảo các thư mục dữ liệu tồn tại
LOG_DIR = os.getenv("LOGS_DIR", "data/logs")
VIOLATIONS_DIR = os.getenv("VIOLATIONS_DIR", "data/violations")
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(VIOLATIONS_DIR, exist_ok=True)

# Cấu hình log chuyên nghiệp
# Đảm bảo StreamHandler sử dụng sys.stdout đã được reconfigure
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.WARNING) # Chỉ hiện Warning/Error ra terminal cho gọn

from logging.handlers import TimedRotatingFileHandler
# Xoay vòng system.log hàng ngày và giữ lại 30 bản (1 tháng)
file_handler = TimedRotatingFileHandler(
    os.getenv("LOG_FILE", "data/logs/system.log"), 
    when="D", interval=1, backupCount=30, encoding='utf-8'
)
file_handler.setLevel(logging.INFO)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[file_handler, console_handler]
)
logger = logging.getLogger("Main")

# Thông báo khởi động vẫn cho hiện ra console một lần
print("=== HTMP SOP MONITORING SYSTEM IS STARTING... (Check logs for details) ===")


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
        num_threads=int(os.getenv("AI_MAX_THREADS", inference_cfg.get("num_threads", 8))),
        input_size=int(os.getenv("AI_INPUT_SIZE", yolo_cfg["input_size"]))
    )

    # 4. Khởi tạo các dịch vụ toàn hệ thống
    logger.info("Main: Initializing system services...")
    storage_cfg = config.get("storage", {})
    cleanup = StorageCleanup(
        violations_dir=storage_cfg.get("violations_dir", os.getenv("VIOLATIONS_DIR", "data/violations")),
        max_usage_percent=storage_cfg.get("max_disk_usage_percent", 85.0),
        retention_days=storage_cfg.get("retention_days", 30)
    )
    cleanup.start()

    logger.info("Main: Creating ClipSaver...")
    fps_cap = int(os.getenv("AI_FPS_CAP", yolo_cfg.get("fps_cap", 15)))
    clip_saver = ClipSaver(output_dir=os.getenv("VIOLATIONS_DIR", "data/violations"), fps=fps_cap)

    logger.info("Main: Creating AudioAlert (Safe Mode)...")
    audio_alert = None
    try:
        audio_alert = AudioAlert(sound_file=os.getenv("ALERT_SOUND_PATH", "sounds/alert.wav"))
    except Exception as e:
        logger.error(f"Main: AudioAlert failed to init: {e}. System will continue without audio.")

    # 5. Khởi tạo từng trạm Camera và đồng bộ Database
    from shared.db.queries import CameraQueries, DefinitionQueries

    logger.info(f"Main: Found {len(config['cameras'])} cameras in config.")
    for cam_cfg in config["cameras"]:
        cam_id = cam_cfg["id"]
        station_id = cam_cfg["id"]

        logger.info(f"Main: Starting station {station_id} setup...")

        # Load SOP (Phiên bản ZONES mới)
        sop_file = cam_cfg.get("sop_file")
        if sop_file:
            sop_def = ConfigLoader.load_yaml(sop_file)
        else:
            clean_sid = station_id.replace("station_", "")
            sop_def = ConfigLoader.load_sop_definition(clean_sid)
        
        # --- ĐỒNG BỘ MYSQL: Lưu quy trình và camera vào DB để dashboard sử dụng ---
        def_name = sop_def.get("station_name", f"SOP {station_id}")
        def_id = DefinitionQueries.upsert_definition(def_name, total_steps=len(sop_def.get("steps", [])))
        if def_id:
            DefinitionQueries.sync_steps(def_id, sop_def.get("steps", []))
            CameraQueries.upsert_camera(station_id, cam_cfg["name"], cam_cfg["rtsp_url"], def_id)
        
        # Load Engine Logic cho mã sản phẩm này
        engine_id = cam_cfg.get("engine_id")
        if not engine_id:
            logger.error(f"Main: No engine_id defined for {cam_id}. Skipping.")
            continue
            
        logger.info(f"Main: Loading engine '{engine_id}' for {cam_id}...")
        engine = EngineLoader.create_engine(engine_id, sop_def)
        
        violation_detector = ViolationDetector(cam_id)

        # Tạo Processor trung tâm
        logger.info(f"Main: Building Reformed FrameProcessor for {cam_id}...")
        processor = FrameProcessor(
            camera_config=cam_cfg,
            engine=engine,
            violation_detector=violation_detector,
            audio_alert=audio_alert,
            clip_saver=clip_saver
        )

        # Lưu vào registry và Khởi chạy
        processors[cam_id] = processor
        processor.start()
        logger.info(f"Main: Station {cam_id} is now ACTIVE & SYNCED to MySQL.")

    # Chạy Web Dashboard ở chế độ đa luồng (threading)
    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", 5001))
    
    logger.info("====================================================")
    logger.info(f"  DASHBOARD IS READY AT: http://{host}:{port}")
    logger.info("====================================================")

    socketio.run(flask_app, host=host, port=port,
                 debug=False, use_reloader=False,
                 log_output=True, allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    start_sop_monitoring()
