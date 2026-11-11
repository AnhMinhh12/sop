import cv2
import os
import sys

sys.path.append(os.path.abspath("."))
from projects.sop_monitoring.hand_detector import HandDetector

frame = cv2.imread("scratch/original_51.0s.jpg")
print("Original frame shape:", frame.shape)

for conf_th in [0.15, 0.20, 0.25, 0.30]:
    detector = HandDetector("machine_08", confidence_threshold=conf_th, model_path="shared/models/yolo/laprap_8_oc.onnx")
    dets = detector.detect(frame)
    screws = [d for d in dets if d["class"] == "screw"]
    part_hands = [d for d in dets if d["class"] == "part_hand"]
    print(f"\n--- Conf threshold: {conf_th} ---")
    print(f"PartHand: {len(part_hands)}, Screws: {len(screws)}")
    for s in screws:
        print(f"  screw conf={s['confidence']:.3f} bbox={s['bbox']}")

