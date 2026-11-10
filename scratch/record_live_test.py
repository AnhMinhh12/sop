import cv2, time, os, sys
sys.path.append(os.path.abspath("."))
from projects.sop_monitoring.hand_detector import HandDetector
from projects.sop_monitoring.core.engines.loader import EngineLoader
from shared.services.config_loader import ConfigLoader

cap = cv2.VideoCapture("rtsp://admin:Htmp%402019@10.0.7.243:554/Streaming/Channels/102")
detector = HandDetector("machine_08", confidence_threshold=0.22, model_path="shared/models/yolo/laprap_8_oc.onnx")
sop_config = ConfigLoader.load_yaml("projects/sop_monitoring/config/laprap.yaml")
engine = EngineLoader.create_engine("laprap", sop_config)

print("Capturing 40 frames and tracking detections...")
saved_frames = 0
for frame_i in range(40):
    ret, frame = cap.read()
    if not ret:
        break
    dets = detector.detect(frame)
    hands = [d for d in dets if d.get("class") == "hand"]
    prods = [d for d in dets if d.get("class") in ["part_hand", "part_tray", "screw"]]
    
    status = engine.update(hands_data=hands, products_data=prods)
    screws = [d for d in prods if d.get("class") == "screw"]
    parts = [d for d in prods if d.get("class") == "part_hand"]
    
    cnt = sum(engine.slots)
    print(f"F{frame_i:02d}: state={engine.state}, part={len(parts)}, screws_det={len(screws)}, cnt={cnt}, slots={engine.slots}")
    if len(screws) > 0:
        for s in screws:
            print(f"     screw conf={s['confidence']:.3f}, bbox={s['bbox']}")
        if saved_frames < 3:
            cv2.imwrite(f"C:/Users/it07/.gemini/antigravity/brain/280ea8cc-b6e9-4fde-af82-57a4804840ce/screw_detected_{saved_frames}.jpg", frame)
            saved_frames += 1
    time.sleep(0.1)

cap.release()
print("Done.")

