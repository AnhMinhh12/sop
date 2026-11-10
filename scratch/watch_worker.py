import cv2
import time
import os
import sys

sys.path.append(os.path.abspath("."))
from shared.services.config_loader import ConfigLoader
from projects.sop_monitoring.hand_detector import HandDetector
from projects.sop_monitoring.core.engines.loader import EngineLoader

def main():
    cap = cv2.VideoCapture("rtsp://admin:Htmp%402019@10.0.7.243:554/Streaming/Channels/102")
    detector = HandDetector("machine_08", confidence_threshold=0.22, model_path="shared/models/yolo/laprap_8_oc.onnx")
    sop_config = ConfigLoader.load_yaml("projects/sop_monitoring/config/laprap.yaml")
    engine = EngineLoader.create_engine("laprap", sop_config)

    out_dir = "scratch/live_worker_action"
    os.makedirs(out_dir, exist_ok=True)
    
    print("Watching worker action for 250 frames (~25s)...")
    saved = 0
    for i in range(250):
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
        
        # Save any frame where screws > 0 or state changes or every 20 frames
        should_save = False
        if len(screws) > 0 and (i % 5 == 0):
            should_save = True
        elif engine.state != "IDLE" and (i % 5 == 0):
            should_save = True
        elif i % 25 == 0:
            should_save = True
            
        if should_save and saved < 25:
            vis = frame.copy()
            for d in dets:
                box = d["bbox"]
                cls = d["class"]
                conf = d["confidence"]
                c = (0, 255, 0) if cls == "screw" else ((255, 0, 0) if cls == "hand" else (0, 165, 255))
                cv2.rectangle(vis, (box[0], box[1]), (box[2], box[3]), c, 2)
                cv2.putText(vis, f"{cls} {conf:.2f}", (box[0], max(15, box[1]-4)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, c, 1)
            cv2.putText(vis, f"{engine.state} Step:{engine.current_step_idx} Slots:{engine.slots} ({slots_sum}/8)", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            cv2.putText(vis, f"Msg: {engine.status_msg}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cv2.imwrite(f"{out_dir}/act_{saved:02d}_f{i:03d}_{engine.state}_{slots_sum}.jpg", vis)
            saved += 1
            print(f"[{i:03d}] State: {engine.state} | Step: {engine.current_step_idx} | SlotsSum: {slots_sum} | Screws: {len(screws)} | Msg: {engine.status_msg}")

        time.sleep(0.08)

    cap.release()
    print(f"Done. Saved {saved} frames.")

if __name__ == "__main__":
    main()

