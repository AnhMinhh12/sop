import cv2
import os
import sys

sys.path.append(os.path.abspath("."))
from projects.sop_monitoring.hand_detector import HandDetector

detector = HandDetector("machine_08", confidence_threshold=0.25, model_path="shared/models/yolo/laprap_8_oc.onnx")

frame = cv2.imread("scratch/video_samples/sample_45s.jpg")
dets = detector.detect(frame)

part = next((d for d in dets if d["class"] == "part_hand"), None)
screws = [d for d in dets if d["class"] == "screw"]

print("Part bbox:", part["bbox"] if part else None)
px1, py1, px2, py2 = part["bbox"]
pw = px2 - px1
ph = py2 - py1

print(f"pw={pw}, ph={ph}, aspect={ph/pw:.2f}")

screws_on_part = []
for s in screws:
    b = s["bbox"]
    scx = (b[0] + b[2]) / 2
    scy = (b[1] + b[3]) / 2
    rel_x = (scx - px1) / pw
    rel_y = (scy - py1) / ph
    screws_on_part.append((rel_y, rel_x, s["confidence"], b))

screws_on_part.sort(key=lambda x: x[0])
for i, (ry, rx, conf, b) in enumerate(screws_on_part):
    side = "LEFT" if rx < 0.50 else "RIGHT"
    print(f"  Screw {i+1}: rel_y={ry:.3f}, rel_x={rx:.3f} ({side}), conf={conf:.3f}, bbox={b}")

