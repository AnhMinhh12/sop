import cv2
import os
import sys
import time

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Ensure project root is in python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set logging level
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestSOP")

from shared.services.config_loader import ConfigLoader
from shared.inference_engine import InferenceEngine
from projects.sop_monitoring.processor import FrameProcessor
from projects.sop_monitoring.core.engines.loader import EngineLoader
from projects.sop_monitoring.core.violation_detector import ViolationDetector

# Mock time.time globally
simulated_time = 0.0
def mock_time():
    return simulated_time

import time as real_time
time.time = mock_time

def main():
    global simulated_time
    config = ConfigLoader.load_config()
    if not config:
        print("Failed to load config.")
        return

    # Find machine_07 camera config
    cam_cfg = next((c for c in config["cameras"] if c["id"] == "machine_07"), None)
    if not cam_cfg:
        print("machine_07 config not found.")
        return

    # Initialize Inference Engine
    yolo_cfg = config["models"]["yolo"]
    model_path = cam_cfg.get("yolo_model", yolo_cfg["weights"])
    print(f"Loading model: {model_path}")
    InferenceEngine(
        model_path=model_path,
        num_threads=4,
        input_size=yolo_cfg.get("input_size", 416)
    )

    # Load SOP
    sop_file = cam_cfg.get("sop_file")
    sop_def = ConfigLoader.load_yaml(sop_file)
    
    # Load Engine
    engine_id = cam_cfg.get("engine_id")
    engine = EngineLoader.create_engine(engine_id, sop_def)
    violation_detector = ViolationDetector(cam_cfg["id"])
    
    # Create Processor
    processor = FrameProcessor(
        camera_config=cam_cfg,
        engine=engine,
        violation_detector=violation_detector,
        audio_alert=None,
        clip_saver=None
    )
    processor.sop_config = sop_def
    
    # Open video directly for deterministic processing
    video_path = cam_cfg["rtsp_url"]
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Failed to open video: {video_path}")
        return
        
    frame_idx = 0
    last_status = None
    w, h = 640, 480
    
    print("Starting deterministic SOP simulation on video...")
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        # Simulate time at 15 FPS
        simulated_time = frame_idx / 15.0
        
        frame_resized = cv2.resize(frame, (w, h))
        
        # Run processor step synchronously
        processor._target_w = w
        processor._target_h = h
        
        hands_data = processor._cached_hands
        if frame_idx % 2 == 0:
            detections = processor.hand_detector.detect(frame_resized)
            
            # separation and sizing filter
            hand_dets = [
                d for d in detections 
                if d.get("class", "hand") == "hand"
                and (d["bbox"][2] - d["bbox"][0]) <= w * 0.35
                and (d["bbox"][3] - d["bbox"][1]) <= h * 0.35
            ]
            processor._cached_products = [d for d in detections if d.get("class") == "sp"]
            processor._cached_robots = [d for d in detections if d.get("class") == "robot"]
            
            filtered_dets = processor._filter_detections_by_roi(hand_dets)
            hands_data = processor._associate_hands(filtered_dets)
            processor._cached_hands = hands_data
            processor._last_hands_update_time = simulated_time
            
        # Clear cache if no hands seen for 0.8s
        if simulated_time - processor._last_hands_update_time > 0.8:
            processor._cached_hands = []
            processor._cached_products = []
            processor._cached_robots = []
            hands_data = []
            
        status = processor.engine.update(hands_data, processor._cached_products, processor._cached_robots)
        
        # Check if there is a change in status
        status_str = f"Step: {status.get('step_index')} ({status.get('expected_step')}), Status: {status.get('sop_status')}, Msg: {status.get('status_msg')}"
        if status_str != last_status:
            print(f"Frame {frame_idx} (Time {simulated_time:.2f}s): {status_str}")
            last_status = status_str
            
        if status.get("is_failed") or status.get("sop_status") == "violation":
            print(f"Frame {frame_idx}: FAILURE DETECTED! Violation type: {status.get('violation_type')}")
            # Reset engine to continue testing
            processor.engine.reset()
            
        if status.get("sop_status") == "completed":
            print(f"Frame {frame_idx}: CYCLE COMPLETED SUCCESSFULLY!")
            
        frame_idx += 1
        
    cap.release()
    print("Done testing.")

if __name__ == "__main__":
    main()
