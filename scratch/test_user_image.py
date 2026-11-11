import cv2
import os
import sys

sys.path.append(os.path.abspath("."))
from projects.sop_monitoring.hand_detector import HandDetector

img_path = "C:/Users/it07/.gemini/antigravity/brain/88e475b7-230d-49ed-8d09-458bee4e6c85/.user_uploaded/media_1794279411729_92d31d8d.jpg"
frame = cv2.imread(img_path)
print("Image shape:", frame.shape if frame is not None else "None")

detector = HandDetector("machine_08", confidence_threshold=0.25, model_path="shared/models/yolo/laprap_8_oc.onnx")
dets = detector.detect(frame)

print(f"\nDetections count: {len(dets)}")
screws = []
parts = []
hands = []

for d in dets:
    c = d["class"]
    conf = d["confidence"]
    b = d["bbox"]
    print(f"  {c:12s} conf={conf:.3f} bbox={b}")
    if c == "screw":
        screws.append(d)
    elif c == "part_hand":
        parts.append(d)
    elif c == "hand":
        hands.append(d)

print(f"\nSummary: {len(hands)} hands, {len(parts)} parts, {len(screws)} screws")

