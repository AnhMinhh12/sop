import cv2
import sys
import os
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from projects.sop_monitoring.hand_detector import HandDetector

def main():
    model_path = "shared/models/yolo/max.onnx"
    detector = HandDetector("test_cam", confidence_threshold=0.15, model_path=model_path)
    
    url = "rtsp://admin:Htmp%402019@10.0.7.47:554/Streaming/Channels/102"
    print(f"Connecting to {url}...")
    cap = cv2.VideoCapture(url)
    if not cap.isOpened():
        print("Failed to open RTSP stream")
        return
        
    # Flush frames for a bit
    print("Flushing buffer...")
    for _ in range(30):
        cap.grab()
        
    ret, frame = cap.read()
    if not ret or frame is None:
        print("Failed to read frame")
        cap.release()
        return
        
    print(f"Frame shape: {frame.shape}")
    
    # Run detection
    dets = detector.detect(frame)
    print(f"Detections: {dets}")
    
    # Draw detections
    for d in dets:
        bbox = d["bbox"]
        cls = d["class"]
        conf = d["confidence"]
        color = (0, 230, 20) if cls == "hand" else ((255, 0, 0) if cls == "sp" else (255, 100, 180))
        cv2.rectangle(frame, (int(bbox[0]), int(bbox[1])), (int(bbox[2]), int(bbox[3])), color, 2)
        cv2.putText(frame, f"{cls} {conf:.2f}", (int(bbox[0]), int(bbox[1] - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
                    
    cv2.imwrite("live_check_rtsp.jpg", frame)
    print("Saved live_check_rtsp.jpg")
    cap.release()

if __name__ == "__main__":
    main()
