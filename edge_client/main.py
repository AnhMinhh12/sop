"""
Edge Client Main Entry Point

Chạy trên máy trạm con (mini-PC):
- Đọc video từ RTSP camera
- Chạy YOLO inference local
- Xử lý FSM logic
- Push frame + status lên Hub

Usage:
    cd edge_client
    python main.py --config config.yaml
    # Hoặc dùng env vars:
    HUB_URL=http://10.0.10.100:5001 HUB_API_KEY=secret python main.py
"""
import os
import sys
import time
import logging
import argparse
import cv2
import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from edge_client.frame_pusher import FramePusher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("EdgeClient")


def load_edge_config() -> dict:
    """Load config từ file hoặc env vars."""
    import yaml

    config = {}

    # Load from file if exists
    config_file = os.getenv("EDGE_CONFIG_FILE", "config.yaml")
    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}

    # Override with env vars (higher priority)
    config['hub_url'] = os.getenv("HUB_URL", config.get('hub', {}).get('url', 'http://localhost:5001'))
    config['hub_api_key'] = os.getenv("HUB_API_KEY", config.get('hub', {}).get('api_key', 'change-me-in-production'))

    config['camera_id'] = os.getenv("CAMERA_ID", config.get('camera', {}).get('id', 'edge_camera'))
    config['rtsp_url'] = os.getenv("RTSP_URL", config.get('camera', {}).get('rtsp_url', ''))
    config['camera_name'] = os.getenv("CAMERA_NAME", config.get('camera', {}).get('name', 'Edge Camera'))

    config['model_path'] = os.getenv("MODEL_PATH", config.get('ai', {}).get('model_path', 'shared/models/yolo/laprap.onnx'))
    config['sop_file'] = os.getenv("SOP_FILE", config.get('sop', {}).get('file', ''))

    config['push_interval'] = float(os.getenv("PUSH_INTERVAL", config.get('push', {}).get('interval_sec', 1.0)))
    config['jpeg_quality'] = int(os.getenv("JPEG_QUALITY", config.get('push', {}).get('quality', 60)))

    return config


def draw_annotations(frame, hands, products, robots, engine, camera_id, status):
    """Vẽ annotations lên frame."""
    h, w = frame.shape[:2]

    # Draw zones
    if engine and hasattr(engine, 'zones') and engine.zones:
        from shared.services.annotator import Annotator
        Annotator.draw_zones(frame, engine.zones)

    # Draw hand boxes
    for hand in hands:
        bbox = hand["bbox"]
        color = (0, 255, 255) if hand.get("label") == "left" else (0, 230, 20)
        x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

    # Draw product boxes
    prod_color = (0, 128, 255) if getattr(engine, "product_id", None) == "laprap" else (255, 0, 0)
    for prod in products:
        bbox = prod["bbox"]
        x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
        cv2.rectangle(frame, (x1, y1), (x2, y2), prod_color, 2)
        cv2.putText(frame, "Product", (x1, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, prod_color, 1, cv2.LINE_AA)

    # Draw robot boxes
    for robot in robots:
        bbox = robot["bbox"]
        x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 100, 180), 2)
        cv2.putText(frame, "Robot", (x1, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 100, 180), 1, cv2.LINE_AA)

    # Status overlay
    status_text = status.get('sop_status', 'idle')
    cv2.putText(frame, f"Edge: {camera_id}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.putText(frame, f"Status: {status_text}", (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    return frame


def main():
    parser = argparse.ArgumentParser(description='Edge Client for AI Monitoring Hub')
    parser.add_argument('--config', default='config.yaml', help='Config file path')
    parser.add_argument('--hub-url', help='Hub server URL')
    parser.add_argument('--api-key', help='Hub API key')
    parser.add_argument('--camera-id', help='Camera ID')
    parser.add_argument('--rtsp-url', help='RTSP URL')
    args = parser.parse_args()

    os.environ['EDGE_CONFIG_FILE'] = args.config

    logger.info("=== EDGE CLIENT STARTING ===")

    # Load config
    config = load_edge_config()

    # Override with CLI args
    if args.hub_url:
        config['hub_url'] = args.hub_url
    if args.api_key:
        config['hub_api_key'] = args.api_key
    if args.camera_id:
        config['camera_id'] = args.camera_id
    if args.rtsp_url:
        config['rtsp_url'] = args.rtsp_url

    # Validate required config
    if not config.get('hub_url'):
        logger.error("hub_url is required")
        sys.exit(1)
    if not config.get('camera_id'):
        logger.error("camera_id is required")
        sys.exit(1)
    if not config.get('rtsp_url'):
        logger.error("rtsp_url is required")
        sys.exit(1)

    camera_id = config['camera_id']
    logger.info(f"Camera ID: {camera_id}")
    logger.info(f"Hub URL: {config['hub_url']}")
    logger.info(f"RTSP: {config['rtsp_url']}")

    # Initialize components
    from shared.services.config_loader import ConfigLoader
    from shared.rtsp_manager import RTSPStream
    from shared.inference_engine import InferenceEngine
    from projects.sop_monitoring.hand_detector import HandDetector
    from projects.sop_monitoring.core.engines.loader import EngineLoader

    # Load SOP config
    sop_file = config.get('sop_file')
    if sop_file and os.path.exists(sop_file):
        sop_def = ConfigLoader.load_yaml(sop_file)
        logger.info(f"Loaded SOP from: {sop_file}")
    else:
        clean_id = camera_id.replace("station_", "").replace("machine_", "")
        sop_def = ConfigLoader.load_sop_definition(clean_id)
        if not sop_def:
            logger.warning(f"No SOP found for {camera_id}, using default config")
            sop_def = {"steps": [], "zones": {}}

    # Initialize RTSP stream
    logger.info("Connecting to RTSP stream...")
    stream = RTSPStream(
        camera_id,
        config['rtsp_url'],
        fps_cap=15,
        target_width=640,
        target_height=480
    )
    stream.start()

    # Wait for first frame
    for _ in range(30):
        frame = stream.get_frame()
        if frame is not None:
            logger.info("RTSP stream connected!")
            break
        time.sleep(0.5)
    else:
        logger.error("Failed to connect to RTSP stream")
        sys.exit(1)

    # Initialize AI Inference
    model_path = config.get('model_path')
    if model_path and os.path.exists(model_path):
        logger.info(f"Loading model: {model_path}")
        inference = InferenceEngine(model_path=model_path, num_threads=2)
        conf_thres = config.get("ai", {}).get("conf_threshold") or config.get("conf_threshold") or 0.25
        iou_thres = config.get("ai", {}).get("iou_threshold") or config.get("iou_threshold") or 0.45
        hand_detector = HandDetector(
            camera_id, 
            confidence_threshold=conf_thres, 
            iou_threshold=iou_thres, 
            model_path=model_path
        )
    else:
        logger.warning("Model not found, running in passthrough mode (no AI)")
        inference = None
        hand_detector = None

    # Initialize Engine (FSM logic)
    engine = None
    if sop_def.get('steps'):
        engine_id = sop_def.get('engine_id', 'laprap')
        logger.info(f"Loading engine: {engine_id}")
        try:
            engine = EngineLoader.create_engine(engine_id, sop_def)
        except Exception as e:
            logger.error(f"Failed to load engine: {e}")
            sys.exit(1)
    else:
        logger.info("No SOP steps defined, running in passthrough mode")

    # Initialize Frame Pusher
    pusher = FramePusher(
        hub_url=config['hub_url'],
        api_key=config['hub_api_key'],
        camera_id=camera_id
    )
    pusher.set_push_interval(config['push_interval'])

    logger.info(f"Push interval: {config['push_interval']}s")
    logger.info("=== EDGE CLIENT READY ===")
    logger.info(f"Pushing to: {config['hub_url']}/api/station/{camera_id}/push_frame")

    # Main loop
    frame_count = 0
    cached_hands = []
    cached_products = []
    cached_robots = []
    last_push_time = 0
    push_interval = config['push_interval']
    jpeg_quality = config['jpeg_quality']

    try:
        while True:
            loop_start = time.time()

            # Get frame
            frame = stream.get_frame()
            if frame is None:
                time.sleep(0.1)
                continue

            # AI Processing (every 2 frames)
            if hand_detector and inference and frame_count % 2 == 0:
                detections = hand_detector.detect(frame)
                cached_hands = [
                    d for d in detections 
                    if d.get("class", "hand") == "hand"
                    and (d["bbox"][2] - d["bbox"][0]) <= frame.shape[1] * 0.35
                    and (d["bbox"][3] - d["bbox"][1]) <= frame.shape[0] * 0.35
                ]
                cached_products = [d for d in detections if d.get("class") == "sp"]
                cached_robots = [d for d in detections if d.get("class") == "robot"]

            # Update Engine FSM
            status = {"sop_status": "idle", "progress_percent": 0}
            if engine:
                status = engine.update(cached_hands, cached_products, cached_robots)

            # Annotate and draw
            display_frame = frame.copy()
            display_frame = draw_annotations(display_frame, cached_hands, cached_products, cached_robots, engine, camera_id, status)

            # Push to Hub at interval
            current_time = time.time()
            if current_time - last_push_time >= push_interval:
                ret, buffer = cv2.imencode('.jpg', display_frame,
                                           [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
                if ret:
                    frame_bytes = buffer.tobytes()
                    success = pusher.push(frame_bytes, status, cached_hands)

                    if success:
                        if frame_count % 100 == 0:
                            logger.info(f"Pushed frame {frame_count} - Status: {status.get('sop_status')}")
                    else:
                        if frame_count % 50 == 0:
                            logger.warning(f"Push failed, consecutive errors: {pusher.consecutive_errors}")

                last_push_time = current_time

            frame_count += 1

            # Adaptive sleep (~30 FPS cap)
            elapsed = time.time() - loop_start
            time.sleep(max(0.001, 0.033 - elapsed))

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        stream.stop()
        logger.info("Edge client stopped")


if __name__ == "__main__":
    main()
