import cv2
import os
import sys

sys.path.append(os.path.abspath("."))
from shared.services.config_loader import ConfigLoader
from projects.sop_monitoring.hand_detector import HandDetector
from projects.sop_monitoring.core.engines.loader import EngineLoader

def test_engine_on_video():
    video_path = "data/recordings/laprap_20261103_131237_10min.mp4"
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 20
    
    detector = HandDetector("machine_08", confidence_threshold=0.22, model_path="shared/models/yolo/laprap_8_oc.onnx")
    sop_config = ConfigLoader.load_yaml("projects/sop_monitoring/config/laprap.yaml")
    engine = EngineLoader.create_engine("laprap", sop_config)

    print("Running engine on first 120 seconds of video...")
    
    # Let's process every 2nd frame (10 FPS)
    frame_idx = 0
    while frame_idx < 120 * fps:
        ret, frame = cap.read()
        if not ret:
            break
            
        frame_idx += 1
        if frame_idx % 2 != 0:
            continue
            
        dets = detector.detect(frame)
        hands = [d for d in dets if d.get("class") == "hand"]
        prods = [d for d in dets if d.get("class") in ["part_hand", "part_tray", "screw"]]
        screws = [d for d in prods if d.get("class") == "screw"]
        part_hands = [d for d in prods if d.get("class") == "part_hand"]
        
        status = engine.update(hands_data=hands, products_data=prods)
        
        sec = frame_idx / fps
        slots_sum = sum(engine.slots)
        
        # Print when anything interesting happens
        if len(screws) > 0 or engine.state != "IDLE" or frame_idx % 40 == 0:
            print(f"[{sec:5.1f}s | F{frame_idx:04d}] State: {engine.state:11s} | Step: {engine.current_step_idx} | Slots: {engine.slots} ({slots_sum}/8) | ScrewsDet: {len(screws)} | Msg: {engine.status_msg}")

    cap.release()

if __name__ == "__main__":
    test_engine_on_video()

