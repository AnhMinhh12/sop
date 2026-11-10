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

    out_dir = "scratch/debug_frames"
    os.makedirs(out_dir, exist_ok=True)

    print("Capturing 60 frames (approx 6 seconds)...")
    saved = 0
    for i in range(60):
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.05)
            continue
            
        dets = detector.detect(frame)
        hands = [d for d in dets if d.get("class") == "hand"]
        prods = [d for d in dets if d.get("class") in ["part_hand", "part_tray", "screw"]]
        screws = [d for d in prods if d.get("class") == "screw"]
        part_hands = [d for d in prods if d.get("class") == "part_hand"]
        part_trays = [d for d in prods if d.get("class") == "part_tray"]
        
        status = engine.update(hands_data=hands, products_data=prods)
        
        if len(screws) > 0 or len(part_hands) > 0 or i % 10 == 0:
            print(f"[{i:02d}] Hands:{len(hands)} PartHand:{len(part_hands)} PartTray:{len(part_trays)} Screws:{len(screws)} | State:{engine.state} StepIdx:{engine.current_step_idx} Slots:{engine.slots} Cnt:{sum(engine.slots)} Msg:{engine.status_msg}")
            for s in screws:
                print(f"    SCREW: conf={s['confidence']:.3f}, bbox={s['bbox']}")
            for ph in part_hands:
                print(f"    PART: conf={ph['confidence']:.3f}, bbox={ph['bbox']}")

        # Save annotated image for inspection
        if (len(screws) > 0 or len(part_hands) > 0) and saved < 10:
            vis = frame.copy()
            for d in dets:
                box = d["bbox"]
                cls = d["class"]
                conf = d["confidence"]
                color = (0, 255, 0) if cls == "screw" else ((255, 0, 0) if cls == "hand" else (0, 165, 255))
                cv2.rectangle(vis, (box[0], box[1]), (box[2], box[3]), color, 2)
                cv2.putText(vis, f"{cls} {conf:.2f}", (box[0], max(15, box[1] - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            cv2.putText(vis, f"State: {engine.state} Slots:{engine.slots} Step:{engine.current_step_idx}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            cv2.imwrite(f"{out_dir}/frame_{saved:02d}.jpg", vis)
            saved += 1
            
        time.sleep(0.08)

    cap.release()
    print(f"Finished. Saved {saved} frames to {out_dir}")

if __name__ == "__main__":
    main()

