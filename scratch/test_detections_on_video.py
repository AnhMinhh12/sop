import cv2
import os
import sys

sys.path.append(os.path.abspath("."))
from projects.sop_monitoring.hand_detector import HandDetector

detector = HandDetector("machine_08", confidence_threshold=0.20, model_path="shared/models/yolo/laprap_8_oc.onnx")

for sec in [5, 45, 60, 100]:
    img_path = f"scratch/video_samples/sample_{sec}s.jpg"
    frame = cv2.imread(img_path)
    dets = detector.detect(frame)
    
    print(f"\n=== SAMPLE {sec}s ===")
    for d in dets:
        print(f"  {d['class']:10s} conf={d['confidence']:.3f} bbox={d['bbox']}")

