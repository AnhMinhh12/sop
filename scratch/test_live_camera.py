import cv2
import time
import os
import sys

sys.path.append(os.path.abspath("."))
from shared.services.config_loader import ConfigLoader
from projects.sop_monitoring.hand_detector import HandDetector
from projects.sop_monitoring.core.engines.loader import EngineLoader

def test_live():
    cap = cv2.VideoCapture("rtsp://admin:Htmp%402019@10.0.7.243:554/Streaming/Channels/102")
    detector = HandDetector("machine_08", confidence_threshold=0.22, model_path="shared/models/yolo/laprap_8_oc.onnx")
    sop_config = ConfigLoader.load_yaml("projects/sop_monitoring/config/laprap.yaml")
    engine = EngineLoader.create_engine("laprap", sop_config)

    print("Reading frames from RTSP camera...")
    for i in range(30):
        ret, frame = cap.read()
        if not ret:
            print("Failed to read frame")
            time.sleep(0.1)
            continue
            
        dets = detector.detect(frame)
        hands = [d for d in dets if d.get("class") == "hand"]
        prods = [d for d in dets if d.get("class") in ["part_hand", "part_tray", "screw"]]
        screws = [d for d in prods if d.get("class") == "screw"]
        part_hands = [d for d in prods if d.get("class") == "part_hand"]
        
        status = engine.update(hands_data=hands, products_data=prods)
        
        print(f"[{i:02d}] Hands: {len(hands)}, PartHand: {len(part_hands)}, Screws: {len(screws)}")
        for s in screws:
            print(f"    -> Screw: conf={s['confidence']:.2f}, bbox={s['bbox']}")
        for ph in part_hands:
            print(f"    -> PartHand: conf={ph['confidence']:.2f}, bbox={ph['bbox']}")
        print(f"    State: {engine.state}, Slots: {engine.slots}, Sum: {sum(engine.slots)}, Msg: {engine.status_msg}")
        time.sleep(0.15)
        
    cap.release()

if __name__ == "__main__":
    test_live()

