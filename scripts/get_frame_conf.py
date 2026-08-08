import cv2
import os
import sys

# Ensure project root is in python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from projects.sop_monitoring.hand_detector import HandDetector

def main():
    model_path = "shared/models/yolo/TFF4040_final.onnx"
    video_path = "data/recordings/08_08_20260808_113003_3min.mp4"
    
    detector = HandDetector("test_cam", confidence_threshold=0.05, model_path=model_path)
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("Failed to open video")
        return
        
    frame_idx = 0
    w, h = 640, 480
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        if 2070 <= frame_idx <= 2085:
            frame_resized = cv2.resize(frame, (w, h))
            detections = detector.detect(frame_resized)
            print(f"--- Frame {frame_idx} ---")
            for det in detections:
                if det["class"] == "hand":
                    bbox = det["bbox"]
                    print(f"Hand det: Conf={det['confidence']:.4f}, Box=[{int(bbox[0])}, {int(bbox[1])}, {int(bbox[2])}, {int(bbox[3])}]")
                    
        if frame_idx > 2085:
            break
        frame_idx += 1
        
    cap.release()

if __name__ == "__main__":
    main()
