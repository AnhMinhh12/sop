import cv2
import time
import os
import sys

sys.path.append(os.path.abspath("."))
from shared.services.config_loader import ConfigLoader
from projects.sop_monitoring.hand_detector import HandDetector
from projects.sop_monitoring.core.engines.loader import EngineLoader

def record_stream():
    cap = cv2.VideoCapture("rtsp://admin:Htmp%402019@10.0.7.243:554/Streaming/Channels/102")
    detector = HandDetector("machine_08", confidence_threshold=0.22, model_path="shared/models/yolo/laprap_8_oc.onnx")
    sop_config = ConfigLoader.load_yaml("projects/sop_monitoring/config/laprap.yaml")
    engine = EngineLoader.create_engine("laprap", sop_config)

    out_dir = "scratch/cycle_investigation"
    os.makedirs(out_dir, exist_ok=True)
    
    print("Investigating live stream for 200 frames (~20s)...")
    last_slots_sum = -1
    last_state = ""
    saved_count = 0
    
    for i in range(200):
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.05)
            continue
            
        dets = detector.detect(frame)
        hands = [d for d in dets if d.get("class") == "hand"]
        prods = [d for d in dets if d.get("class") in ["part_hand", "part_tray", "screw"]]
        screws = [d for d in prods if d.get("class") == "screw"]
        part_hands = [d for d in prods if d.get("class") == "part_hand"]
        
        status = engine.update(hands_data=hands, products_data=prods)
        slots_sum = sum(engine.slots)
        
        # Log when state changes or screw count changes
        if slots_sum != last_slots_sum or engine.state != last_state or i % 30 == 0:
            print(f"[{i:03d}] State: {engine.state} | Step: {engine.current_step_idx} | SlotsSum: {slots_sum} (MaxSim: {engine.max_simultaneous}) | ScrewsDet: {len(screws)} | Msg: {engine.status_msg}")
            last_slots_sum = slots_sum
            last_state = engine.state
            
            # Save frame
            if saved_count < 20:
                vis = frame.copy()
                for d in dets:
                    box = d["bbox"]
                    cls = d["class"]
                    conf = d["confidence"]
                    c = (0, 255, 0) if cls == "screw" else ((255, 0, 0) if cls == "hand" else (0, 165, 255))
                    cv2.rectangle(vis, (box[0], box[1]), (box[2], box[3]), c, 2)
                    cv2.putText(vis, f"{cls} {conf:.2f}", (box[0], max(15, box[1]-4)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, c, 1)
                cv2.putText(vis, f"{engine.state} Slots:{engine.slots} Cnt:{slots_sum}", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                cv2.putText(vis, f"Msg: {engine.status_msg}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                cv2.imwrite(f"{out_dir}/img_{saved_count:02d}_f{i:03d}_{engine.state}_{slots_sum}.jpg", vis)
                saved_count += 1
                
        time.sleep(0.08)

    cap.release()
    print("Done recording investigation.")

if __name__ == "__main__":
    record_stream()

