import cv2
import os
import sys
import numpy as np

# Ensure project root is in python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from projects.sop_monitoring.hand_detector import HandDetector

def test_stream(name, url):
    print(f"\n================ Testing Stream: {name} ================")
    cap = cv2.VideoCapture(url)
    if not cap.isOpened():
        print(f"Failed to open {name}")
        return
        
    # Flush a few frames
    for _ in range(10):
        cap.grab()
        
    ret, frame = cap.read()
    if not ret or frame is None:
        print(f"Failed to read frame from {name}")
        cap.release()
        return
        
    orig_h, orig_w = frame.shape[:2]
    print(f"Original resolution: {orig_w}x{orig_h}")
    
    # Initialize detector
    model_path = "shared/models/yolo/max.onnx"
    detector = HandDetector("test_cam", confidence_threshold=0.15, model_path=model_path)
    
    # Test 1: Original size
    print("--- Test 1: Original size ---")
    dets_orig = detector.detect(frame)
    print(f"Detections: {dets_orig}")
    if dets_orig:
        draw_and_save(frame.copy(), dets_orig, f"live_{name}_orig.jpg")
        
    # Test 2: Resized to 640x480 (Distorted aspect ratio if original is 16:9)
    print("--- Test 2: Resized to 640x480 ---")
    frame_640x480 = cv2.resize(frame, (640, 480))
    dets_640x480 = detector.detect(frame_640x480)
    print(f"Detections: {dets_640x480}")
    if dets_640x480:
        draw_and_save(frame_640x480.copy(), dets_640x480, f"live_{name}_640x480.jpg")
        
    # Test 3: Resized to 640x360 (Keep 16:9 aspect ratio)
    print("--- Test 3: Resized to 640x360 ---")
    frame_640x360 = cv2.resize(frame, (640, 360))
    dets_640x360 = detector.detect(frame_640x360)
    print(f"Detections: {dets_640x360}")
    if dets_640x360:
        draw_and_save(frame_640x360.copy(), dets_640x360, f"live_{name}_640x360.jpg")
        
    cap.release()

def draw_and_save(img, detections, filename):
    for d in detections:
        bbox = d["bbox"]
        cls = d["class"]
        conf = d["confidence"]
        color = (0, 230, 20) if cls == "hand" else ((255, 0, 0) if cls == "sp" else (255, 100, 180))
        cv2.rectangle(img, (int(bbox[0]), int(bbox[1])), (int(bbox[2]), int(bbox[3])), color, 2)
        cv2.putText(img, f"{cls} {conf:.2f}", (int(bbox[0]), int(bbox[1] - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
    cv2.imwrite(filename, img)
    print(f"Saved {filename}")

def main():
    test_stream("Channel_101", "rtsp://admin:Htmp%402019@10.0.7.47:554/Streaming/Channels/101")
    test_stream("Channel_102", "rtsp://admin:Htmp%402019@10.0.7.47:554/Streaming/Channels/102")

if __name__ == "__main__":
    main()
